"""T8 (F6): shortage risk list 1-3 months ahead from T2's forecast table and A8's capacity.

Usage:
    python scripts/forecast/run_shortage.py [--out PATH]

Reads data/derived/forecast_table.csv (T2) and A8's committed capacity files; writes
data/derived/shortage_risk.csv. Every derived column has a _basis column. Groundwater (D7):
each section's anomaly at the forecast origin (data/derived/groundwater/section_anomaly.csv) is
in the reason and its own column; it does not change the risk. Reservoirs are off.
"""

from __future__ import annotations

import argparse
import csv
import io
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.config.forecast import FORECAST_CONFIG, SHORTAGE_CONFIG  # noqa: E402
from app.services import shortage  # noqa: E402

LABEL = "DERIVED forecast vs ASSUMED capacity"


def _fmt(value: float | None, decimals: int = 2) -> str:
    return "" if value is None else f"{value:.{decimals}f}"


def build() -> bytes:
    # The refreshed contract retains unmatched rows with null forecasts and unknown risk.
    # Share the pure builder rather than reapplying the old section names/capacity split.
    import importlib.util

    crosswalk = ROOT / "data/derived/forecast_section_crosswalk.csv"
    if crosswalk.exists():
        spec = importlib.util.spec_from_file_location(
            "refresh_forecast", ROOT / "scripts/forecast/refresh_forecast.py"
        )
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with (ROOT / SHORTAGE_CONFIG.forecast_table_path).open(
            encoding="utf-8", newline=""
        ) as handle:
            table = [
                {k: None if v == "" else v for k, v in r.items()} for r in csv.DictReader(handle)
            ]
        for row in table:
            for key in ("point", "lower_80", "upper_80", "lower_90", "upper_90", "capacity_trips"):
                if row.get(key) is not None:
                    row[key] = float(row[key])
        matches = list(csv.DictReader(crosswalk.open(encoding="utf-8", newline="")))
        reservoir_path = ROOT / "data/derived/reservoir_monthly.csv"
        reservoirs = (
            list(csv.DictReader(reservoir_path.open(encoding="utf-8", newline="")))
            if reservoir_path.exists()
            else []
        )
        for row in reservoirs:
            row["storage_share"] = float(row["storage_share"])
        rows = module.build_shortage(table, matches, reservoirs)
        stream = io.StringIO(newline="")
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
        return stream.getvalue().encode()
    cfg = SHORTAGE_CONFIG
    with (ROOT / cfg.forecast_table_path).open(encoding="utf-8", newline="") as handle:
        forecast = list(csv.DictReader(handle))
    first = min(r["month"] for r in forecast)
    y, m = (int(x) for x in first.split("-"))
    origin = f"{y - (m == 1):04d}-{(m - 2) % 12 + 1:02d}"
    groundwater = shortage.load_groundwater(ROOT / cfg.groundwater_path, origin)
    rows = shortage.risk_list(
        forecast, shortage.load_capacity(ROOT), origin, groundwater=groundwater or None
    )
    section_basis = (
        f"REAL HMWSSB section; {cfg.section_label}: {FORECAST_CONFIG.forecast_table_note}"
    )
    out = []
    for r in rows:
        out.append(
            {
                "section": r.section,
                "section_basis": section_basis,
                "month": r.month,
                "months_ahead": r.months_ahead,
                "forecast_bookings": _fmt(r.forecast_bookings, 1),
                "forecast_bookings_basis": r.forecast_basis,
                "upper_80": _fmt(r.upper_80, 1),
                "upper_80_basis": r.upper_80_basis,
                "capacity_trips": _fmt(r.capacity_trips, 1),
                "capacity_trips_basis": r.capacity_basis,
                "capacity_ratio": _fmt(r.capacity_ratio, 4),
                "capacity_ratio_basis": (
                    "DERIVED: forecast / capacity"
                    if r.capacity_ratio is not None
                    else "UNAVAILABLE"
                ),
                "risk": r.risk,
                "risk_basis": (
                    f"DERIVED: config rules (high >= {cfg.risk_high_ratio:g} x capacity; medium >= "
                    f"{cfg.risk_medium_ratio:g} x capacity or upper 80% >= capacity; ASSUMED, OPEN)"
                ),
                "reason": r.reason,
                "reason_basis": "DERIVED: built from the numbers in this row",
                "groundwater_status": r.groundwater_status,
                "groundwater_status_basis": (
                    "DERIVED: median anomaly of TGGWD wells near the section (REAL levels), "
                    "latest month at or before the forecast origin"
                    if r.groundwater_status == "DERIVED"
                    else "UNAVAILABLE: see the reason"
                ),
                "groundwater_m": _fmt(r.groundwater_m, 2),
                "groundwater_m_basis": (
                    "DERIVED: metres deeper (+) or shallower (-) than the same month in earlier "
                    "years, median of nearby wells"
                    if r.groundwater_m is not None
                    else "UNAVAILABLE"
                ),
                "reservoir_status": r.reservoir_status,
                "reservoir_status_basis": "flag off: reservoirs only if Q2 is approved",
                "label": LABEL,
            }
        )
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=list(out[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(out)
    return stream.getvalue().encode()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", default=str(ROOT / SHORTAGE_CONFIG.output_path))
    args = parser.parse_args(argv)
    content = build()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(content)
    print(f"shortage risk list -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
