"""The live blocks of a ward report card (F20): deliveries, water debt and schedule.

Each block is {value, basis, reason}: a value with its basis and reason null, or value null with
basis UNAVAILABLE and the reason. Nothing here is sample data.

- deliveries: tanker visits started in the last `delivery_window_days` at the ward's registered
  stops, by F12 outcome (REAL or SYNTHETIC as the stops are registered).
- debt: the ward's A6 account as the last closed day left it (DERIVED: planned litres at the
  ward's stops minus Confirmed deliveries).
- schedule: the ward's part of one stored plan: booked trips served and waiting for the ward's
  group, its scheduled-supply share and the loads planned for each of its stops.
"""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta
from typing import Any

from app.config.allocation import ALLOCATION_CONFIG
from app.config.report_cards import REPORT_CARD_CONFIG
from app.services import booking_groups, planner
from app.services import delivery as dl
from app.services.delivery_store import Stop
from app.services.plan_builder import SOURCE, stop_litres
from app.services.water_debt import DebtAccount, cap_litres

UNAVAILABLE = "UNAVAILABLE"
OUTCOMES = ("Confirmed", "Disputed", "Unconfirmed", "Failed")


def _value(value: Any, basis: str) -> dict[str, Any]:
    return {"value": value, "basis": basis, "reason": None}


def _none(reason: str) -> dict[str, Any]:
    return {"value": None, "basis": UNAVAILABLE, "reason": reason}


def delivery_window(now: datetime) -> tuple[datetime, datetime]:
    return now - timedelta(days=REPORT_CARD_CONFIG.delivery_window_days), now


def deliveries_block(
    stops: Sequence[Stop], deliveries: Sequence[dl.DeliveryState], now: datetime
) -> dict[str, Any]:
    """Deliveries at these stops (the ward's) started in the window ending now."""
    if not stops:
        return _none("no delivery stop is registered in this ward yet")
    start, end = delivery_window(now)
    ids = {s.stop_id for s in stops}
    counted = [d for d in deliveries if d.stop_id in ids and start <= d.started_at < end]
    outcomes = Counter(d.outcome.outcome if d.outcome else "open" for d in counted)
    bases = sorted({s.basis for s in stops})
    basis = bases[0] if len(bases) == 1 else f"MIXED ({' and '.join(bases)} stops)"
    return _value(
        {
            "window_days": REPORT_CARD_CONFIG.delivery_window_days,
            "from": start.isoformat(),
            "to": end.isoformat(),
            "stops": [
                {"stop_id": s.stop_id, "basis": s.basis, "ward_basis": s.ward_basis}
                for s in sorted(stops, key=lambda s: s.stop_id)
            ],
            "started": len(counted),
            "by_outcome": {o: outcomes.get(o, 0) for o in (*OUTCOMES, "open")},
            "confirmed_litres": outcomes.get("Confirmed", 0) * ALLOCATION_CONFIG.tanker_load_litres,
        },
        basis,
    )


def debt_block(account: DebtAccount | None, last_day: Mapping[str, Any] | None) -> dict[str, Any]:
    if account is None:
        return _none(
            "no closed day has given this ward planned water yet, so it has no debt account"
        )
    days = (
        (account.settled_through - account.in_debt_since).days + 1
        if account.in_debt_since and account.settled_through
        else 0
    )
    return _value(
        {
            "debt_litres": account.debt_litres,
            "debt_loads": math.ceil(account.debt_litres / ALLOCATION_CONFIG.tanker_load_litres),
            "cap_litres": cap_litres(account),
            "in_debt_since": account.in_debt_since.isoformat() if account.in_debt_since else None,
            "days_in_debt": days,
            "alert_raised": account.alert_raised,
            "settled_through": (
                account.settled_through.isoformat() if account.settled_through else None
            ),
            "last_day": dict(last_day) if last_day else None,
        },
        "DERIVED (A6: litres the approved plan gave the ward's stops minus one load per Confirmed "
        "delivery, settled when an officer closes the day; bookings as supplied, not verified)",
    )


def schedule_block(
    plan: planner.DailyPlan | None,
    recipe: Mapping[str, Any] | None,
    inputs: planner.PlanInputs | None,
    basis: Mapping[str, str] | None,
    ward_id: str,
) -> dict[str, Any]:
    """The ward's part of one plan (the caller chooses which; see the router)."""
    if plan is None or inputs is None:
        return _none("no plan has been built yet")
    group = booking_groups.ward_group(ward_id)
    group_of = {p.booking.booking_id: p.booking.group for p in inputs.pending}
    served = sum(1 for s in plan.stations.values() for b in s.served if b.group == group)
    waiting = sum(1 for s in plan.stations.values() for b in s.waiting if group_of.get(b) == group)
    share = plan.scheduled.get(ward_id)
    stops = [s for s in (recipe or {}).get("stops", []) if s["ward_id"] == ward_id]
    litres = stop_litres(plan, [s["stop_id"] for s in stops])
    arrivals: dict[str, list[str]] = {}
    for stop in plan.special_stops:
        if stop.kind == "scheduled":
            arrivals.setdefault(stop.place_id, []).append(stop.arrival)
    load = ALLOCATION_CONFIG.tanker_load_litres
    source = (recipe or {}).get("source", SOURCE)
    return _value(
        {
            "plan_id": plan.plan_id,
            "day": plan.day.isoformat(),
            "status": plan.status,
            "source": source,
            "booked": {"group": group, "served": served, "waiting": waiting},
            "scheduled": (
                {
                    "litres": share.litres,
                    "floor": share.floor,
                    "target": share.target,
                    "status": share.status,
                }
                if share
                else None
            ),
            "stops": [
                {
                    "stop_id": s["stop_id"],
                    "litres": litres[s["stop_id"]],
                    "loads": litres[s["stop_id"]] / load,
                    "arrivals": sorted(arrivals.get(s["stop_id"], [])),
                }
                for s in stops
            ],
        },
        (basis or {}).get("plan", "UNKNOWN"),
    )
