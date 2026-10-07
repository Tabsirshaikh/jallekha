"""Booking endpoints: a resident (or a field worker for them) books a tanker; an officer lists the
bookings and checks hospital / care-home / school claims. services/bookings.py has the rules.

Responses never carry the phone number (only its last 2 digits). A booking's progress after it
is given a tanker (on the way, code checked, delivered) is read from its delivery (F12).
"""

from __future__ import annotations

from datetime import date
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from app.auth import require_roles
from app.config.api import ApiConfig
from app.models import Booking
from app.routers import deliveries
from app.routers.common import invalid, not_found, page
from app.routers.stores import DeliveryStore, get_booking_store, get_delivery_store
from app.services import bookings as bk
from app.services import delivery as dl
from app.services.ledger_store import StoredLedger

router = APIRouter(prefix="/bookings", tags=["bookings"])

Store = Annotated[bk.BookingStore, Depends(get_booking_store)]
Deliveries = Annotated[DeliveryStore, Depends(get_delivery_store)]
# Reading a booking can decide its delivery's outcome (reply window closed): logged on the
# deliveries' ledger, the same dependency the delivery routes use (overridden in tests).
Ledger = Annotated[StoredLedger, Depends(deliveries.get_delivery_ledger)]
Booker = Depends(require_roles("resident", "field_worker"))
Anyone = Depends(require_roles("resident", "field_worker", "officer", "driver"))
Officer = Depends(require_roles("officer"))
Offset = Annotated[int, Query(ge=0)]
Limit = Annotated[int, Query(ge=1, le=ApiConfig.max_limit)]

TIER_LABEL = {
    0: "First: hospital or care home",
    1: "Second: no water at home",
    2: "Fair turns with everyone else",
}


class NewBooking(BaseModel):
    model_config = ConfigDict(extra="forbid")
    lat: float = Field(ge=-90, le=90, allow_inf_nan=False)
    lon: float = Field(ge=-180, le=180, allow_inf_nan=False)
    category: str
    water_at_home: Literal["yes", "no", "unknown"] = "unknown"
    phone: str
    language: str = "en"
    channel: Literal["app", "field_worker"] = "app"
    facility_name: str | None = Field(default=None, max_length=120)
    basis: Literal["REAL", "SYNTHETIC"] = "REAL"


class ClaimCheck(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: Literal["VERIFIED", "REJECTED"]
    officer_id: str = Field(min_length=1, max_length=64)
    reason: str = Field(min_length=1, max_length=500)


def delivery_of(
    store: DeliveryStore, row: Booking, ledger: StoredLedger
) -> dl.DeliveryState | None:
    """The latest delivery at the booking's stop, its outcome decided if it can be now."""
    if not row.stop_id:
        return None
    found = store.list_deliveries(stop_id=row.stop_id)
    if not found:
        return None
    return deliveries._closed(store, found[-1], ledger)


def progress(row: Booking, delivery: dl.DeliveryState | None, expired: bool) -> str:
    """WAITING, EXPIRED, ASSIGNED, ON_THE_WAY, CHECKING (code verified, waiting for the
    resident's answer), DELIVERED (Confirmed), NOT_CONFIRMED or CANCELLED."""
    if row.status == "CANCELLED":
        return "CANCELLED"
    if row.status == "WAITING":
        return "EXPIRED" if expired else "WAITING"
    if delivery is None:
        return "ASSIGNED"
    if delivery.outcome is not None:
        return "DELIVERED" if delivery.outcome.outcome == "Confirmed" else "NOT_CONFIRMED"
    return "CHECKING" if delivery.otp_verified else "ON_THE_WAY"


def view(row: Booking, delivery: dl.DeliveryState | None, expired: bool) -> dict[str, Any]:
    tier = bk.tier_of(row.category, row.claim_status, row.water_at_home)
    return {
        "booking_id": row.booking_id,
        "arrived_at": bk._aware(row.arrived_at).isoformat(),
        "section": row.section,
        "section_name": row.section.removeprefix("section:"),
        "ward_id": row.ward_id,
        "lat": row.lat,
        "lon": row.lon,
        "category": row.category,
        "facility_name": row.facility_name,
        "water_at_home": row.water_at_home,
        "claim_status": row.claim_status,
        "tier": tier,
        "priority": TIER_LABEL[tier],
        "status": progress(row, delivery, expired),
        "plan_id": row.plan_id,
        "tanker_id": row.tanker_id,
        "station_id": row.station_id,
        "trip_n": row.trip_n,
        "depart": row.depart,
        "arrive": row.arrive,
        "delivery": None
        if delivery is None
        else {
            "delivery_id": delivery.delivery_id,
            "otp_issued": delivery.otp is not None,
            "otp_verified": delivery.otp_verified,
            "asked_residents": len(delivery.sampled_resident_ids),
            "replies": len(delivery.responses),
            "outcome": delivery.outcome.outcome if delivery.outcome else None,
            "counts_toward_debt": dl.counts_toward_debt(delivery.outcome.outcome)
            if delivery.outcome
            else None,
        },
        "phone_last2": row.phone[-2:],
        "channel": row.channel,
        "basis": row.basis,
    }


def _view(
    store: bk.BookingStore, deliveries_: DeliveryStore, ledger: StoredLedger, row: Booking
) -> dict[str, Any]:
    return view(row, delivery_of(deliveries_, row, ledger), store.expired(row))


@router.get("/locate", dependencies=[Anyone])
def locate(
    store: Store,
    lat: Annotated[float, Query(ge=-90, le=90)],
    lon: Annotated[float, Query(ge=-180, le=180)],
) -> dict[str, Any]:
    """Which section (and ward) a point is in, so the booking form can show it before sending."""
    place = store.locate(lat, lon)
    if place is None:
        return {"inside": False, "section": None, "section_name": None, "ward_id": None,
                "ward_name": None}  # fmt: skip
    return {
        "inside": True,
        "section": place.section,
        "section_name": place.name,
        "ward_id": place.ward_id,
        "ward_name": place.ward_name,
        "basis": "DERIVED (approximate section areas; HMWSSB publishes no section boundaries)",
    }


@router.post("", dependencies=[Booker], status_code=201)
def create(body: NewBooking, store: Store, deliveries_: Deliveries, ledger: Ledger) -> Any:
    try:
        row = store.create(**body.model_dump())
    except bk.BookingConflict as exc:
        raise HTTPException(409, str(exc)) from exc
    except bk.BookingRefused as exc:
        return invalid(str(exc))
    return _view(store, deliveries_, ledger, row)


@router.get("", dependencies=[Officer])
def list_bookings(
    store: Store,
    deliveries_: Deliveries,
    ledger: Ledger,
    day: date | None = None,
    status: Literal["WAITING", "ASSIGNED", "CANCELLED"] | None = None,
    claim: Literal["NONE", "CLAIMED", "VERIFIED", "REJECTED"] | None = None,
    section: str | None = None,
    offset: Offset = 0,
    limit: Limit = ApiConfig.default_limit,
) -> dict[str, Any]:
    rows = store.list(day=day, status=status, section=section, claim=claim)
    items = [_view(store, deliveries_, ledger, r) for r in reversed(rows)]  # newest first
    return {
        **page(items, offset, limit),
        "claims_to_check": sum(1 for r in rows if r.claim_status == "CLAIMED"),
    }


@router.get("/{booking_id}", dependencies=[Anyone])
def get_booking(
    booking_id: str, store: Store, deliveries_: Deliveries, ledger: Ledger
) -> dict[str, Any]:
    row = store.get(booking_id)
    if row is None:
        raise not_found(f"Booking {booking_id}")
    return _view(store, deliveries_, ledger, row)


@router.post("/{booking_id}/claim", dependencies=[Officer])
def check_claim(
    booking_id: str, body: ClaimCheck, store: Store, deliveries_: Deliveries, ledger: Ledger
) -> Any:
    try:
        row = store.check_claim(booking_id, body.decision, body.officer_id, body.reason)
    except KeyError as exc:
        raise not_found(f"Booking {booking_id}") from exc
    except bk.BookingConflict as exc:
        raise HTTPException(409, str(exc)) from exc
    except bk.BookingRefused as exc:
        return invalid(str(exc))
    return _view(store, deliveries_, ledger, row)
