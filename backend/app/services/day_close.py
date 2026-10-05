"""Closing a day: water debt (A6, F11) from an approved supplied plan and its delivery outcomes.

The approved plan says how many litres of scheduled supply each registered stop gets that day
(A4 split across the ward's stops, as the plan was built). For each ward:

    entitled = litres the plan gave the ward's stops
    credited = one tanker load for each Confirmed delivery started that day (Hyderabad time) at
               a stop now registered in the ward
    debt'    = min(cap, max(0, debt + entitled - credited))        (A6 settle_day, unchanged)

Disputed, Unconfirmed and Failed deliveries never pay debt back (A6/T3). A ward that already has
an account is settled even when the plan gives it nothing, so its days stay in order. A day with
no supplied plan is closed without one: nothing is owed, Confirmed deliveries still pay debt
back. Nothing is written unless every check passes: an approved plan for that very day (when one
is given), every delivery of the day closed, no ward already settled for the day, and a reason.
Then one `water_debt_changed` entry per changed account (A6) and one `debt_day_closed` entry are
appended.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

from app.config.allocation import ALLOCATION_CONFIG
from app.config.report_cards import REPORT_CARD_CONFIG
from app.services import delivery as dl
from app.services import planner, water_debt
from app.services.ledger_port import LedgerPort
from app.services.plan_builder import stop_litres
from app.services.water_debt import DebtAccount, DeliveryCredit

WARD_PREFIX = "ward:"


class DayCloseRefused(ValueError):
    """The day cannot be closed (yet); nothing was written."""


@dataclass(frozen=True)
class WardDay:
    ward_id: str
    planned_litres: float
    credited_litres: float
    deliveries: dict[str, int]  # outcome -> count, deliveries at the ward's stops that day
    debt_before: float
    debt_after: float
    capped: bool
    alert: bool
    days_in_debt: int


@dataclass(frozen=True)
class ClosedDay:
    day: date
    plan_id: str | None  # None: closed without a plan
    plan_digest: str | None
    accounts: tuple[DebtAccount, ...]  # every account settled, by id
    wards: tuple[WardDay, ...]  # by ward id


def service_day(moment: datetime) -> date:
    """The Hyderabad day of a moment (a delivery's start)."""
    return moment.astimezone(REPORT_CARD_CONFIG.service_timezone).date()


def day_bounds(day: date) -> tuple[datetime, datetime]:
    """[start, end) of a Hyderabad day, as aware datetimes."""
    start = datetime.combine(day, datetime.min.time(), REPORT_CARD_CONFIG.service_timezone)
    return start, start + timedelta(days=1)


def account_id(ward_id: str) -> str:
    return f"{WARD_PREFIX}{ward_id}"


def _checks(
    day: date,
    plan: planner.DailyPlan | None,
    deliveries: Sequence[dl.DeliveryState],
    accounts: Mapping[str, DebtAccount],
    reason: str,
) -> dict[str, Any]:
    try:
        fields = planner._reason_fields(reason)
    except ValueError as exc:
        raise DayCloseRefused("A reason is required to close a day") from exc
    if plan is not None and plan.day != day:
        raise DayCloseRefused(
            f"Plan {plan.plan_id} is for {plan.day.isoformat()}, not {day.isoformat()}"
        )
    if plan is not None and plan.status != "APPROVED":
        raise DayCloseRefused(f"Plan {plan.plan_id} must be approved before its day is closed")
    elsewhere = [d.delivery_id for d in deliveries if service_day(d.started_at) != day]
    if elsewhere:
        raise DayCloseRefused(
            f"Deliveries {elsewhere} did not start on {day.isoformat()} (Hyderabad time)"
        )
    still_open = sorted(d.delivery_id for d in deliveries if d.outcome is None)
    if still_open:
        raise DayCloseRefused(
            f"Deliveries still open: {still_open}; their outcomes must be decided first"
        )
    settled = sorted(
        a.account_id
        for a in accounts.values()
        if a.settled_through is not None and a.settled_through >= day
    )
    if settled:
        raise DayCloseRefused(f"{settled} already settled through {day.isoformat()} or later")
    return fields


def close_day(
    day: date,
    plan: planner.DailyPlan | None,
    plan_stops: Sequence[Mapping[str, Any]],
    ward_of_stop: Mapping[str, str],
    deliveries: Sequence[dl.DeliveryState],
    accounts: Mapping[str, DebtAccount],
    ledger: LedgerPort,
    now: datetime,
    officer_id: str,
    reason: str,
) -> ClosedDay:
    """Settle every ward's debt for `day`: owed = what the approved plan (None: no plan) gave
    the stops it was built with (`plan_stops`); paid = Confirmed deliveries of the day, each
    counted for the ward its stop serves now (`ward_of_stop`). Raises DayCloseRefused, writing
    nothing, if it cannot."""
    fields = _checks(day, plan, deliveries, accounts, reason)
    planned: dict[str, float] = defaultdict(float)
    if plan is not None:
        built_ward = {str(s["stop_id"]): str(s["ward_id"]) for s in plan_stops}
        for stop_id, litres in stop_litres(plan, list(built_ward)).items():
            planned[built_ward[stop_id]] += litres
    by_ward: dict[str, list[dl.DeliveryState]] = defaultdict(list)
    for delivery in deliveries:
        if delivery.stop_id in ward_of_stop:
            by_ward[ward_of_stop[delivery.stop_id]].append(delivery)

    load = ALLOCATION_CONFIG.tanker_load_litres
    wards = sorted(
        {w for w, litres in planned.items() if litres > 0}
        | {a.removeprefix(WARD_PREFIX) for a in accounts if a.startswith(WARD_PREFIX)}
    )
    settled: list[DebtAccount] = []
    days: list[WardDay] = []
    for ward in wards:
        key = account_id(ward)
        entitled = planned.get(ward, 0.0)
        account = accounts.get(key) or DebtAccount(key, entitled)
        if entitled > 0:  # the cap follows the latest day's entitlement
            account = DebtAccount(**{**account.__dict__, "daily_entitlement_litres": entitled})
        done = [d for d in by_ward.get(ward, []) if d.outcome is not None]
        credits = [
            DeliveryCredit(d.delivery_id, float(load), d.outcome.outcome)  # type: ignore[union-attr]
            for d in done
        ]
        change = water_debt.settle_day(account, day, entitled, credits, ledger, now, officer_id)
        settled.append(change.account)
        days.append(
            WardDay(
                ward_id=ward,
                planned_litres=entitled,
                credited_litres=change.credited_litres,
                deliveries=dict(sorted(Counter(c.outcome for c in credits).items())),
                debt_before=change.debt_before,
                debt_after=change.account.debt_litres,
                capped=change.capped,
                alert=change.alert,
                days_in_debt=change.days_in_debt,
            )
        )
    ledger.append(
        "debt_day_closed",
        {
            "entity_type": "debt_day",
            "entity_id": day.isoformat(),
            "day": day.isoformat(),
            "plan_id": plan.plan_id if plan else None,
            "digest": plan.digest if plan else None,
            "wards": len(days),
            "planned_litres": round(sum(w.planned_litres for w in days), 3),
            "credited_litres": round(sum(w.credited_litres for w in days), 3),
            "debt_after_litres": round(sum(w.debt_after for w in days), 3),
            "alerts": sorted(w.ward_id for w in days if w.alert),
            "at": now.isoformat(),
            **fields,
        },
        officer_id,
    )
    return ClosedDay(
        day=day,
        plan_id=plan.plan_id if plan else None,
        plan_digest=plan.digest if plan else None,
        accounts=tuple(sorted(settled, key=lambda a: a.account_id)),
        wards=tuple(days),
    )
