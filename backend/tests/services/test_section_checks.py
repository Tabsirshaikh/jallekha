"""Section screening never manufactures missing bookings or learns from the test year."""

from dataclasses import replace

import pytest

from app.config.section_checks import SECTION_CHECK_CONFIG
from app.services.section_checks import AnnualSection, backtest, screen


def cohort(year=2024):
    return [
        AnnualSection(str(i), "1", year, 120 if i == 0 else 1200, 1000, 0.1, 12, 12)
        for i in range(8)
    ]


def test_target_excluded_and_need_only_gates_the_flag():
    rows = cohort()
    config = replace(SECTION_CHECK_CONFIG, ratio_quantile=0.5)
    needs = {str(i): 0.8 if i == 0 else 0.2 for i in range(8)}
    results = screen(rows, rows, needs, config)
    target = results[0]
    assert "0" not in target["peer_sections"]
    assert target["reference_rate"] == 1200
    assert target["field_check_candidate"] is True
    assert (
        screen(rows, rows, {str(i): 0.2 for i in range(8)}, config)[0]["field_check_candidate"]
        is False
    )


def test_incomplete_year_and_missing_denominator_never_become_zero():
    rows = cohort()
    rows[0] = replace(rows[0], booking_months=11)
    rows[1] = replace(rows[1], connections=0)
    results = screen(rows, cohort(), {}, SECTION_CHECK_CONFIG)
    assert results[0]["rate"] is None
    assert results[0]["status"] == "INCOMPLETE_SOURCE_YEAR"
    assert results[1]["rate"] is None
    assert results[1]["status"] == "MISSING_DOMESTIC_CONNECTIONS"
    assert all(not r["field_check_candidate"] for r in results)


def test_training_predictions_unchanged_when_test_bookings_change():
    train, test = cohort(), cohort(2025)
    first = backtest(train, test)
    test[0] = replace(test[0], bookings=50000)
    second = backtest(train, test)
    assert [r["expected"] for r in first["predictions"]] == [
        r["expected"] for r in second["predictions"]
    ]
    assert first["peer"]["mean_absolute_error"] != second["peer"]["mean_absolute_error"]
    assert first["train_year"] == 2024
    assert first["test_year"] == 2025


def test_negative_counts_rejected():
    with pytest.raises(ValueError):
        AnnualSection("bad", "1", 2024, -1, 1000, 0.1, 12, 12)
