"""Saved U6 output must reproduce published outputs, never illustrative demand."""

import csv
import importlib.util
from pathlib import Path


def test_snapshot_uses_published_numbers_and_preserves_missing_forecasts(tmp_path):
    script = Path(__file__).resolve().parents[2] / "scripts/frontend/build_u6_snapshot.py"
    spec = importlib.util.spec_from_file_location("u6_snapshot", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    derived = tmp_path / "data/derived"
    derived.mkdir(parents=True)
    rows = {
        "forecast_table.csv": [
            {
                "level": "city",
                "section": "",
                "month": "2026-09",
                "point": 200,
                "lower_80": 100,
                "upper_80": 300,
                "point_basis": "DERIVED",
            },
            {
                "level": "section",
                "section": "NEW",
                "month": "2026-09",
                "point": "",
                "lower_80": "",
                "upper_80": "",
                "point_basis": "UNAVAILABLE",
            },
        ],
        "forecast_history.csv": [
            {
                "level": "city",
                "section": "",
                "month": "2026-08",
                "actual": 250,
                "actual_basis": "REAL",
            }
        ],
        "forecast_accuracy.csv": [
            {
                "level": "city",
                "section": "",
                "month": "2026-08",
                "point": 200,
                "actual": 250,
                "error_pct": -20,
            }
        ],
        "shortage_risk.csv": [
            {"section": "NEW", "month": "2026-09", "risk": "unknown", "capacity_trips": ""}
        ],
    }
    for name, values in rows.items():
        with (derived / name).open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(values[0]))
            writer.writeheader()
            writer.writerows(values)
    result = module.build_snapshot(tmp_path, snapshot_date="2026-10-06")
    assert result["forecastRows"][0]["point"] == 200
    assert result["forecastRows"][1]["point"] is None
    assert result["forecastRows"][0]["section"] is None
    assert result["historyEnd"] == "2026-08"
    assert result["accuracyRows"][0]["error_pct"] == -20
    assert result["shortageRows"][0]["capacity_trips"] is None
    assert "forecast" not in result
