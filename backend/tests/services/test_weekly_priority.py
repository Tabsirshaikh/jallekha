from datetime import date

from app.services.water_debt import DebtAccount
from app.services.weekly_priority import allocation_factors, calculate, section_debt

DAY = date(2026, 10, 7)


def review(**changes):
    return {
        "checked_on": "2026-10-06",
        "supply": "unavailable",
        "tanker_share": 1.0,
        "records_complete": True,
        "ledger_missing": False,
        **changes,
    }


def test_delivered_water_reduces_priority_and_neglected_area_overtakes_baseline():
    served = calculate(100, 2.0, review(), 10500, DAY)
    neglected = calculate(100, 1.2, review(), 0, DAY)
    assert served["weekly_requirement_litres"] == 10500
    assert served["shortfall_litres"] == 0
    assert neglected["shortfall_litres"] == 10500
    assert neglected["current_need_weight"] > served["current_need_weight"]
    assert allocation_factors({"a": served, "b": neglected})["a"] < 1


def test_partial_delivery_is_not_adequate_and_no_booking_needed():
    value = calculate(100, 1.2, review(), 1000, DAY)
    assert value["shortfall_litres"] == 9500
    assert value["allocation_factor"] > 1


def test_unknown_stale_unlogged_or_incomplete_records_do_not_infer_zero_supply():
    for assessment in [
        None,
        review(supply="unknown"),
        review(records_complete=False),
        review(checked_on="2026-09-20"),
        review(ledger_missing=True),
    ]:
        value = calculate(100, 1.2, assessment, 0, DAY)
        assert value["shortfall_litres"] is None
        assert value["allocation_factor"] == 1
        assert value["status"] == "UNKNOWN"


def test_alternative_supply_adequate_does_not_claim_tanker_shortage():
    value = calculate(100, 2, review(supply="adequate", tanker_share=0), 0, DAY)
    assert value["weekly_requirement_litres"] == 0
    assert value["shortfall_litres"] == 0
    assert value["status"] == "COVERED"


def test_future_review_cannot_change_historical_plan():
    assert calculate(100, 2, review(), 0, date(2025, 5, 15))["status"] == "UNKNOWN"


def test_new_day_without_complete_records_returns_unknown():
    assert calculate(100, 2, review(), 0, date(2026, 10, 8))["status"] == "UNKNOWN"


def test_section_debt_zero_overrides_ward_proxy():
    accounts = {
        "section:A": DebtAccount("section:A", 1000, debt_litres=0),
        "ward:W": DebtAccount("ward:W", 1000, debt_litres=999),
    }
    assert section_debt("A", "W", accounts) == (0, "SECTION_ACCOUNT")
    assert section_debt("B", "W", accounts) == (999, "WARD_PROXY")


def test_more_days_below_daily_minimum_raise_priority_at_same_weekly_shortfall():
    brief = calculate(100, 1.2, review(), 5000, DAY, days_below_minimum=1)
    prolonged = calculate(100, 1.2, review(), 5000, DAY, days_below_minimum=6)
    assert prolonged["allocation_factor"] > brief["allocation_factor"]
    covered = calculate(100, 1.2, review(), 10500, DAY, days_below_minimum=6)
    assert covered["allocation_factor"] == 0.25
