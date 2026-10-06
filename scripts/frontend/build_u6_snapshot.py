"""Build U6's saved snapshot from the same published CSV outputs served by the API."""

from __future__ import annotations

import csv
import json
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "frontend/src/data/u6Forecast.json"
NUMERIC = {
    "point",
    "lower_80",
    "upper_80",
    "lower_90",
    "upper_90",
    "capacity_trips",
    "actual",
    "error_pct",
    "forecast_bookings",
    "capacity_ratio",
    "months_ahead",
    "groundwater_m",
    "groundwater_wells",
}


def _rows(root: Path, name: str) -> list[dict]:
    with (root / "data/derived" / name).open(encoding="utf-8-sig", newline="") as handle:
        result = []
        for row in csv.DictReader(handle):
            result.append(
                {
                    key: None if value == "" else float(value) if key in NUMERIC else value
                    for key, value in row.items()
                }
            )
        return result


def build_snapshot(root: Path = ROOT, *, snapshot_date: str | None = None) -> dict:
    """Copy published rows exactly; fail if missing instead of substituting demo figures."""
    history_rows = _rows(root, "forecast_history.csv")
    city = sorted(
        (row for row in history_rows if row["level"] == "city"), key=lambda row: row["month"]
    )
    return {
        "snapshotDate": snapshot_date or date.today().isoformat(),
        "historyEnd": city[-1]["month"],
        "cityCoverage": json.loads(
            (root / "data/verification/forecast_refresh.json").read_text(encoding="utf-8")
        ).get("city_coverage", [])
        if (root / "data/verification/forecast_refresh.json").exists()
        else [],
        "history": [
            {"month": row["month"], "bookings": row["actual"], "basis": row["actual_basis"]}
            for row in city
        ],
        "forecastRows": _rows(root, "forecast_table.csv"),
        "historyRows": history_rows,
        "accuracyRows": _rows(root, "forecast_accuracy.csv"),
        "shortageRows": _rows(
            root,
            "shortage_outlook.csv"
            if (root / "data/derived/shortage_outlook.csv").exists()
            else "shortage_risk.csv",
        ),
        "notes": {
            "forecast": "Published model output; intervals use rolling-origin residuals.",
            "accuracy": "Retrospective rolling-origin estimates, not previously issued forecasts.",
            "history": "Section historical correspondence may be approximate; bases preserved.",
        },
    }


def main() -> None:
    payload = build_snapshot()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8"
    )
    print(f"Wrote published U6 output through {payload['historyEnd']} to {OUTPUT}")


if __name__ == "__main__":
    main()
