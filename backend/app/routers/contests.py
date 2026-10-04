"""Contest and reply endpoints (T10 over T7's `ContestService`). docs/api_shapes.md section 11.

A service status of `invalid` is 422, `not_found` 404, `already_replied` 409 (agreed with P4).
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException

from app.auth import require_roles
from app.db import create_all, make_engine
from app.routers.common import invalid
from app.services import ledger_store
from app.services.contest import ContestResult, ContestService

router = APIRouter(tags=["contests"])

_default: ContestService | None = None


def get_contest_service() -> ContestService:
    global _default
    if _default is None:
        engine = make_engine()
        create_all(engine)
        _default = ContestService(engine, ledger=ledger_store.get_ledger())
    return _default


Service = Annotated[ContestService, Depends(get_contest_service)]


def _answer(result: ContestResult) -> Any:
    if result.status == "invalid":
        return invalid(result.error)
    if result.status == "not_found":
        raise HTTPException(404, result.error or "Contest not found")
    if result.status == "already_replied":
        raise HTTPException(409, result.error or "This contest already has a reply")
    return asdict(result)


# Councillors may also file contests (F16); that role is OPEN, owner to confirm.
@router.post("/contests", dependencies=[Depends(require_roles("resident"))])
def file_contest(payload: dict[str, Any], service: Service) -> Any:
    return _answer(service.file(payload))


@router.post("/contests/{contest_id}/reply", dependencies=[Depends(require_roles("officer"))])
def reply(contest_id: str, payload: dict[str, Any], service: Service) -> Any:
    return _answer(service.reply(contest_id, payload))
