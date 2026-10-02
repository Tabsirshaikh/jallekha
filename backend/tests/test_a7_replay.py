"""A7 replay output for P3's T9: the real planner run day by day on the A8 replay (Mar-Jul
2025, seed 0, tight capacity), with per-day plans, inputs and per-group quality signals, and
a re-run hook so T9 can degrade a signal and compare plans. Labelled SIMULATION."""

from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
import sys
from collections import defaultdict
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / f"scripts/sandbox/{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


replay_build = _load("build_planner_replay")


def _rows(relative: str) -> list[dict[str, str]]:
    with (ROOT / relative).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


@pytest.fixture(scope="module")
def days() -> list[dict[str, str]]:
    return _rows(replay_build.DAYS)


@pytest.fixture(scope="module")
def groups() -> list[dict[str, str]]:
    return _rows(replay_build.GROUPS)


@pytest.fixture(scope="module")
def setup():
    return replay_build.load(ROOT)


def test_outputs_match_their_checks() -> None:
    checks = json.loads((ROOT / replay_build.CHECKS).read_text(encoding="utf-8"))
    for path, digest in checks["outputs_sha256"].items():
        assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == digest, path


def test_every_replay_day_has_a_plan_and_is_labelled(days, groups) -> None:
    assert len(days) == 153  # Mar-Jul 2025
    assert {r["label"] for r in days} == {r["label"] for r in groups} == {"SIMULATION"}
    for r in days:
        # lent trips are part of the city's trips, so they never add capacity
        assert int(r["booked_served"]) + int(r["reserve_trips"]) <= int(r["trips"])
        assert len(r["digest"]) == 64
    by_day = defaultdict(int)
    for g in groups:
        by_day[g["day"]] += int(g["served"])
    assert all(by_day[r["day"]] == int(r["booked_served"]) for r in days)


def test_quality_signals_are_per_group_and_explain_the_flags(groups) -> None:
    assert {g["need_basis"] for g in groups} <= {"CENSUS_2011", "FALLBACK_MEDIAN"}
    for g in groups:
        assert (g["flagged"] == "1") == (g["need_basis"] == "FALLBACK_MEDIAN")
        if g["group"].startswith("ward:"):
            assert g["location_status"] == "PLACED_IN_WARD"
        else:
            assert g["location_status"].startswith("UNMAPPED")


def test_first_days_reproduce(setup, days) -> None:
    rerun = list(replay_build.replay(setup, max_days=3))
    for result in rerun:
        committed = next(r for r in days if r["day"] == result.day.isoformat())
        assert committed["digest"] == result.plan.digest


def test_t9_can_degrade_a_signal_and_compare(setup) -> None:
    """Treat every group as fallback (no Census need data): plans change, and every group in
    the plan becomes flagged."""
    full = next(iter(replay_build.replay(setup, max_days=1)))
    median = replay_build.fallback_value(setup)
    degraded_entitlement = dict.fromkeys(setup.ctx.entitlement, median)
    degraded = next(
        iter(
            replay_build.replay(
                setup,
                max_days=1,
                entitlement=degraded_entitlement,
                fallback_groups=frozenset(setup.ctx.entitlement),
            )
        )
    )
    assert degraded.plan.digest != full.plan.digest
    served_groups = {b.group for p in degraded.plan.stations.values() for b in p.served}
    assert served_groups <= set(degraded.plan.flags)
