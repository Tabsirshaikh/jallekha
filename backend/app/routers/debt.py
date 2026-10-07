"""Water debt endpoints (A6 on stored plans, F11, F20): an officer closes a day, officers read the
accounts and the closed days. See docs/api_additions/report_cards.md.

Closing a day settles every ward's debt from one approved plan built from supplied bookings
(replay plans are simulations and never create debt) and that day's delivery outcomes at the
plan's stops (services/day_close.py). Days close once, in order, after they end (Hyderabad
time). One close at a time inside this process; the unique day refuses a second close from
another process (409).
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict
from datetime import date, datetime, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.auth import require_roles
from app.config.api import ApiConfig
from app.config.env import REPO_ROOT
from app.config.report_cards import REPORT_CARD_CONFIG
from app.routers.common import get_now, invalid, page
from app.routers.plans import Ledger, Plans, _record
from app.routers.stores import DebtStore, DeliveryStore, get_debt_store, get_delivery_store
from app.services import day_close, plan_builder, section_plan, ward_locate
from app.services.debt_store import DebtDayConflict
from app.services.keyed_lock import KeyedLocks
from app.services.water_debt import DebtAccount, cap_litres

router = APIRouter(prefix="/debt", tags=["debt"])

Officer = Depends(require_roles("officer"))
Debts = Annotated[DebtStore, Depends(get_debt_store)]
Deliveries = Annotated[DeliveryStore, Depends(get_delivery_store)]
Now = Annotated[datetime, Depends(get_now)]
Offset = Annotated[int, Query(ge=0)]
Limit = Annotated[int, Query(ge=1, le=ApiConfig.max_limit)]

_locks = KeyedLocks()
_CLOSING = "debt-days"


class CloseDay(BaseModel):
    # The approved supplied plan for the day; absent: the day had no plan (nothing is owed,
    # Confirmed deliveries still pay debt back).
    plan_id: str | None = None
    officer_id: str
    reason: str


@contextmanager
def _one_close() -> Iterator[None]:
    with _locks.hold(_CLOSING):
        yield


def account_view(account: DebtAccount) -> dict[str, Any]:
    by_section = account.account_id.startswith(day_close.SECTION_PREFIX)
    ward_id = account.account_id.removeprefix(day_close.WARD_PREFIX)
    return {
        "account_id": account.account_id,
        "unit": "section" if by_section else "ward",
        "ward_id": None if by_section else ward_id,
        "ward_name": (
            account.account_id.removeprefix(day_close.SECTION_PREFIX)
            if by_section
            else ward_locate.ward_name(ward_id)
        ),
        "debt_litres": account.debt_litres,
        "daily_entitlement_litres": account.daily_entitlement_litres,
        "cap_litres": cap_litres(account),
        "in_debt_since": account.in_debt_since.isoformat() if account.in_debt_since else None,
        "alert_raised": account.alert_raised,
        "settled_through": account.settled_through.isoformat() if account.settled_through else None,
    }


def _closed_view(closed: day_close.ClosedDay) -> dict[str, Any]:
    return {
        "day": closed.day.isoformat(),
        "plan_id": closed.plan_id,
        "plan_digest": closed.plan_digest,
        "wards": [
            {
                **asdict(w),
                "ward_name": (
                    w.ward_id.removeprefix(day_close.SECTION_PREFIX)
                    if w.ward_id.startswith(day_close.SECTION_PREFIX)
                    else ward_locate.ward_name(w.ward_id)
                ),
            }
            for w in closed.wards
        ],
        "accounts": [account_view(a) for a in closed.accounts],
        "basis": (
            "DERIVED (A6: litres the approved plan gave each ward's registered stops minus one "
            "tanker load per Confirmed delivery started that day at those stops)"
        ),
    }


@router.post("/days/{day}/close", dependencies=[Officer])
def close(
    day: date,
    body: CloseDay,
    plans: Plans,
    deliveries: Deliveries,
    debts: Debts,
    ledger: Ledger,
    now: Now,
) -> Any:
    if not body.reason.strip():
        return invalid("A reason is required to close a day")
    today = now.astimezone(REPORT_CARD_CONFIG.service_timezone).date()
    if day >= today:
        raise HTTPException(409, f"{day.isoformat()} is not over yet (Hyderabad time)")
    with _one_close():
        last = debts.last_closed_day()
        if last is not None and day == last:
            raise HTTPException(409, f"{day.isoformat()} is already closed")
        if last is not None and day < last:
            raise HTTPException(
                409, f"Days are closed in order: {last.isoformat()} is already closed"
            )
        if last is not None and day != last + timedelta(days=1):
            following = (last + timedelta(days=1)).isoformat()
            raise HTTPException(
                409,
                f"Days are closed one after another: close {following} first (without a plan "
                "if it had none)",
            )
        plan, plan_stops = None, []
        by_section = False
        if body.plan_id is not None:
            record = _record(plans, body.plan_id)
            recipe = record.recipe or {}
            by_section = recipe.get("source") == plan_builder.SECTION
            if recipe.get("source") not in (plan_builder.SUPPLIED, plan_builder.SECTION):
                raise HTTPException(
                    409,
                    f"Plan {body.plan_id} is a replay SIMULATION; only a plan built from "
                    "supplied bookings or by section can create water debt",
                )
            plan, plan_stops = record.plan, recipe.get("stops", [])
        # Every delivery of the day at a stop that serves a ward counts for that ward.
        ward_of_stop = {s.stop_id: s.ward_id for s in deliveries.list_stops() if s.ward_id}
        start, end = day_close.day_bounds(day)
        todays = deliveries.list_deliveries(
            stop_ids=list(ward_of_stop), started_from=start, started_before=end
        )
        try:
            if by_section:
                assert plan is not None
                stop_section = {
                    s.stop_id: g
                    for s in deliveries.list_stops()
                    if (g := section_plan.section_of_point(REPO_ROOT, s.lat, s.lon)) is not None
                }
                section_todays = deliveries.list_deliveries(
                    stop_ids=list(stop_section), started_from=start, started_before=end
                )
                if "bookings" in recipe:
                    booked = Counter(
                        "section:" + b["section"]
                        for b in recipe["bookings"]
                        if datetime.fromisoformat(b["arrived_at"])
                        .astimezone(section_plan.IST)
                        .date()
                        == day
                    )
                else:
                    booked = section_plan.fresh_bookings(REPO_ROOT, day)
                closed = day_close.close_section_day(
                    day, plan, booked, stop_section,
                    section_todays, debts.accounts(), ledger, now, body.officer_id, body.reason,
                )  # fmt: skip
            else:
                closed = day_close.close_day(
                    day, plan, plan_stops, ward_of_stop, todays, debts.accounts(), ledger, now,
                    body.officer_id, body.reason,
                )  # fmt: skip
        except day_close.DayCloseRefused as exc:
            raise HTTPException(409, str(exc)) from exc
        try:
            debts.save(closed, body.officer_id, body.reason)
        except DebtDayConflict as exc:
            raise HTTPException(409, str(exc)) from exc
        return _closed_view(closed)


@router.get("/accounts", dependencies=[Officer])
def accounts(
    debts: Debts, offset: Offset = 0, limit: Limit = ApiConfig.default_limit
) -> dict[str, Any]:
    return page([account_view(a) for a in debts.accounts().values()], offset, limit)


@router.get("/days", dependencies=[Officer])
def days(
    debts: Debts, offset: Offset = 0, limit: Limit = ApiConfig.default_limit
) -> dict[str, Any]:
    return page(debts.closed_days(), offset, limit)
