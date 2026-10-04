"""Delivery-proof endpoints (T10 over T3's `services/delivery.py`). docs/api_shapes.md section 13.

Stops (with their 2-3 registered representatives and residents, `POST /stops`) and delivery
states live in the database (`DeliveryStore`, services/delivery_store.py), so they survive a
restart. Responses never carry phone numbers, the OTP, its nonce or its hash. `outcome_status`
is `pending` until the outcome is decided (reply window closed, or every sampled resident
replied).
"""

from __future__ import annotations

import re
from dataclasses import asdict
from datetime import UTC, datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.auth import Config, require_gateway, require_roles
from app.config.api import ApiConfig
from app.routers.common import invalid, not_found, page
from app.routers.stores import DeliveryStore, Stop, get_delivery_store
from app.services import delivery as dl
from app.services import ledger_store
from app.services.ledger_store import StoredLedger
from app.services.sms import SmsSender, get_sms_sender

router = APIRouter(prefix="/deliveries", tags=["deliveries"])

Driver = Depends(require_roles("driver"))
Reader = Depends(require_roles("officer", "driver"))
Store = Annotated[DeliveryStore, Depends(get_delivery_store)]
Offset = Annotated[int, Query(ge=0)]
Limit = Annotated[int, Query(ge=1, le=ApiConfig.max_limit)]
OutcomeStatus = Literal["pending", "Confirmed", "Disputed", "Unconfirmed", "Failed"]


def get_delivery_ledger() -> StoredLedger:
    return ledger_store.get_ledger()


def get_delivery_sms() -> SmsSender:
    return get_sms_sender()


Ledger = Annotated[StoredLedger, Depends(get_delivery_ledger)]
Sms = Annotated[SmsSender, Depends(get_delivery_sms)]


class Start(BaseModel):
    # Column widths: delivery.id String(36), stop_id and driver_id String(64) (app/models).
    delivery_id: str = Field(min_length=1, max_length=36)
    stop_id: str = Field(min_length=1, max_length=64)
    driver_id: str = Field(min_length=1, max_length=64)


class OtpRequest(BaseModel):
    representative_id: str


class OtpVerify(BaseModel):
    code: str
    lat: float | None = None
    lon: float | None = None


def view(s: dl.DeliveryState) -> dict[str, Any]:
    return {
        "delivery_id": s.delivery_id,
        "stop_id": s.stop_id,
        "driver_id": s.driver_id,
        "started_at": s.started_at,
        "geofence_radius_m": s.geofence_radius_m,
        "otp_issued": s.otp is not None,
        "otp_expires_at": s.otp.expires_at if s.otp else None,
        "otp_digits": s.otp.digits if s.otp else None,
        "wrong_attempts": s.wrong_attempts,
        "outside_tries": s.outside_tries,
        "otp_verified": s.otp_verified,
        "sampled_residents": len(s.sampled_resident_ids),
        "replies": len(s.responses),
        "outcome_status": s.outcome.outcome if s.outcome else "pending",
        "outcome": asdict(s.outcome) if s.outcome else None,
    }


def _state(store: DeliveryStore, delivery_id: str) -> dl.DeliveryState:
    state = store.get_delivery(delivery_id)
    if state is None:
        raise not_found(f"Delivery {delivery_id}")
    return state


def _stop(store: DeliveryStore, stop_id: str) -> Stop:
    stop = store.get_stop(stop_id)
    if stop is None:
        raise not_found(f"Stop {stop_id}")
    return stop


def _otp_key(config: Any) -> str:
    if not config.otp_key:
        raise HTTPException(503, "OTP_HMAC_KEY is not set")
    return config.otp_key


@router.post("", dependencies=[Driver])
def start(body: Start, store: Store, ledger: Ledger) -> Any:
    stop = _stop(store, body.stop_id)
    if store.has_delivery(body.delivery_id):
        raise HTTPException(409, f"Delivery {body.delivery_id} already exists")
    try:
        state = dl.start_delivery(
            body.delivery_id, stop.stop_id, stop.lat, stop.lon, body.driver_id,
            stop.representatives, ledger, datetime.now(UTC),
        )  # fmt: skip
    except ValueError as exc:
        return invalid(str(exc))
    store.put_delivery(state)
    return view(state)


@router.post("/{delivery_id}/otp", dependencies=[Driver])
def request_otp(
    delivery_id: str, body: OtpRequest, store: Store, ledger: Ledger, sms: Sms, config: Config
) -> Any:
    state = _state(store, delivery_id)
    try:
        state = dl.request_otp(
            state, body.representative_id, _otp_key(config), sms, ledger, datetime.now(UTC)
        )
    except ValueError as exc:
        return invalid(str(exc))
    store.put_delivery(state)
    return view(state)


@router.post("/{delivery_id}/otp/verify", dependencies=[Driver])
def verify_otp(
    delivery_id: str, body: OtpVerify, store: Store, ledger: Ledger, sms: Sms, config: Config
) -> dict[str, Any]:
    state = _state(store, delivery_id)
    now = datetime.now(UTC)
    state, result = dl.verify_otp(
        state, body.code, body.lat, body.lon, _otp_key(config), ledger, now
    )
    if result == "verified":  # the resident check goes out as soon as the OTP is verified
        stop = _stop(store, state.stop_id)
        state = dl.send_resident_check(state, stop.residents, state.delivery_id, sms, ledger, now)
    store.put_delivery(state)
    return {
        "result": result,
        "location": asdict(dl.locate(state, body.lat, body.lon)),
        "delivery": view(state),
    }


def phone_key(phone: str) -> str:
    """Replies are matched on the last 10 digits of the sender's number."""
    digits = re.sub(r"\D", "", phone)
    return digits[-10:]


@router.post("/{delivery_id}/replies", dependencies=[Depends(require_gateway)])
def resident_reply(delivery_id: str, payload: dict[str, Any], store: Store, ledger: Ledger) -> Any:
    sender, text = payload.get("from"), payload.get("text")
    if not isinstance(sender, str) or not isinstance(text, str):
        return invalid("A reply needs `from` and `text`")
    state = _state(store, delivery_id)
    stop = _stop(store, state.stop_id)
    resident = next((r for r in stop.residents if phone_key(r.phone) == phone_key(sender)), None)
    counted = False
    if resident is not None:
        state, counted = dl.record_response(state, resident.id, text, ledger, datetime.now(UTC))
        store.put_delivery(state)
    return {
        "replies": [
            {"resident_id": resident.id if resident else None, "text": text, "counted": counted}
        ],
        "delivery": view(state),
    }


def _closed(store: DeliveryStore, state: dl.DeliveryState, ledger: Ledger) -> dl.DeliveryState:
    """Decide the outcome if it can be decided now, and save it (once)."""
    closed = dl.close_delivery(state, ledger, datetime.now(UTC))
    if closed != state:
        store.put_delivery(closed)
    return closed


@router.get("", dependencies=[Reader])
def list_deliveries(
    store: Store,
    ledger: Ledger,
    driver_id: str | None = None,
    stop_id: str | None = None,
    outcome_status: OutcomeStatus | None = None,
    offset: Offset = 0,
    limit: Limit = ApiConfig.default_limit,
) -> dict[str, Any]:
    """Deliveries in start order; outcomes that can be decided now are decided first."""
    items = [
        view(_closed(store, s, ledger))
        for s in store.list_deliveries(driver_id=driver_id, stop_id=stop_id)
    ]
    if outcome_status is not None:
        items = [i for i in items if i["outcome_status"] == outcome_status]
    return page(items, offset, limit)


@router.get("/{delivery_id}", dependencies=[Reader])
def get_delivery(delivery_id: str, store: Store, ledger: Ledger) -> dict[str, Any]:
    state = _closed(store, _state(store, delivery_id), ledger)
    outcome = state.outcome.outcome if state.outcome else None
    return {
        **view(state),
        "counts_toward_debt": dl.counts_toward_debt(outcome) if outcome else None,
    }
