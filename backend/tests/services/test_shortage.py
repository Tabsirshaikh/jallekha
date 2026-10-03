"""T8 shortage early warning (F6): T2 forecast vs A8 capacity, risk rules, reasons, basis."""

from __future__ import annotations

import csv
import importlib.util
import json
import sys
from pathlib import Path

import pytest

from app.config.forecast import SHORTAGE_CONFIG
from app.config.sandbox import SANDBOX_CONFIG
from app.services import shortage as sh

REPO = Path(__file__).resolve().parents[3]


def _row(section: str, month: str, point: float, upper_80: float | None) -> dict[str, str]:
    return {
        "level": "section",
        "section": section,
        "month": month,
        "model": "seasonal_naive",
        "point": str(point),
        "point_basis": "DERIVED: seasonal_naive",
        "upper_80": "" if upper_80 is None else str(upper_80),
        "upper_80_basis": "DERIVED: split-conformal",
    }


# --- risk rules ----------------------------------------------------------------------------


def test_risk_threshold_boundaries() -> None:
    high, medium = SHORTAGE_CONFIG.risk_high_ratio, SHORTAGE_CONFIG.risk_medium_ratio
    cap = 1000.0
    assert sh.risk_level(high * cap, None, cap) == "high"  # at the high ratio: high
    assert sh.risk_level(high * cap - 0.01, None, cap) == "medium"
    assert sh.risk_level(medium * cap, None, cap) == "medium"  # at the medium ratio: medium
    assert sh.risk_level(medium * cap - 0.01, None, cap) == "low"
    # The upper 80% bound reaching capacity makes a low point medium.
    assert sh.risk_level(0.5 * cap, cap, cap) == "medium"
    assert sh.risk_level(0.5 * cap, cap - 0.01, cap) == "low"
    assert sh.risk_level(10.0, None, None) == "unknown"
    assert sh.risk_level(10.0, None, 0.0) == "unknown"


def test_rules_live_in_config_with_sources() -> None:
    assert SHORTAGE_CONFIG.months_ahead == (1, 2, 3)
    assert SHORTAGE_CONFIG.reservoirs_enabled is False
    assert "unavailable" in SHORTAGE_CONFIG.groundwater_note


# --- capacity from A8 --------------------------------------------------------------------------


def test_capacity_reuses_a8_fleet_split() -> None:
    cap = sh.load_capacity(REPO)
    checks = json.loads((REPO / SHORTAGE_CONFIG.a8_checks_path).read_text(encoding="utf-8"))
    stations = checks["capacities"][SHORTAGE_CONFIG.a8_replay][SHORTAGE_CONFIG.a8_scenario]
    with (REPO / SHORTAGE_CONFIG.a8_sections_path).open(encoding="utf-8") as handle:
        points = list(csv.DictReader(handle))
    # Every station's daily trips are shared out exactly over its home sections.
    for station, trips in stations.items():
        home = [p["section"] for p in points if p["home_station"] == station]
        if home:
            assert sum(cap[s].trips_per_day for s in home) == pytest.approx(trips)
    # The A8 fleet total is REAL fleet x DERIVED trips per tanker.
    total = SANDBOX_CONFIG.fleet_tankers * SANDBOX_CONFIG.trips_per_tanker_day
    assert sum(stations.values()) == pytest.approx(total, abs=len(stations))
    sample = next(iter(cap.values()))
    assert "ASSUMED" in sample.basis
    # Sections without an A8 point have no capacity (never 0).
    no_point = {p["section"] for p in points if not p["home_station"]}
    assert no_point and not (no_point & set(cap))


# --- reasons -----------------------------------------------------------------------------------


def test_reason_is_built_from_the_numbers_and_says_groundwater_unavailable() -> None:
    cap = {"S1": sh.SectionCapacity("S1", 10.0, "ASSUMED: test")}
    rows = sh.risk_list([_row("S1", "2026-02", 290.0, 330.0)], cap, origin="2026-01")
    (r,) = rows
    assert r.risk == "high" and r.capacity_trips == 280.0  # 10 trips x 28 days
    assert "290" in r.reason and "330" in r.reason and "280" in r.reason
    assert "104%" in r.reason
    assert "groundwater data unavailable" in r.reason
    assert r.groundwater_status == "UNAVAILABLE"


def test_reservoir_flag_off_and_on_without_data() -> None:
    cap = {"S1": sh.SectionCapacity("S1", 10.0, "ASSUMED: test")}
    (r,) = sh.risk_list([_row("S1", "2026-02", 10.0, 20.0)], cap, origin="2026-01")
    assert r.reservoir_status == "NOT_USED" and "reservoir" not in r.reason.lower()
    with pytest.raises(ValueError, match="reservoir"):
        sh.risk_list(
            [_row("S1", "2026-02", 10.0, 20.0)],
            cap,
            origin="2026-01",
            reservoirs_enabled=True,
        )


def test_only_one_to_three_months_ahead_and_unknown_capacity() -> None:
    cap = {"S1": sh.SectionCapacity("S1", 10.0, "ASSUMED: test")}
    rows = [_row("S1", m, 10.0, 20.0) for m in ("2026-02", "2026-03", "2026-04", "2026-05")]
    rows.append(_row("S9", "2026-02", 10.0, 20.0))
    out = sh.risk_list(rows, cap, origin="2026-01")
    assert [(r.section, r.months_ahead) for r in out] == [
        ("S1", 1),
        ("S1", 2),
        ("S1", 3),
        ("S9", 1),
    ]
    unknown = out[-1]
    assert unknown.risk == "unknown" and unknown.capacity_trips is None
    assert "capacity unavailable" in unknown.reason


# --- done-when on the real files ----------------------------------------------------------------


def _script():  # type: ignore[no-untyped-def]
    spec = importlib.util.spec_from_file_location(
        "run_shortage", REPO / "scripts/forecast/run_shortage.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_risk_list_one_to_three_months_ahead_with_reasons(tmp_path: Path) -> None:
    out = tmp_path / "shortage.csv"
    assert _script().main(["--out", str(out)]) == 0
    with out.open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    with (REPO / SHORTAGE_CONFIG.forecast_table_path).open(encoding="utf-8") as handle:
        forecast = list(csv.DictReader(handle))
    # Only sections present in the forecast for the target months appear in the risk list.
    first = min(r["month"] for r in forecast)
    y, m = (int(x) for x in first.split("-"))
    from app.services.shortage import _add_months  # noqa: PLC0415

    origin = f"{y - (m == 1):04d}-{(m - 2) % 12 + 1:02d}"
    wanted = {_add_months(origin, k) for k in SHORTAGE_CONFIG.months_ahead}
    # T2 forecasts a section only where it had a value a year earlier, so the expected rows are
    # exactly the forecast's section-months in the three target months (read from the table).
    expected = {
        (r["section"], r["month"])
        for r in forecast
        if r["level"] == "section" and r["month"] in wanted
    }
    assert expected
    assert {r["months_ahead"] for r in rows} == {"1", "2", "3"}
    assert {(r["section"], r["month"]) for r in rows} == expected
    assert len(rows) == len(expected)
    for r in rows:
        assert r["risk"] in ("low", "medium", "high", "unknown")
        assert r["reason"] and "groundwater data unavailable" in r["reason"]
        if r["risk"] != "unknown":
            formatted = f"{float(r['forecast_bookings']):,.0f}"
            assert r["forecast_bookings"] in r["reason"] or formatted in r["reason"]
        assert r["label"] and SHORTAGE_CONFIG.section_label in r["section_basis"]
    # Every derived column has a _basis column.
    derived = {
        "forecast_bookings",
        "upper_80",
        "capacity_trips",
        "capacity_ratio",
        "risk",
        "reason",
        "groundwater_status",
        "reservoir_status",
        "section",
    }
    assert all(f"{c}_basis" in rows[0] for c in derived)


def test_committed_risk_list_reproduces(tmp_path: Path) -> None:
    out = tmp_path / "shortage.csv"
    assert _script().main(["--out", str(out)]) == 0
    assert out.read_bytes() == (REPO / SHORTAGE_CONFIG.output_path).read_bytes()
