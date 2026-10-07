"""Verified recent tanker shortfall, separate from structural Census vulnerability.

No assessment or incomplete records means unknown, never zero supply. The 15 lpcd
allowance is an emergency minimum, not total domestic water demand. Officers estimate
the population share needing tanker water after checking alternative supply.
"""

from datetime import date, timedelta
from math import isfinite

from app.config.allocation import ALLOCATION_CONFIG
from app.config.weekly_priority import WEEKLY_PRIORITY_CONFIG as CFG


def calculate(population, baseline, review, delivered, as_of: date, days_below_minimum=0):
    end = as_of - timedelta(days=1)
    start = as_of - timedelta(days=CFG.window_days)
    result = {
        "window_start": start.isoformat(),
        "window_end": end.isoformat(),
        "population_estimate": population,
        "baseline_need_weight": baseline,
        "daily_allowance_litres": ALLOCATION_CONFIG.minimum_litres_per_person_day,
        "weekly_requirement_litres": None,
        "confirmed_litres": None,
        "shortfall_litres": None,
        "shortfall_share": None,
        "days_below_minimum": None,
        "allocation_factor": 1.0,
        "current_need_weight": baseline,
        "status": "UNKNOWN",
        "reason": "NO_CURRENT_VERIFIED_SUPPLY_AND_COMPLETE_DELIVERY_RECORDS",
        "basis": "DERIVED_APPROXIMATE (connection-based population; officer supply assessment; "
        "ASSUMED emergency allowance and priority coefficients)",
    }
    if not review or review.get("ledger_missing", True):
        return result
    checked = date.fromisoformat(review["checked_on"])
    if checked != end or not review["records_complete"] or review["supply"] == "unknown":
        return result
    if not isfinite(population) or population <= 0 or not isfinite(delivered) or delivered < 0:
        return result
    share = review["tanker_share"]
    required = population * share * result["daily_allowance_litres"] * CFG.window_days
    shortfall = max(0, required - delivered)
    ratio = shortfall / required if required else 0.0
    factor = CFG.covered_factor + (CFG.shortage_factor - CFG.covered_factor) * ratio
    factor *= 1 + CFG.deprivation_weight * (days_below_minimum / CFG.window_days) * ratio
    result.update(
        weekly_requirement_litres=round(required, 2),
        confirmed_litres=round(delivered, 2),
        shortfall_litres=round(shortfall, 2),
        shortfall_share=ratio,
        days_below_minimum=days_below_minimum,
        allocation_factor=factor,
        current_need_weight=baseline * factor,
        status="SHORTFALL" if shortfall > 0 else "COVERED",
        reason="VERIFIED_WEEKLY_SHORTFALL" if shortfall > 0 else "VERIFIED_REQUIREMENT_COVERED",
    )
    return result


def allocation_factors(values):
    return {
        group: value["allocation_factor"]
        for group, value in values.items()
        if value["status"] != "UNKNOWN"
    }


def section_debt(section, ward, accounts):
    """Prefer the section's exact account, including zero; ward debt is approximate fallback."""
    account = accounts.get(f"section:{section}")
    if account is not None:
        return account.debt_litres, "SECTION_ACCOUNT"
    fallback = accounts.get(f"ward:{ward}")
    return (fallback.debt_litres, "WARD_PROXY") if fallback else (0.0, "UNAVAILABLE")
