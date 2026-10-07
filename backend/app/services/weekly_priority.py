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
        basis=("SYNTHETIC (demo supply check) on " if review.get("synthetic") else "")
        + result["basis"],
        reason="VERIFIED_WEEKLY_SHORTFALL" if shortfall > 0 else "VERIFIED_REQUIREMENT_COVERED",
    )
    return result


def service_factor(unmet_share: float) -> float:
    """Turn factor from the share of the need that went unmet (0 = fully served -> covered
    factor; 1 = nothing served -> shortage factor), straight in between. ASSUMED coefficients."""
    unmet = min(1.0, max(0.0, unmet_share))
    return CFG.covered_factor + (CFG.shortage_factor - CFG.covered_factor) * unmet


def from_bookings(population, baseline, delivered, not_delivered, unknown, as_of: date):
    """Current priority from the section's own bookings of the last 7 completed days, when no
    officer supply check applies: each booking is one tanker load (5,000 l, ASSUMED); the
    shortfall is the loads booked but not delivered. Only bookings with a known result count;
    too few known results leave the section UNKNOWN (Census baseline)."""
    result = calculate(population, baseline, None, 0, as_of)
    known = delivered + not_delivered
    result.update(
        source="BOOKINGS",
        bookings_delivered=delivered,
        bookings_not_delivered=not_delivered,
        bookings_unknown=unknown,
    )
    if known < CFG.min_known_bookings:
        result["reason"] = "TOO_FEW_BOOKINGS_WITH_A_KNOWN_RESULT"
        return result
    load = ALLOCATION_CONFIG.tanker_load_litres
    required, confirmed = known * load, delivered * load
    shortfall = required - confirmed
    ratio = not_delivered / known
    factor = service_factor(ratio)
    result.update(
        weekly_requirement_litres=float(required),
        confirmed_litres=float(confirmed),
        shortfall_litres=float(shortfall),
        shortfall_share=ratio,
        days_below_minimum=None,
        allocation_factor=factor,
        current_need_weight=baseline * factor,
        status="SHORTFALL" if shortfall > 0 else "COVERED",
        reason="BOOKINGS_NOT_DELIVERED" if shortfall > 0 else "BOOKINGS_DELIVERED",
        basis="DERIVED (the section's JalLekha bookings and Confirmed deliveries of the last 7 "
        "days; one booking = one 5,000-litre load, ASSUMED coefficients)",
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
