"""T9 (F17): choose the confidence threshold on P2's A7 planner replay. SIMULATION.

Usage:
    python scripts/trust/calibrate_confidence.py [--out PATH] [--max-days N]

Runs the A7 replay (scripts/sandbox/build_planner_replay.py, reading only committed files;
A8's files are never rebuilt) twice, day by day:
- full information: the replay as committed (Census 2011 need per ward, A3 fallback otherwise);
- degraded: the only degraded scenario P2's replay supports, every group on the A3 fallback
  entitlement (the median).
A group-day matches when the group's served and waiting counts are the same in both plans.
For each candidate threshold, groups with confidence below it are flagged (T9Gate on the real
files); the script reports the share of unflagged group-days that match, and the share of
groups flagged, and chooses the lowest threshold meeting the target share (config). If no
threshold meets it, or it is already met with nothing flagged (the replay cannot tell
thresholds apart), nothing is chosen and the provisional threshold stays.

Output: data/derived/confidence_calibration.csv (SIMULATION; every derived column has a
_basis). Confidences are rounded to 4 decimals, thresholds to 2.
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import io
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.config.confidence import CONFIDENCE_CONFIG  # noqa: E402
from app.services import confidence as cf  # noqa: E402

LABEL = "SIMULATION"
MATCH_BASIS = (
    "SIMULATION; A7 replay main_2025 tight seed 0; unflagged group-days with the same served "
    "and waiting counts under full information and with every group on the A3 fallback "
    "entitlement, over unflagged group-days"
)
FLAGGED_BASIS = "DERIVED; groups with T9 confidence below the threshold, over replay groups"


def _replay_module() -> Any:
    path = ROOT / "scripts/sandbox/build_planner_replay.py"
    spec = importlib.util.spec_from_file_location("build_planner_replay", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _counts(result: Any) -> tuple[Counter[str], Counter[str]]:
    pending = Counter(p.booking.group for p in result.inputs.pending)
    served = Counter(s.group for p in result.plan.stations.values() for s in p.served)
    return pending, served


def group_days(max_days: int | None = None) -> list[cf.GroupDay]:
    replay = _replay_module()
    setup = replay.load(ROOT)
    median = replay.fallback_value(setup)
    degraded = replay.replay(
        setup,
        max_days=max_days,
        entitlement=dict.fromkeys(setup.ctx.entitlement, median),
        fallback_groups=frozenset(setup.ctx.entitlement),
    )
    days = []
    for full_day, low_day in zip(replay.replay(setup, max_days=max_days), degraded, strict=True):
        pending_f, served_f = _counts(full_day)
        pending_d, served_d = _counts(low_day)
        for group in sorted(set(pending_f) | set(pending_d)):
            same = (served_f[group], pending_f[group] - served_f[group]) == (
                served_d[group],
                pending_d[group] - served_d[group],
            )
            days.append(cf.GroupDay(group, full_day.day, same))
    return days


def _fmt(value: float | None, decimals: int) -> str:
    return "" if value is None else f"{value:.{decimals}f}"


def build(max_days: int | None = None) -> tuple[bytes, cf.Calibration, dict[str, float]]:
    config = CONFIDENCE_CONFIG
    days = group_days(max_days)
    gate = cf.T9Gate(cf.SignalTables.from_files(ROOT))
    groups = sorted({d.group for d in days})
    confidences = {g: a.confidence for g, a in gate.assess(groups).items()}
    result = cf.calibrate(days, confidences, config.candidate_thresholds, config.target_match_share)
    c, t = config.confidence_decimals, config.threshold_decimals
    rows: list[dict[str, Any]] = []
    for r in result.rows:
        rows.append(
            {
                "row_type": "threshold",
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
                "status": "meets_target"
                if r.match_share is not None and r.match_share >= result.target - 1e-12
                else "below_target",
                "label": LABEL,
            }
        )
    chosen = result.chosen
    selected = chosen if chosen is not None else config.provisional_threshold
    row = next(r for r in result.rows if abs(r.threshold - selected) < 1e-9)
    rows.append(
        {
            "row_type": "selection",
            "threshold": _fmt(selected, t),
            "group_days": row.group_days,
            "unflagged_group_days": row.unflagged_group_days,
            "matched_unflagged": row.matched_unflagged,
            "match_share": _fmt(row.match_share, c),
            "match_share_basis": (
                f"lowest threshold with match share >= target {config.target_match_share:.2f} "
                "(OPEN, owner to confirm)"
                if chosen is not None
                else f"{result.status}: target {config.target_match_share:.2f} "
                + (
                    "already met with nothing flagged, so the replay cannot tell thresholds apart"
                    if result.status == "not_separable"
                    else "not reached by any threshold"
                )
                + "; PROVISIONAL threshold kept (OPEN, owner to confirm)"
            ),
            "groups": row.groups,
            "flagged_groups": row.flagged_groups,
            "flagged_share": _fmt(row.flagged_share, c),
            "flagged_share_basis": FLAGGED_BASIS,
            "status": result.status,
            "label": LABEL,
        }
    )
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode(), result, confidences


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", default=str(ROOT / CONFIDENCE_CONFIG.calibration_path))
    parser.add_argument("--max-days", type=int, default=None)
    args = parser.parse_args(argv)
    content, result, _ = build(args.max_days)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(content)
    print(f"confidence calibration ({LABEL}): {result.status}, chosen {result.chosen} -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
