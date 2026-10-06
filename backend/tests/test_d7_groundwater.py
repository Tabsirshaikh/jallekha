"""D7: groundwater-level anomaly per well and per HMWSSB section (item 17)."""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "groundwater", ROOT / "scripts/forecast/build_groundwater.py"
)
gw = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = gw
spec.loader.exec_module(gw)


def _row(month, depth, lat="17.4000", lon="78.4000", village="V", district="Hyderabad"):
    return {"source_month": month, "district": district, "mandal": "M", "village": village,
            "lat": lat, "lon": lon, "date": f"{month}-01", "depth_m_bgl": str(depth)}  # fmt: skip


def test_swapped_coordinates_are_fixed_and_points_outside_the_region_dropped() -> None:
    assert gw.position({"lat": "78.4", "lon": "17.4"}) == (17.4, 78.4)
    assert gw.position({"lat": "17.4", "lon": "78.4"}) == (17.4, 78.4)
    assert gw.position({"lat": "27.4", "lon": "78.4"}) is None  # outside the region
    assert gw.position({"lat": "", "lon": "78.4"}) is None


def test_a_well_is_its_village_and_rounded_position() -> None:
    a = gw.well_id(_row("2023-01", 5, lat="17.40012", lon="78.40044"))
    b = gw.well_id(_row("2024-01", 5, lat="78.40031", lon="17.40021"))  # swapped, same spot
    c = gw.well_id(_row("2024-01", 5, lat="17.5000"))  # same village name, another well
    assert a == b != c


def test_anomaly_is_depth_minus_the_same_month_in_earlier_years() -> None:
    rows = [_row("2021-05", 10), _row("2022-05", 12), _row("2023-05", 14), _row("2023-06", 9),
            _row("2024-05", "N/A")]  # fmt: skip
    anomalies = gw.well_anomalies(rows)
    well = gw.well_id(rows[0])
    # 2023-05: 14 - mean(10, 12) = 3 (two earlier years); 2022-05 has only one: no anomaly.
    assert anomalies[(well, (2023, 5))] == pytest.approx(3.0)
    assert (well, (2022, 5)) not in anomalies
    assert (well, (2023, 6)) not in anomalies  # no earlier June
    assert (well, (2024, 5)) not in anomalies  # N/A is missing, not zero


def test_section_takes_the_median_of_nearby_wells_or_says_why_not() -> None:
    wells = {"w1": (17.400, 78.400), "w2": (17.405, 78.405), "w3": (17.410, 78.400),
             "far": (17.600, 78.600)}  # fmt: skip
    anomalies = {("w1", (2025, 1)): 1.0, ("w2", (2025, 1)): 3.0, ("w3", (2025, 1)): 2.0,
                 ("far", (2025, 1)): 9.0, ("w1", (2025, 2)): 1.0}  # fmt: skip
    near = gw.section_anomaly((17.401, 78.401), (2025, 1), wells, anomalies)
    assert near.value == pytest.approx(2.0) and near.wells == 3
    one = gw.section_anomaly((17.401, 78.401), (2025, 2), wells, anomalies)
    assert one.value is None and "1 well" in one.reason
    assert gw.section_anomaly(None, (2025, 1), wells, anomalies).value is None


def test_committed_groundwater_is_reproducible() -> None:
    built = gw.build()
    for path, content in built.items():
        assert (ROOT / path).read_bytes() == content, path
    checks = json.loads(built[gw.CHECKS])
    assert checks["sections_with_value_at_latest_month"] > 0


def test_the_shortage_reason_quotes_the_radius_the_build_uses() -> None:
    from app.config.forecast import SHORTAGE_CONFIG

    assert SHORTAGE_CONFIG.groundwater_radius_km == gw.RADIUS_KM
