"""Build U6's observed booking history and clearly marked illustrative fixtures."""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw" / "hmwssb_tankers_portal"
OUTPUT = ROOT / "frontend" / "src" / "data" / "u6Forecast.json"

# These values are illustrative only. T2/T8 do not yet produce forecast or shortage output.
FORECAST_FIXTURE = [
    {"month": "2026-10", "low80": 170000, "high80": 220000, "low90": 150000, "high90": 245000, "median": 195000},
    {"month": "2026-11", "low80": 176000, "high80": 232000, "low90": 151000, "high90": 258000, "median": 205000},
    {"month": "2026-12", "low80": 131000, "high80": 190000, "low90": 109000, "high90": 218000, "median": 162000},
]
DEMO_MONTHLY_CAPACITY = 180000


def main() -> None:
    totals: dict[str, dict[str, int]] = defaultdict(lambda: {"bookings": 0, "delivered": 0, "rows": 0})
    for path in sorted(RAW.glob("20??-??.csv")):
        with path.open(encoding="utf-8-sig", newline="") as source:
            for row in csv.DictReader(source):
                month = f"{int(row['year']):04d}-{int(row['month']):02d}"
                totals[month]["bookings"] += int(row["noofbookings"] or 0)
                totals[month]["delivered"] += int(row["delivered"] or 0)
                totals[month]["rows"] += 1

    months: list[str] = []
    year, month = 2022, 1
    while (year, month) <= (2026, 8):
        months.append(f"{year:04d}-{month:02d}")
        month += 1
        if month == 13:
            year, month = year + 1, 1
    history = []
    for key in months:
        total = totals.get(key)
        has_source = total is not None and total["rows"] > 0
        history.append(
            {
                "month": key,
                "bookings": total["bookings"] if has_source else None,
                "delivered": total["delivered"] if has_source else None,
                "reportedSections": total["rows"] if has_source else 0,
                "basis": "REAL" if has_source else "UNAVAILABLE",
            }
        )
    observed = [
        row
        for row in history
        if row["basis"] == "REAL" and row["bookings"] is not None
    ]
    latest = observed[-1]
    peak = max(observed, key=lambda row: row["bookings"])
    for item in FORECAST_FIXTURE:
        item["capacity"] = DEMO_MONTHLY_CAPACITY
        item["capacityBasis"] = "SIMULATION"
        item["basis"] = "SIMULATION"

    payload = {
        "snapshotDate": date.today().isoformat(),
        "historyStart": observed[0]["month"],
        "historyEnd": latest["month"],
        "history": history,
        "forecast": FORECAST_FIXTURE,
        "capacityBasis": "SIMULATION",
        "baseline": {
            "cityMapePct": 21.9,
            "sectionWapePct": 35.1,
            "basis": "DERIVED",
            "protocolStatus": "NOT_DOCUMENTED",
        },
        "summary": {
            "observedMonthCount": len(observed),
            "missingMonths": [row["month"] for row in history if row["basis"] == "UNAVAILABLE"],
            "latest": latest,
            "peak": peak,
        },
        "groundwater": {
            "basis": "UNAVAILABLE",
            "reason": "GHMC station coverage and extraction/licence are not confirmed.",
        },
        "notes": {
            "history": "Monthly city totals summed from HMWSSB section records; missing months remain null.",
            "forecast": "Illustrative UI fixture; no current T2 model, calibrated interval, or live API output.",
            "capacity": "Illustrative threshold only; trips per tanker per day and current operational capacity are unverified.",
            "accuracy": "Previously documented seasonal-naive backtest values; exact protocol is not documented in this repository.",
        },
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    print(f"Wrote {len(observed)} observed months through {latest['month']} to {OUTPUT}")


if __name__ == "__main__":
    main()
