import math

import pytest

from app.services import forecast as fc
from app.services import forecast_refresh as refresh


def test_new_recut_alias_keeps_real_count_instead_of_inventing_zero():
    assert refresh.normal_name("ADIKMET (NEW)") == "ADIKMET"
    panel = fc.Panel(
        "noofbookings",
        {(2026, 5): {"ADIKMET (NEW)": 379, "ADIKMET (OLD)": 2}, (2026, 6): {"UNRELATED": 5}},
    )
    matched = refresh.matched_panel(panel, [{"section": "ADIKMET", "old_section": "ADIKMET"}])
    assert matched.values[(2026, 5)] == {"ADIKMET": 379}
    assert matched.values[(2026, 6)] == {}  # absent identity is unknown, not a zero observation


def test_crosswalk_never_duplicates_old_history_and_marks_ambiguity():
    old = {"ALPHA": "1", "BETA": "2"}
    new = {"ALPHA": "1", "ALPHA (OLD)": "1", "BETA (OLD)": "2"}
    matches = refresh.match_sections(old, new)
    by_name = {r["section"]: r for r in matches}
    assert by_name["ALPHA"]["old_section"] == "ALPHA"
    assert by_name["ALPHA"]["match_status"] == "approximate"
    assert by_name["ALPHA (OLD)"]["match_status"] == "unmatched"
    assert len([r for r in matches if r["old_section"] == "ALPHA"]) == 1


def test_latest_city_totals_include_every_recut_section():
    panel = fc.Panel("noofbookings", {(2025, 8): {"A": 30}, (2026, 8): {"A": 4, "NEW": 60}})
    city = refresh.city_panel(panel)
    assert city.values[(2026, 8)] == {"city": 64}
    rows = refresh.city_forecast_rows(panel, "seasonal_naive", 12)
    assert rows[0]["month"] == "2026-09"
    assert rows[-1]["month"] == "2027-08"
    assert rows[-1]["point"] == 64


def test_city_interval_uses_city_residual_not_sum_of_section_widths():
    rows = [
        fc.BacktestRow(
            "seasonal_naive", (2023 + i // 12, i % 12 + 1), 100, 90 + i, abs(10 - i), 0, 100, 1
        )
        for i in range(24)
    ]
    intervals, measured = refresh.city_intervals(rows, "seasonal_naive")
    assert math.isfinite(intervals[0.8])
    assert len(measured) == 2
    assert all(r["months"] == 12 for r in measured)
    assert all(0 <= r["coverage"] <= 1 for r in measured)


def test_level_candidate_refuses_target_leakage():
    panel = fc.Panel(
        "noofbookings",
        {(2024, m): {"city": 100} for m in range(1, 13)}
        | {(2025, m): {"city": 150} for m in range(1, 7)},
    )
    assert refresh.city_predict(panel, (2025, 7), "seasonal_level12") > 100
    with pytest.raises(ValueError):
        refresh.city_predict(panel, (2025, 6), "seasonal_level12")
