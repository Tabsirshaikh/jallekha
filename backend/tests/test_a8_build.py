"""A8 committed outputs: stand-in stations and the SIMULATION results (F19).

The full run (2 replays x 2 capacity scenarios x 7 policies x 30 seeds) takes about half an
hour, so these tests check the committed files against their checks file and against each
other, and re-run one seed of the smaller replay to show the results reproduce."""

from __future__ import annotations

import csv
import hashlib
import importlib.util
import io
import json
import sys
from collections import Counter
from pathlib import Path

import pytest

from app.config.sandbox import SANDBOX_CONFIG
from app.services import sandbox

ROOT = Path(__file__).resolve().parents[2]


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / f"scripts/sandbox/{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module  # dataclasses need the module registered
    spec.loader.exec_module(module)
    return module


stations_build = _load("build_stations")
sandbox_build = _load("build_sandbox")


def _rows(relative: str) -> list[dict[str, str]]:
    with (ROOT / relative).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


@pytest.fixture(scope="module")
def results() -> list[dict[str, str]]:
    return _rows(sandbox_build.RESULTS)


@pytest.fixture(scope="module")
def summary() -> dict:
    return json.loads((ROOT / sandbox_build.SUMMARY).read_text(encoding="utf-8"))


def test_stations_are_reproducible_committed_and_labelled() -> None:
    built = stations_build.build()
    for path, content in built.items():
        assert (ROOT / path).read_bytes() == content
    stations = list(csv.DictReader(io.StringIO(built[stations_build.STATIONS].decode())))
    assert len(stations) == SANDBOX_CONFIG.station_count == 90
    assert {s["basis"] for s in stations} == {"ASSUMED_STAND_IN"}
    assert sum(int(s["home_sections"]) for s in stations) >= 170
    checks = json.loads(built[stations_build.CHECKS])["summary"]
    assert checks["booking_share_by_point_basis"]["GEOCODED"] > 0.85


def test_committed_outputs_match_their_checks() -> None:
    checks = json.loads((ROOT / sandbox_build.CHECKS).read_text(encoding="utf-8"))
    for path, digest in checks["outputs_sha256"].items():
        assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == digest, path
    for path, digest in checks["inputs_sha256"].items():
        assert sandbox_build._sha(ROOT / path) == digest, path


def test_every_policy_runs_on_the_same_30_seeds_and_is_labelled(results) -> None:
    assert {r["label"] for r in results} == {"SIMULATION"}
    cells = Counter((r["replay"], r["scenario"], r["policy"]) for r in results)
    assert set(cells) == {
        (rp, sc, p)
        for rp in sandbox_build.REPLAYS
        for sc in sandbox_build.SCENARIOS
        for p in sandbox.POLICIES
    }
    assert set(cells.values()) == {SANDBOX_CONFIG.seeds}
    assert SANDBOX_CONFIG.seeds >= 30
    for r in results:
        assert int(r["served"]) + int(r["unmet"]) == int(r["booked"])
    # common random numbers: every policy sees the same bookings for a seed
    booked = {}
    for r in results:
        booked.setdefault((r["replay"], r["seed"]), set()).add(r["booked"])
    assert all(len(v) == 1 for v in booked.values())


def test_tight_capacity_matches_the_real_2026_delivered_share(results, summary) -> None:
    for replay_name in sandbox_build.REPLAYS:
        b1 = [
            float(r["served_share"])
            for r in results
            if (r["replay"], r["scenario"], r["policy"]) == (replay_name, "tight", "B1")
        ]
        assert sum(b1) / len(b1) == pytest.approx(SANDBOX_CONFIG.tight_delivered_share, abs=0.01)
    real = summary["real_baselines"]["delivered_share"]["jun_aug_2026"]
    assert real == pytest.approx(SANDBOX_CONFIG.tight_delivered_share, abs=0.02)


def test_summary_is_the_comparison_of_the_results(results, summary) -> None:
    for replay_name, scenarios in summary["results"].items():
        for scenario, block in scenarios.items():
            subset = [
                {"policy": r["policy"], "seed": int(r["seed"])}
                | {m: float(r[m]) for m in sandbox_build.METRICS}
                for r in results
                if r["replay"] == replay_name and r["scenario"] == scenario
            ]
            expected = sandbox.compare(subset, list(sandbox_build.METRICS))
            for policy, metrics in expected.items():
                for metric, stats in metrics.items():
                    got = block["policies"][policy][metric]
                    for key, value in stats.items():
                        assert got[key] == pytest.approx(value, abs=1e-6), (policy, metric, key)


def test_real_baselines_and_duplicates_are_kept_apart(summary) -> None:
    assert summary["label"] == "SIMULATION"
    assert summary["real_baselines"]["label"] == "REAL"
    assert summary["real_baselines"]["booking_gini_sections"] == pytest.approx(0.78, abs=0.01)
    assert summary["duplicates"]["status"] == "NOT_AVAILABLE"


def test_where_jl_is_worse_is_listed(summary) -> None:
    listed = {(w["replay"], w["scenario"], w["metric"]) for w in summary["jl_worse_than_b1"]}
    for replay_name, scenarios in summary["results"].items():
        for scenario, block in scenarios.items():
            for metric in sandbox_build.METRICS:
                if metric in sandbox_build.NEUTRAL:
                    continue
                diff = block["policies"]["JL"][metric]["diff_vs_b1_mean"]
                worse = diff < -1e-9 if metric in sandbox_build.HIGHER_IS_BETTER else diff > 1e-9
                assert ((replay_name, scenario, metric) in listed) == worse


def test_one_seed_reproduces(results) -> None:
    checks = json.loads((ROOT / sandbox_build.CHECKS).read_text(encoding="utf-8"))
    capacity = checks["capacities"]["secondary_2023"]["tight"]
    ctx = sandbox_build.load_context()
    rows = sandbox_build.run_seed(ctx, "secondary_2023", {"tight": capacity}, 0, ("B1", "JL"))
    committed = {
        r["policy"]: r
        for r in results
        if (r["replay"], r["scenario"], r["seed"]) == ("secondary_2023", "tight", "0")
    }
    for row in rows:
        for key, value in row.items():
            assert str(value) == committed[row["policy"]][key], (row["policy"], key)
