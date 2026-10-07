"""A driver's route for the day: the trips of their tanker in the approved plan by section, with the
bookings made through JalLekha marked so the driver can prove each delivery (F12).

`GET /driver/tankers?day=` lists the tankers of the day's approved plan that carry at least one
such booking (the ones a test or a pilot can follow); `GET /driver/route?day=&tanker_id=` gives
one tanker's trips. Estimated loads (from monthly totals) stay on the sheet without a delivery
code: there is no person behind them.
"""

from __future__ import annotations

from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth import require_roles
from app.routers import bookings as booking_routes
from app.routers import deliveries
from app.routers.plans import Plans, _record, routes_of
from app.routers.stores import DeliveryStore, get_booking_store, get_delivery_store
from app.services import booking_dispatch, plan_builder
from app.services import bookings as bk
from app.services.ledger_store import StoredLedger

router = APIRouter(prefix="/driver", tags=["driver"])

Reader = Depends(require_roles("driver", "officer"))
Bookings = Annotated[bk.BookingStore, Depends(get_booking_store)]
Deliveries = Annotated[DeliveryStore, Depends(get_delivery_store)]
Ledger = Annotated[StoredLedger, Depends(deliveries.get_delivery_ledger)]


def _approved(plans: Plans, day: date) -> str:
    """The approved plan by section for `day` (the latest approved one if there are several)."""
    found = [
        s["plan_id"]
        for s in plans.summaries()
        if s["day"] == day.isoformat()
        and s["status"] == "APPROVED"
        and s.get("source") == plan_builder.SECTION
    ]
    if not found:
        raise HTTPException(404, f"No approved plan by section for {day.isoformat()}")
    return found[-1]


@router.get("/tankers", dependencies=[Reader])
def tankers(day: date, plans: Plans) -> dict[str, Any]:
    plan_id = _approved(plans, day)
    routes = routes_of(_record(plans, plan_id))
    items = []
    for t in routes["tankers"]:
        real = [x for x in t["trips"] if booking_dispatch.is_real(x.get("booking_id"))]
        if real:
            items.append(
                {
                    "tanker_id": t["tanker_id"],
                    "station_id": t["station_id"],
                    "trips": len(t["trips"]),
                    "real_bookings": len(real),
                    "first_depart": t["trips"][0]["depart"],
                }
            )
    return {"day": day.isoformat(), "plan_id": plan_id, "tankers_total": len(routes["tankers"]),
            "items": items}  # fmt: skip


@router.get("/route", dependencies=[Reader])
def route(
    day: date,
    tanker_id: Annotated[str, Query(min_length=1, max_length=16)],
    plans: Plans,
    store: Bookings,
    deliveries_: Deliveries,
    ledger: Ledger,
) -> dict[str, Any]:
    plan_id = _approved(plans, day)
    routes = routes_of(_record(plans, plan_id))
    tanker = next((t for t in routes["tankers"] if t["tanker_id"] == tanker_id), None)
    if tanker is None:
        raise HTTPException(404, f"Tanker {tanker_id} has no trips in plan {plan_id}")
    trips = []
    for x in tanker["trips"]:
        booking = None
        if booking_dispatch.is_real(x.get("booking_id")):
            row = store.get(x["booking_id"])
            if row is not None:
                booking = booking_routes._view(store, deliveries_, ledger, row)
        trips.append(
            {
                "n": x["n"],
                "kind": x["kind"],
                "name": x["name"],
                "depart": x["depart"],
                "arrive": x["arrive"],
                "back": x["back"],
                "km": x["km"],
                "leg_basis": x["leg_basis"],
                # where the trip goes, for the driver's map (a booking uses the booker's place)
                "group": x["group"],
                "lat": booking["lat"] if booking else x["lat"],
                "lng": booking["lon"] if booking else x["lng"],
                # a booking made through JalLekha: where to go and how to prove the delivery
                "booking": booking,
                "stop_id": booking_dispatch.stop_id_for(x["booking_id"]) if booking else None,
            }
        )
    station = next(r for r in routes["stations"] if r["station_id"] == tanker["station_id"])
    return {
        "day": day.isoformat(),
        "plan_id": plan_id,
        "tanker_id": tanker_id,
        "station_id": tanker["station_id"],
        "station": {
            "station_id": station["station_id"],
            "lat": station["lat"],
            "lng": station["lng"],
        },
        "finish": tanker["finish"],
        "km": tanker["km"],
        "trips": trips,
    }
