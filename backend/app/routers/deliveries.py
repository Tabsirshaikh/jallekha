"""Delivery-proof endpoints (T10 over T3's `services/delivery.py`). docs/api_shapes.md section 13.

Stops (with their 2-3 registered representatives and residents) and delivery states live in the
in-memory `DeliveryStore` (no delivery store on `main`, OPEN). Responses never carry phone
numbers, the OTP, its nonce or its hash. `outcome_status` is `pending` until the outcome is
decided (reply window closed, or every sampled resident replied).
"""

from __future__ import annotations

import re
from dataclasses import asdict
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.auth import Config, require_gateway, require_roles
from app.routers.common import invalid, not_found
from app.routers.stores import DeliveryStore, get_delivery_store
from app.services import delivery as dl
from app.services import ledger_store
from app.services.ledger_store import StoredLedger
from app.services.sms import SmsSender, get_sms_sender

router = APIRouter(prefix="/deliveries", tags=["deliveries"])

Driver = Depends(require_roles("driver"))
Store = Annotated[DeliveryStore, Depends(get_delivery_store)]


def get_delivery_ledger() -> StoredLedger:
    return ledger_store.get_ledger()


def get_delivery_sms() -> SmsSender:
    return get_sms_sender()


Ledger = Annotated[StoredLedger, Depends(get_delivery_ledger)]
Sms = Annotated[SmsSender, Depends(get_delivery_sms)]


class Start(BaseModel):
    delivery_id: str
    stop_id: str
    driver_id: str


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
    state = store.deliveries.get(delivery_id)
    if state is None:
        raise not_found(f"Delivery {delivery_id}")
    return state


def _otp_key(config: Any) -> str:
    if not config.otp_key:
        raise HTTPException(503, "OTP_HMAC_KEY is not set")
    return config.otp_key


@router.post("", dependencies=[Driver])
def start(body: Start, store: Store, ledger: Ledger) -> Any:
    stop = store.stops.get(body.stop_id)
    if stop is None:
        raise not_found(f"Stop {body.stop_id}")
    if body.delivery_id in store.deliveries:
        raise HTTPException(409, f"Delivery {body.delivery_id} already exists")
    try:
        state = dl.start_delivery(
            body.delivery_id, stop.stop_id, stop.lat, stop.lon, body.driver_id,
            stop.representatives, ledger, datetime.now(UTC),
        )  # fmt: skip
    except ValueError as exc:
        return invalid(str(exc))
    store.deliveries[state.delivery_id] = state
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
    store.deliveries[delivery_id] = state
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
        stop = store.stops[state.stop_id]
        state = dl.send_resident_check(state, stop.residents, state.delivery_id, sms, ledger, now)
    store.deliveries[delivery_id] = state
    return {
        "result": result,
        "location": asdict(dl.locate(state, body.lat, body.lon)),
        "delivery": view(state),
    }


def _digits(phone: str) -> str:
    digits = re.sub(r"\D", "", phone)
    return digits[-10:]


@router.post("/{delivery_id}/replies", dependencies=[Depends(require_gateway)])
def resident_reply(delivery_id: str, payload: dict[str, Any], store: Store, ledger: Ledger) -> Any:
    sender, text = payload.get("from"), payload.get("text")
    if not isinstance(sender, str) or not isinstance(text, str):
        return invalid("A reply needs `from` and `text`")
    state = _state(store, delivery_id)
    stop = store.stops[state.stop_id]
    resident = next((r for r in stop.residents if _digits(r.phone) == _digits(sender)), None)
    counted = False
    if resident is not None:
        state, counted = dl.record_response(state, resident.id, text, ledger, datetime.now(UTC))
        store.deliveries[delivery_id] = state
    return {
        "replies": [
            {"resident_id": resident.id if resident else None, "text": text, "counted": counted}
        ],
        "delivery": view(state),
    }


@router.get("/{delivery_id}", dependencies=[Depends(require_roles("officer", "driver"))])
def get_delivery(delivery_id: str, store: Store, ledger: Ledger) -> dict[str, Any]:
    state = dl.close_delivery(_state(store, delivery_id), ledger, datetime.now(UTC))
    store.deliveries[delivery_id] = state
    outcome = state.outcome.outcome if state.outcome else None
    return {
        **view(state),
        "counts_toward_debt": dl.counts_toward_debt(outcome) if outcome else None,
    }
