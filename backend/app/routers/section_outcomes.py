"""Officer and field-worker observations of exact-section booking flags."""

from datetime import date
from functools import lru_cache
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field

from app.auth import Principal, require_roles
from app.config.api import ApiConfig
from app.config.section_outcomes import SECTION_OUTCOME_CONFIG
from app.routers.common import csv_rows, invalid, page, typed
from app.routers.evidence import Limit, Offset
from app.services.ledger_store import get_ledger
from app.services.section_outcomes import SectionOutcomeStore

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
