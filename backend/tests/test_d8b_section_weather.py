"""D8b: station weather per mandal, given to each HMWSSB section (research follow-up B)."""

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "section_weather", ROOT / "scripts/forecast/build_section_weather.py"
)
sw = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = sw  # dataclasses look their module up
spec.loader.exec_module(sw)


def _day(mandal, day, rain, tmax, station="", district="Hyderabad"):
    return {"district": district, "mandal": mandal, "station": station, "date": day,
            "rain_mm": str(rain), "tmin_c": "", "tmax_c": str(tmax)}  # fmt: skip


def test_mandal_month_averages_stations_per_day_then_the_month() -> None:
    days = [_day("A", f"2023-02-{d:02d}", 1.0, 30.0) for d in range(1, 29)]
    # A second station on one day: that day's values are the station mean.
    days.append(_day("A", "2023-02-01", 3.0, 34.0, station="s2"))
    month = sw.mandal_monthly(days)[("Hyderabad", "A", (2023, 2))]
    assert month.days == 28
    assert month.rain_total == pytest.approx(1.0 * 27 + 2.0)
    assert month.tmax_mean == pytest.approx((30.0 * 27 + 32.0) / 28)


def test_a_month_with_too_few_days_is_missing_and_rain_is_scaled_to_the_month() -> None:
    sparse = [_day("A", f"2023-03-{d:02d}", 2.0, 30.0) for d in range(1, 20)]  # 19 of 31
    assert ("Hyderabad", "A", (2023, 3)) not in sw.mandal_monthly(sparse)
    most = [_day("A", f"2023-03-{d:02d}", 2.0, 30.0) for d in range(1, 26)]  # 25 of 31
    month = sw.mandal_monthly(most)[("Hyderabad", "A", (2023, 3))]
    assert month.rain_total == pytest.approx(2.0 * 25 * 31 / 25)


def test_blank_or_unparsed_values_do_not_count() -> None:
    days = [_day("A", f"2023-02-{d:02d}", 1.0, 30.0) for d in range(1, 29)]
    days[0]["tmax_c"] = ""
    days[1]["date"] = ""
    month = sw.mandal_monthly(days)[("Hyderabad", "A", (2023, 2))]
    assert month.days == 26  # days with both values: the undated row and the blank one drop out


def test_sections_take_the_nearest_mandal_and_fall_back_with_a_label() -> None:
    m = sw.MonthWeather
    mandals = {
        ("Hyderabad", "A", (2023, 2)): m(30.0, 10.0, 28),
        ("Hyderabad", "B", (2023, 2)): m(32.0, 20.0, 28),
        ("Hyderabad", "B", (2023, 3)): m(35.0, 0.0, 31),
    }
    city = {(2023, 2): m(31.0, 12.0, 28), (2023, 3): m(34.0, 1.0, 31), (2023, 4): m(36.0, 0.0, 30)}
    points = {("Hyderabad", "A"): (17.40, 78.40), ("Hyderabad", "B"): (17.40, 78.50)}
    sections = {"NEAR_A": (17.40, 78.41), "NOWHERE": None}
    table = sw.section_table(sections, points, mandals, city)
    assert table["NEAR_A"][(2023, 2)] == (m(30.0, 10.0, 28), "MANDAL")
    # A missing in March: the district mean of the mandals that have it (B only).
    assert table["NEAR_A"][(2023, 3)] == (m(35.0, 0.0, 31), "DISTRICT")
    assert table["NEAR_A"][(2023, 4)] == (city[(2023, 4)], "CITY")
    assert all(src == "CITY" for _, src in table["NOWHERE"].values())


def test_nearest_mandal_is_by_distance() -> None:
    points = {("Hyderabad", "A"): (17.40, 78.40), ("Rangareddy", "C"): (17.30, 78.30)}
    assert sw.nearest((17.31, 78.31), points)[0] == ("Rangareddy", "C")


def test_spelling_variants_join_one_mandal_and_numbers_are_dropped() -> None:
    assert sw.canonical("Hyderabad", "Maredpally") == sw.canonical("Hyderabad", "Marredpally")
    assert sw.canonical("Medchal-Malkajgiri", "Dundigal_Gandimaisamma") == sw.canonical(
        "Medchal-Malkajgiri", "Dundigal Gandimaisamma"
    )
    assert sw.canonical("Rangareddy", "Keshampeta") == sw.canonical("Rangareddy", "Keshampet")
    assert sw.canonical("Sangareddy", "28") is None
    assert sw.canonical("Hyderabad", "Amberpet") == "Amberpet"
    # The aliases are applied before days are averaged, so one series results.
    days = [_day("Marredpally", f"2019-02-{d:02d}", 0.0, 30.0) for d in range(1, 15)]
    days += [_day("Maredpally", f"2019-02-{d:02d}", 0.0, 32.0) for d in range(15, 29)]
    months = sw.mandal_monthly(days)
    assert list(months) == [("Hyderabad", "Marredpally", (2019, 2))]


def test_committed_section_weather_is_reproducible() -> None:
    built = sw.build()
    for path, content in built.items():
        assert (ROOT / path).read_bytes() == content, path
    checks = __import__("json").loads(built[sw.CHECKS])
    assert checks["sections_with_point"] >= 170
    assert checks["section_month_sources"]["MANDAL"] > checks["section_month_sources"]["CITY"]
