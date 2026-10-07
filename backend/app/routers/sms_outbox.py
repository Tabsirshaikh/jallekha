"""SMS test mode (`SMS_PROVIDER=outbox`): read the messages "sent" to a phone number and answer
"did you get water?" from the screen, so the delivery-code flow (F12) can be tried end to end on
one machine without an SMS company. Off unless SMS_PROVIDER=outbox, and refused whenever sign-in
is required (AUTH_REQUIRED), so it cannot run on a real deployment by accident. English wording
only: the real per-language templates belong to the SMS provider work.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.auth import Config
from app.routers import deliveries
from app.routers.stores import DeliveryStore, get_delivery_store
from app.services import delivery as dl
from app.services import sms
from app.services.ledger_store import StoredLedger

router = APIRouter(prefix="/sms", tags=["sms-test-mode"])

Deliveries = Annotated[DeliveryStore, Depends(get_delivery_store)]
Ledger = Annotated[StoredLedger, Depends(deliveries.get_delivery_ledger)]

TEXT = {
    dl.OTP_TEMPLATE: "JalLekha: your tanker delivery code is {code}. Tell it to the driver at your "
    "door. Valid {valid_minutes} minutes.",
    dl.RESIDENT_CHECK_TEMPLATE: "JalLekha: did you get water from the tanker today? Reply 1 for "
    "yes, 2 for no.",
}


def get_outbox() -> sms.OutboxSmsSender | None:
    return sms.outbox()


Outbox = Annotated[sms.OutboxSmsSender | None, Depends(get_outbox)]


def _enabled(outbox: sms.OutboxSmsSender | None, config: Any) -> sms.OutboxSmsSender:
    if outbox is None:
        raise HTTPException(404, "SMS test mode is off (set SMS_PROVIDER=outbox)")
    if config.auth_required:
        raise HTTPException(404, "SMS test mode runs only without sign-in (AUTH_REQUIRED unset)")
    return outbox


class Reply(BaseModel):
    phone: str = Field(min_length=8, max_length=20)
    text: str = Field(min_length=1, max_length=10)


@router.get("/test-mode")
def test_mode(outbox: Outbox, config: Config) -> dict[str, Any]:
    return {"test_mode": outbox is not None and not config.auth_required}


@router.get("/outbox")
def read(
    outbox: Outbox, config: Config, phone: Annotated[str, Query(min_length=8, max_length=20)]
) -> dict[str, Any]:
    box = _enabled(outbox, config)
    key = deliveries.phone_key(phone)
    items = [
        {
            "at": e.at.isoformat(),
            "template": e.message.template_key,
            "text": TEXT.get(e.message.template_key, e.message.template_key).format(
                **dict(e.message.params)
            ),
            "code": e.message.params.get("code"),
        }
        for e in reversed(box.to(key, deliveries.phone_key))
    ]
    return {"test_mode": True, "basis": "TEST MODE: nothing was sent by SMS", "items": items}


@router.post("/outbox/reply")
def reply(
    body: Reply, outbox: Outbox, config: Config, store: Deliveries, ledger: Ledger
) -> dict[str, Any]:
    """Answer the latest open "did you get water?" question asked of this phone number, as the
    SMS gateway would (routers/deliveries.resident_reply)."""
    _enabled(outbox, config)
    key = deliveries.phone_key(body.phone)
    for state in reversed(store.list_deliveries()):
        if state.outcome is not None or state.sampled_at is None:
            continue
        stop = store.get_stop(state.stop_id)
        resident = next(
            (r for r in (stop.residents if stop else ()) if deliveries.phone_key(r.phone) == key),
            None,
        )
        if resident is None or resident.id not in state.sampled_resident_ids:
            continue
        with deliveries._locks.hold(state.delivery_id):
            fresh = store.get_delivery(state.delivery_id) or state
            fresh, counted = dl.record_response(
                fresh, resident.id, body.text, ledger, datetime.now(UTC)
            )
            store.put_delivery(fresh)
        closed = deliveries._closed(store, fresh, ledger)
        return {"counted": counted, "delivery": deliveries.view(closed)}
    raise HTTPException(404, "No open question was asked of this phone number")
