"""T9 (F17): choose the confidence threshold on a degraded-signal replay (item 18). SIMULATION.

Usage:
    python scripts/trust/calibrate_confidence.py [--out PATH] [--max-days N] [--seeds N]

The A7 replay (scripts/sandbox/build_planner_replay.py, reading only committed files; A8's
files are never rebuilt) is run once on the data the system has (the "system" plan). For each
seed, services/confidence.degrade draws where that data is wrong (ASSUMED rates in config):
weakly placed sections really lie in a neighbouring ward, and true need differs from the
recorded need by more where the Census join is weaker. The replay is run again on the true
data (the "full-information" plan). A group-day matches when the group's served and waiting
counts are the same in both plans (groups as the system sees them).

For each candidate threshold the gate (T9Gate on the real files, exactly as the API uses it)
flags groups below it. The script reports, per seed: the share of unflagged group-days that
match, the share of groups flagged (the officers' load) and the share of damaged groups caught.
The threshold is the lowest one meeting the target share in every seed; if none does, or the
target is met with nothing flagged, nothing is chosen and the provisional threshold stays.

The earlier scenario (every group on the A3 fallback) could not tell thresholds apart
("not_separable"); it is replaced by this one.

Output: data/derived/confidence_calibration.csv (SIMULATION; every derived column has a
_basis). Confidences are rounded to 4 decimals, thresholds to 2.
"""

from __future__ import annotations

import argparse
import csv
import dataclasses
import importlib.util
import io
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.config.confidence import CONFIDENCE_CONFIG  # noqa: E402
from app.services import booking_groups, service_models  # noqa: E402
from app.services import confidence as cf  # noqa: E402

LABEL = "SIMULATION"
SCENARIO = "degraded_signals"
MATCH_BASIS = (
    "SIMULATION; A7 replay main_2025 tight seed 0; unflagged group-days with the same served "
    "and waiting counts in the system plan and the full-information plan of this error draw, "
    "over unflagged group-days"
)
FLAGGED_BASIS = "DERIVED; groups with T9 confidence below the threshold, over replay groups"
CAUGHT_BASIS = (
    "SIMULATION; damaged groups (a section wrongly placed in it, or need off by at least "
    "the configured share) with T9 confidence below the threshold, over damaged groups"
)
Run = list[tuple[Any, list[str], set[str]]]  # (day, pending booking ids, served booking ids)


def _replay_module() -> Any:
    path = ROOT / "scripts/sandbox/build_planner_replay.py"
    spec = importlib.util.spec_from_file_location("build_planner_replay", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _run(replay: Any, setup: Any, max_days: int | None, entitlement: Any = None) -> Run:
    out = []
    for day in replay.replay(setup, max_days=max_days, entitlement=entitlement):
        served = {s.booking_id for p in day.plan.stations.values() for s in p.served}
        out.append((day.day, [p.booking.booking_id for p in day.inputs.pending], served))
    return out


def _neighbours() -> dict[str, list[str]]:
    graph = json.loads((ROOT / CONFIDENCE_CONFIG.adjacency_path).read_text(encoding="utf-8"))
    out: dict[str, list[str]] = {}
    for edge in graph["edges"]:
        out.setdefault(edge["a"], []).append(edge["b"])
        out.setdefault(edge["b"], []).append(edge["a"])
    return out


def truth_run(replay: Any, setup: Any, degradation: cf.Degradation, max_days: int | None) -> Run:
    """The replay on the true data of one error draw."""
    moved = degradation.moved
    bookings = [
        dataclasses.replace(b, group=booking_groups.ward_group(moved[b.section]))
        if b.section in moved
        else b
        for b in setup.bookings
    ]
    needs = service_models.build_ward_needs(service_models.load_evidence(ROOT), [])
    ward_need = {n.ward_id: n.entitlement for n in needs if n.entitlement}
    fallback = replay.fallback_value(setup)
    base = dict(setup.ctx.entitlement)
    for ward in moved.values():
        base.setdefault(booking_groups.ward_group(ward), ward_need.get(ward) or fallback)
    entitlement = {g: v * degradation.need_factor.get(g, 1.0) for g, v in base.items()}
    return _run(replay, dataclasses.replace(setup, bookings=bookings), max_days, entitlement)


def compare(system: Run, truth: Run, group_of: dict[str, str]) -> list[cf.GroupDay]:
    days = []
    for (day, pending_s, served_s), (_, pending_t, served_t) in zip(system, truth, strict=True):
        ps = Counter(group_of[b] for b in pending_s)
        ss = Counter(group_of[b] for b in served_s)
        pt = Counter(group_of[b] for b in pending_t)
        st = Counter(group_of[b] for b in served_t)
        for group in sorted(set(ps) | set(pt)):
            same = (ss[group], ps[group] - ss[group]) == (st[group], pt[group] - st[group])
            days.append(cf.GroupDay(group, day, same))
    return days


def _fmt(value: float | None, decimals: int) -> str:
    return "" if value is None else f"{value:.{decimals}f}"


def build(max_days: int | None = None, seeds: int | None = None) -> tuple[bytes, str, float | None]:
    config = CONFIDENCE_CONFIG
    seeds = config.degraded_seeds if seeds is None else seeds
    replay = _replay_module()
    setup = replay.load(ROOT)
    tables = cf.SignalTables.from_files(ROOT)
    neighbours = _neighbours()
    group_of = {b.booking_id: b.group for b in setup.bookings}
    system = _run(replay, setup, max_days)
    replay_groups = sorted({group_of[b] for _, pending, _ in system for b in pending})
    gate = cf.T9Gate(tables)
    confidences = {g: a.confidence for g, a in gate.assess(replay_groups).items()}
    c, t = config.confidence_decimals, config.threshold_decimals
    results, damaged, rows = [], [], []
    for seed in range(seeds):
        groups = set(setup.ctx.entitlement) | {booking_groups.ward_group(w) for w in neighbours}
        degradation = cf.degrade(seed, tables, sorted(groups), neighbours, config)
        days = compare(system, truth_run(replay, setup, degradation, max_days), group_of)
        result = cf.calibrate(
            days, confidences, config.candidate_thresholds, config.target_match_share
        )
        errors = cf.error_groups(degradation, tables, config) & set(replay_groups)
        results.append(result)
        damaged.append(errors)
        for r in result.rows:
            caught = sum(1 for g in errors if confidences[g] < r.threshold)
            rows.append(
                {
                    "row_type": "threshold",
                    "scenario": SCENARIO,
                    "seed": seed,
                    "threshold": _fmt(r.threshold, t),
                    "group_days": r.group_days,
                    "unflagged_group_days": r.unflagged_group_days,
                    "matched_unflagged": r.matched_unflagged,
                    "match_share": _fmt(r.match_share, c),
                    "match_share_basis": MATCH_BASIS,
                    "groups": r.groups,
                    "flagged_groups": r.flagged_groups,
                    "flagged_share": _fmt(r.flagged_share, c),
                    "flagged_share_basis": FLAGGED_BASIS,
                    "damaged_groups": len(errors),
                    "caught_groups": caught,
                    "caught_share": _fmt(caught / len(errors) if errors else None, c),
                    "caught_share_basis": CAUGHT_BASIS,
                    "status": "meets_target"
                    if r.match_share is not None and r.match_share >= result.target - 1e-12
                    else "below_target",
                    "label": LABEL,
                }
            )
    status, chosen = cf.choose_across_seeds(results, config.target_match_share)
    selected = chosen if chosen is not None else config.provisional_threshold
    index = next(i for i, r in enumerate(results[0].rows) if abs(r.threshold - selected) < 1e-9)
    at = [res.rows[index] for res in results]
    shares = [r.match_share for r in at if r.match_share is not None]
    caught = sum(sum(1 for g in e if confidences[g] < selected) for e in damaged)
    total_damaged = sum(len(e) for e in damaged)
    rule = (
        f"lowest threshold with match share >= target {config.target_match_share:.2f} in every "
        f"one of {seeds} error draws (OPEN, owner to confirm); match share is the lowest draw"
        if chosen is not None
        else f"{status}: target {config.target_match_share:.2f} "
        + (
            "already met with nothing flagged in every draw"
            if status == "not_separable"
            else "not reached by any threshold in every draw"
        )
        + "; PROVISIONAL threshold kept (OPEN, owner to confirm)"
    )
    rows.append(
        {
            "row_type": "selection",
            "scenario": SCENARIO,
            "seed": "all",
            "threshold": _fmt(selected, t),
            "group_days": sum(r.group_days for r in at),
            "unflagged_group_days": sum(r.unflagged_group_days for r in at),
            "matched_unflagged": sum(r.matched_unflagged for r in at),
            "match_share": _fmt(min(shares) if shares else None, c),
            "match_share_basis": rule,
            "groups": at[0].groups,
            "flagged_groups": at[0].flagged_groups,
            "flagged_share": _fmt(at[0].flagged_share, c),
            "flagged_share_basis": FLAGGED_BASIS,
            "damaged_groups": total_damaged,
            "caught_groups": caught,
            "caught_share": _fmt(caught / total_damaged if total_damaged else None, c),
            "caught_share_basis": CAUGHT_BASIS + "; summed over draws",
            "status": status,
            "label": LABEL,
        }
    )
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode(), status, chosen


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", default=str(ROOT / CONFIDENCE_CONFIG.calibration_path))
    parser.add_argument("--max-days", type=int, default=None)
    parser.add_argument("--seeds", type=int, default=None)
    args = parser.parse_args(argv)
    content, status, chosen = build(args.max_days, args.seeds)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(content)
    print(f"confidence calibration ({LABEL}): {status}, chosen {chosen} -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
