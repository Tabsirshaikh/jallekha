"""Published forecasts, shortage warnings and the fallback must use current capacities."""

import calendar
import csv
import importlib.util
import json
import shutil
from pathlib import Path

import pytest

from app.services import shortage

ROOT = Path(__file__).resolve().parents[2]


def load_script():
    spec = importlib.util.spec_from_file_location(
        "capacity_refresh_test", ROOT / "scripts/forecast/refresh_forecast.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def rows(root, name):
    with (root / "data/derived" / name).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_published_section_capacities_match_current_station_assignments():
    matches = {r["section"]: r["old_section"] for r in rows(ROOT, "forecast_section_crosswalk.csv")}
    capacities = shortage.load_capacity(ROOT)
    for row in rows(ROOT, "forecast_table.csv"):
        if row["level"] != "section":
            continue
        cap = capacities.get(matches[row["section"]])
        if cap is None:
            assert row["capacity_trips"] == ""
        else:
            days = calendar.monthrange(*map(int, row["month"].split("-")))[1]
            assert float(row["capacity_trips"]) == pytest.approx(cap.trips_per_day * days), row[
                "section"
            ]


def test_capacity_only_refresh_preserves_predictions_and_updates_all_outputs(tmp_path, monkeypatch):
    derived = tmp_path / "data/derived"
    derived.mkdir(parents=True)
    for name in (
        "forecast_table.csv",
        "forecast_capacity.csv",
        "forecast_section_crosswalk.csv",
        "forecast_history.csv",
        "forecast_accuracy.csv",
        "reservoir_monthly.csv",
        "shortage_risk.csv",
        "groundwater/section_anomaly.csv",
        "sandbox/section_points.csv",
    ):
        target = derived / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / "data/derived" / name, target)
    checks = tmp_path / "data/verification/sandbox_checks.json"
    checks.parent.mkdir(parents=True)
    shutil.copyfile(ROOT / "data/verification/sandbox_checks.json", checks)
    before = rows(tmp_path, "forecast_table.csv")
    module = load_script()
    monkeypatch.setattr(module, "ROOT", tmp_path)
    monkeypatch.setattr(module.fc, "load_panel", lambda *a, **kw: pytest.fail("Must not retrain"))
    monkeypatch.setattr(module.subprocess, "run", lambda *a, **kw: pytest.fail("Must not fetch"))
    assert module.main(["--capacity-only"]) == 0
    after = rows(tmp_path, "forecast_table.csv")
    ignored = {"capacity_trips", "capacity_trips_basis"}
    assert [{k: v for k, v in r.items() if k not in ignored} for r in before] == [
        {k: v for k, v in r.items() if k not in ignored} for r in after
    ]
    snapshot = json.loads(
        (tmp_path / "frontend/src/data/u6Forecast.json").read_text(encoding="utf-8")
    )
    table = {(r["section"], r["month"]): r for r in after if r["level"] == "section"}
    for row in rows(tmp_path, "shortage_risk.csv"):
        forecast = table[row["section"], row["month"]]
        if row["forecast_bookings"] and forecast["capacity_trips"]:
            assert float(row["capacity_trips"]) == pytest.approx(
                float(forecast["capacity_trips"]), abs=0.05
            )
    assert len(snapshot["forecastRows"]) == len(after)
    for source, saved in zip(after, snapshot["forecastRows"], strict=True):
        assert saved["capacity_trips"] == (
            float(source["capacity_trips"]) if source["capacity_trips"] else None
        )
    for source, saved in zip(
        rows(tmp_path, "shortage_risk.csv"), snapshot["shortageRows"], strict=True
    ):
        assert saved["capacity_trips"] == (
            float(source["capacity_trips"]) if source["capacity_trips"] else None
        )
    paths = [
        derived / n for n in ("forecast_table.csv", "forecast_capacity.csv", "shortage_risk.csv")
    ]
    first = [p.read_bytes() for p in paths]
    assert module.main(["--capacity-only"]) == 0
    assert first == [p.read_bytes() for p in paths]
