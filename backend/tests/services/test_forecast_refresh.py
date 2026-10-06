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


def test_division_annotation_is_not_an_unmatched_locality_or_an_authoritative_boundary():
    matches = refresh.match_sections({"ALWAL (Div13)": "13"}, {"ALWAL": "73"})
    assert matches[0]["old_section"] == "ALWAL (Div13)"
    assert matches[0]["match_status"] == "approximate"
    assert refresh.normal_name("NAGARAM (PD 3)") == "NAGARAM"
    assert refresh.normal_name("RED HILLS HIGH LEVEL") != refresh.normal_name("RED HILLS LOW LEVEL")


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


def test_city_ranges_adapt_to_recent_errors_and_never_calibrate_on_the_held_month():
    rows = [
        fc.BacktestRow(
            "seasonal_naive",
            (2023 + i // 12, i % 12 + 1),
            2000,
            1990 if i < 12 else 1000,
            0,
            0,
            1,
            1,
        )
        for i in range(24)
    ]
    _, measured = refresh.city_intervals(rows, "seasonal_naive")
    assert all(r["coverage"] < 1 for r in measured)  # the first new surge cannot calibrate itself
    falling = [
        fc.BacktestRow(
            "seasonal_naive",
            (2023 + i // 12, i % 12 + 1),
            2000,
            1000 if i < 12 else 1990,
            0,
            0,
            1,
            1,
        )
        for i in range(24)
    ]
    widths, _ = refresh.city_intervals(falling, "seasonal_naive")
    assert widths[0.8] == 10  # older, very large errors are outside the recent window


def test_joint_groundwater_reservoir_candidate_is_ex_ante():
    panel = fc.Panel(
        "noofbookings", {(2023 + i // 12, i % 12 + 1): {"city": 100 + i} for i in range(30)}
    )
    target = (2025, 7)
    signals = {"ridge_groundwater": {(2025, 6): 0.5}, "ridge_reservoir": {(2025, 6): 0.4}}
    point = refresh.city_predict(panel, target, "ridge_groundwater_reservoir", signals)
    assert point is not None
    signals["ridge_groundwater"][target] = 100000
    signals["ridge_reservoir"][target] = 100000
    assert refresh.city_predict(panel, target, "ridge_groundwater_reservoir", signals) == point


def test_gbm_returns_no_section_predictions_for_an_empty_seasonal_month():
    panel = fc.Panel("noofbookings", {(2024, 1): {}})
    assert fc.global_gbm(panel, (2025, 1)) == {}


def test_gbm_does_not_train_missing_section_months_as_zero(monkeypatch):
    from dataclasses import replace

    import numpy as np
    import sklearn.ensemble

    recorded = []

    class Model:
        def __init__(self, **kwargs):
            pass

        def fit(self, features, targets):
            recorded.extend(targets)

        def predict(self, features):
            return np.zeros(len(features))

    monkeypatch.setattr(sklearn.ensemble, "HistGradientBoostingRegressor", Model)
    monkeypatch.setattr(
        fc,
        "FORECAST_CONFIG",
        replace(fc.FORECAST_CONFIG, gbm_min_training_rows=1, gbm_min_training_months=1),
    )
    panel = fc.Panel("noofbookings", {(2023 + i // 12, i % 12 + 1): {"S": 50} for i in range(24)})
    panel.values[(2024, 6)] = {}
    assert fc.global_gbm(panel, (2025, 1)) is not None
    assert recorded and all(abs(value) < 1e-12 for value in recorded)


def test_level_candidate_refuses_target_leakage():
    panel = fc.Panel(
        "noofbookings",
        {(2024, m): {"city": 100} for m in range(1, 13)}
        | {(2025, m): {"city": 150} for m in range(1, 7)},
    )
    assert refresh.city_predict(panel, (2025, 7), "seasonal_level12") > 100
    with pytest.raises(ValueError):
        refresh.city_predict(panel, (2025, 6), "seasonal_level12")
