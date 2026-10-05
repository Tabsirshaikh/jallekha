"""Rolling-origin backtest and 12-month forecast table (F5, task T2).

Runs every available model on two datasets and writes:
- data/derived/forecast_backtest.csv: per model and origin (MAPE, WAPE), summaries on the
  origins all models share, split-conformal coverage, models not run, the selected model;
- data/derived/forecast_table.csv: section and city forecasts 12 months ahead with 80% / 90%
  section intervals;
- data/derived/forecast_capacity.csv only when --trips-per-day is given (no sourced value
  exists: OPEN, owner to confirm).

Datasets: S2 (data/raw/hmwssb_tankers, Jan 2022 - Feb 2024; the done-when baseline) and the
D1b portal files (data/raw/hmwssb_tankers_portal) up to Jan 2026, before the Feb/Mar 2026
section re-cut. Dec 2022 is missing in both and is never treated as zero.

Usage:
    python scripts/forecast/run_backtest.py [--out-dir data/derived] [--trips-per-day N]
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

from app.config.forecast import FORECAST_CONFIG
from app.services import forecast as fc

ROOT = Path(__file__).resolve().parents[2]
S2_DIR = ROOT / "data/raw/hmwssb_tankers"
PORTAL_DIR = ROOT / "data/raw/hmwssb_tankers_portal"

BACKTEST_COLUMNS = [
    "run",
    "row_type",
    "model",
    "origin",
    "months",
    "section_months",
    "city_mape",
    "city_mape_basis",
    "section_wape",
    "section_wape_basis",
    "interval",
    "coverage",
    "coverage_basis",
    "note",
]


def _label(month: fc.Month) -> str:
    return f"{month[0]}-{month[1]:02d}"


def _run(
    name: str, panel: fc.Panel
) -> tuple[list[dict[str, object]], dict[str, fc.Summary], list[fc.BacktestRow]]:
    rows: list[dict[str, object]] = []
    backtest = fc.backtest(panel)
    basis = f"DERIVED: rolling-origin backtest on {name} ({panel.column}), training before origin"
    for r in backtest:
        rows.append(
            {
                "run": name, "row_type": "origin", "model": r.model, "origin": _label(r.origin),
                "months": 1, "section_months": r.section_months,
                "city_mape": round(r.city_ape, 4), "city_mape_basis": basis,
                "section_wape": round(r.abs_error / r.actual_sum * 100, 4),
                "section_wape_basis": basis,
            }
        )  # fmt: skip
    common = fc.common_origins(backtest)
    summaries = fc.summarise(backtest, common)
    for model, s in sorted(summaries.items()):
        rows.append(
            {
                "run": name, "row_type": "summary_common_origins", "model": model,
                "origin": f"{_label(min(common))}..{_label(max(common))}", "months": s.origins,
                "section_months": s.section_months, "city_mape": round(s.city_mape, 4),
                "city_mape_basis": basis + "; origins shared by all models",
                "section_wape": round(s.section_wape, 4),
                "section_wape_basis": basis + "; origins shared by all models",
            }
        )  # fmt: skip
    for model, s in sorted(fc.summarise(backtest).items()):
        rows.append(
            {
                "run": name, "row_type": "summary_all_origins", "model": model, "months": s.origins,
                "section_months": s.section_months, "city_mape": round(s.city_mape, 4),
                "city_mape_basis": basis, "section_wape": round(s.section_wape, 4),
                "section_wape_basis": basis,
            }
        )  # fmt: skip
    for model in fc.MODELS:
        for c in fc.conformal_backtest(panel, model):
            rows.append(
                {
                    "run": name, "row_type": "coverage", "model": model,
                    "interval": c.level, "months": c.n_test_months,
                    "section_months": c.n_test_points,
                    "coverage": round(c.coverage, 4) if c.coverage is not None else None,
                    "coverage_basis": (
                        "DERIVED: split-conformal, first half of scored months calibrate, "
                        "section-scaled pooled residuals"
                        if c.status == "ok"
                        else "UNAVAILABLE: too few scored months"
                    ),
                    "note": c.reason or f"{c.n_calibration_months} calibration months",
                }
            )  # fmt: skip
    for model, why in fc.NOT_RUN.items():
        rows.append({"run": name, "row_type": "not_run", "model": model, "note": why})
    return rows, summaries, backtest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, default=ROOT / "data/derived")
    parser.add_argument("--trips-per-day", type=float, default=None)
    args = parser.parse_args(argv)
    cfg = FORECAST_CONFIG

    s2 = fc.load_panel(S2_DIR, cfg.baseline_column)
    portal = fc.load_panel(PORTAL_DIR, cfg.baseline_column, through=cfg.portal_through)
    rows_s2, summary_s2, _ = _run("s2_2022-01_2024-02", s2)
    portal_name = f"portal_2022-01_{_label(cfg.portal_through)}"
    rows_portal, summary_portal, backtest_portal = _run(portal_name, portal)
    # The rule is judged on the longest run (portal); S2 only checks the documented baseline.
    history = {o: fc.yoy_months(portal.until(o)) for o in {r.origin for r in backtest_portal}}
    selection = fc.select(backtest_portal, fc.yoy_months(portal), history)
    selected = selection.model
    rows = rows_s2 + rows_portal
    basis = "DERIVED: selection rule on the portal run (config model_selection_rule)"
    for t in selection.tests:
        rows.append(
            {
                "run": portal_name, "row_type": "selection_test", "model": t.model,
                "months": selection.origins, "city_mape": round(t.city_mape, 4),
                "city_mape_basis": basis, "section_wape": round(t.section_wape, 4),
                "section_wape_basis": basis,
                "note": f"seasonal naive {t.baseline_city_mape:.4f} / "
                f"{t.baseline_section_wape:.4f}; "
                f"HLN Diebold-Mariano {t.dm.statistic:.4f}, one-sided p {t.p_value:.4f} "
                f"(n {t.dm.n}); {'passes' if t.passed else 'does not pass'}",
            }
        )  # fmt: skip
    rows.append(
        {
            "run": portal_name, "row_type": "selected", "model": selected,
            "months": selection.origins, "note": selection.reason,
        }
    )  # fmt: skip
    changes = fc.section_changes(portal)
    for year, c in sorted(changes.items()):
        rows.append(
            {
                "run": "portal", "row_type": "section_changes", "origin": str(year),
                "note": f"{c['sections']} sections; {c['appeared']} appeared, "
                f"{c['disappeared']} disappeared vs the year before (no mapping applied)",
            }
        )  # fmt: skip

    args.out_dir.mkdir(parents=True, exist_ok=True)
    with (args.out_dir / "forecast_backtest.csv").open("w", encoding="utf-8", newline="") as h:
        writer = csv.DictWriter(h, fieldnames=BACKTEST_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    table = fc.forecast_table(
        portal, selected, cfg.horizon_months, basis_note=cfg.forecast_table_note
    )
    columns = list(dict.fromkeys(k for row in table for k in row))
    with (args.out_dir / "forecast_table.csv").open("w", encoding="utf-8", newline="") as h:
        writer = csv.DictWriter(h, fieldnames=columns)
        writer.writeheader()
        writer.writerows(table)

    if args.trips_per_day is not None:
        city = {
            tuple(int(x) for x in str(r["month"]).split("-")): float(r["point"])  # type: ignore[arg-type]
            for r in table
            if r["level"] == "city" and r["point"] is not None
        }
        plan = fc.capacity_plan(city, cfg.fleet_tankers_2026, args.trips_per_day)
        with (args.out_dir / "forecast_capacity.csv").open("w", encoding="utf-8", newline="") as h:
            writer = csv.writer(h)
            writer.writerow(["month", "trips_needed", "trips_needed_basis", "capacity_trips",
                             "capacity_basis", "shortfall_trips", "fleet_basis"])  # fmt: skip
            for p in plan:
                writer.writerow([_label(p.month), p.trips_needed, p.trips_needed_basis,
                                 p.capacity_trips, p.capacity_basis, p.shortfall_trips,
                                 p.fleet_basis])  # fmt: skip

    base = fc.baseline(s2)
    print(
        f"Baseline (S2): city MAPE {base.city_mape:.2f}% / section WAPE {base.section_wape:.2f}% "
        f"on {len(base.scored_months)} months (target {cfg.baseline_city_mape_pct}% / "
        f"{cfg.baseline_section_wape_pct}%)"
    )
    for run, summary in (("S2", summary_s2), ("portal", summary_portal)):
        for model, s in sorted(summary.items()):
            print(
                f"{run:6} {model:16} MAPE {s.city_mape:6.2f}  WAPE {s.section_wape:6.2f}  "
                f"({s.origins} origins)"
            )
    print(f"Selected: {selected}")
    if args.trips_per_day is None:
        print("Capacity plan not written: trips per tanker per day is OPEN (no sourced value).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
