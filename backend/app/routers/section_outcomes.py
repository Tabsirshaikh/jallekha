"""Officer and field-worker observations of exact-section booking flags."""

from datetime import date, datetime
from functools import lru_cache
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field

from app.auth import Principal, require_roles
from app.config.api import ApiConfig
from app.config.section_outcomes import SECTION_OUTCOME_CONFIG
from app.routers.common import csv_rows, get_now, invalid, page, typed
from app.routers.evidence import Limit, Offset
from app.routers.stores import DeliveryStore, get_delivery_store
from app.services.ledger_store import get_ledger
from app.services.section_outcomes import SectionOutcomeStore
from app.services.section_plan import IST
from app.services.supply_reviews import SupplyReviewStore, current_sections

router = APIRouter(prefix="/field-checks", tags=["field checks"])
Actor = Annotated[Principal, Depends(require_roles("officer", "field_worker"))]


def candidates():
    return {
        r["section_id"]: r
        for r in (typed(raw) for raw in csv_rows("data/derived/underserved/section_checks.csv"))
        if r["field_check_candidate"]
    }


@lru_cache(maxsize=1)
def get_section_outcome_store():
    ledger = get_ledger()
    return SectionOutcomeStore(ledger.engine, ledger, candidates)


Store = Annotated[SectionOutcomeStore, Depends(get_section_outcome_store)]


def get_supply_review_store(store: Store):
    return SupplyReviewStore(store.engine, store.ledger)


Reviews = Annotated[SupplyReviewStore, Depends(get_supply_review_store)]


class SupplyInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: UUID
    section_id: str
    checked_on: date
    supply: Literal["adequate", "insufficient", "unavailable", "unknown"]
    tanker_share: float = Field(ge=0, le=1, allow_inf_nan=False)
    records_complete: bool = False
    booking_reason: Literal["other_supply", "access_difficulty", "unclear"]
    note: str = Field(min_length=1, max_length=SECTION_OUTCOME_CONFIG.maximum_note_chars)


@router.post("/supply-reviews")
def supply_review(
    payload: SupplyInput, actor: Actor, reviews: Reviews, now: Annotated[datetime, Depends(get_now)]
):
    if payload.checked_on >= now.astimezone(IST).date():
        return invalid("Verify a completed day, not today or a future day")
    sections = {r["section_id"] for r in csv_rows("data/derived/underserved/section_checks.csv")}
    if payload.section_id not in sections:
        return invalid("Unknown section")
    if not payload.note.strip():
        return invalid("Describe the supply and delivery-record checks")
    if (
        (payload.supply == "adequate" and payload.tanker_share != 0)
        or (payload.supply == "unavailable" and payload.tanker_share != 1)
        or (payload.supply == "insufficient" and not 0 < payload.tanker_share < 1)
    ):
        return invalid("Tanker share must agree with the verified alternative supply")
    try:
        return reviews.record(payload.model_dump(mode="json"), actor.user_id or actor.role)
    except ValueError as exc:
        return invalid(str(exc))


@router.get("/weekly-priority")
def weekly_priority_view(
    actor: Actor,
    reviews: Reviews,
    deliveries: Annotated[DeliveryStore, Depends(get_delivery_store)],
    now: Annotated[datetime, Depends(get_now)],
    section_id: str | None = None,
):
    values = current_sections(now.astimezone(IST).date(), reviews, deliveries)
    rows = [v for v in values.values() if section_id is None or v["section_id"] == section_id]
    return {"basis": "DERIVED_APPROXIMATE", "as_of": now.isoformat(), "items": rows}


class OutcomeInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: UUID
    section_id: str
    could_not_book: Literal["yes", "no", "unclear"]
    checked_on: date
    note: str = Field(default="", max_length=SECTION_OUTCOME_CONFIG.maximum_note_chars)


@router.get("/sections")
def flagged_sections(
    actor: Actor, store: Store, offset: Offset = 0, limit: Limit = ApiConfig.default_limit
) -> dict[str, Any]:
    latest = {}
    for outcome in store.list():
        if not outcome["ledger_missing"]:
            latest.setdefault((outcome["section_id"], outcome["period_year"]), outcome)
    rows = [
        {**r, "latest_outcome": latest.get((r["section_id"], r["period_year"]))}
        for r in candidates().values()
    ]
    return {"basis": "DERIVED", **page(rows, offset, limit)}


@router.post("/outcomes")
def record_outcome(payload: OutcomeInput, actor: Actor, store: Store):
    try:
        return store.record(
            payload.section_id,
            payload.could_not_book,
            payload.checked_on,
            payload.note,
            actor.user_id or actor.role,
            str(payload.id),
        )
    except ValueError as exc:
        return invalid(str(exc))


@router.get("/outcomes")
def outcomes(
    actor: Actor, store: Store, offset: Offset = 0, limit: Limit = ApiConfig.default_limit
):
    return page(store.list(), offset, limit)


@router.get("/summary")
def summary(actor: Actor, store: Store):
    return store.summary()
