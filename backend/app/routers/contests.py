"""Contest and reply endpoints (T10 over T7's `ContestService`). docs/api_shapes.md section 11.

A service status of `invalid` is 422, `not_found` 404, `already_replied` 409 (agreed with P4).

Identity: a resident or councillor token that carries a user id files as that id (a different
`filed_by` is 403) and sees only its own contests; the stored role is the token's role. The
officer, and the dev token, see every contest.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth import Principal, require_roles
from app.config.api import ApiConfig
from app.db import create_all, make_engine
from app.routers.common import invalid, not_found
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


Filer = Annotated[Principal, Depends(require_roles("resident", "councillor"))]
Reader = Annotated[Principal, Depends(require_roles("officer", "resident", "councillor"))]
Offset = Annotated[int, Query(ge=0)]
Limit = Annotated[int, Query(ge=1, le=ApiConfig.max_limit)]


def _own_id(principal: Principal) -> str | None:
    """The user id a resident or councillor may read as; None for the officer and dev token,
    who read every contest. A resident token without a user id cannot be told apart from
    another resident, so it reads nothing (403) rather than everything."""
    if principal.role in ("officer", "dev"):
        return None
    if principal.user_id is None:
        raise HTTPException(403, "This token is not bound to a user id, so it has no own contests")
    return principal.user_id


# Councillors may also file contests (F16); that role is OPEN, owner to confirm.
@router.post("/contests")
def file_contest(payload: dict[str, Any], service: Service, principal: Filer) -> Any:
    data = dict(payload)
    if principal.user_id is not None:
        given = data.get("filed_by")
        if given is not None and given != principal.user_id:
            raise HTTPException(403, "filed_by must be the user id of the calling token")
        data["filed_by"] = principal.user_id
    if principal.role != "dev":
        data["role"] = principal.role  # the caller's role, never a supplied one
    return _answer(service.file(data))


@router.post("/contests/{contest_id}/reply", dependencies=[Depends(require_roles("officer"))])
def reply(contest_id: str, payload: dict[str, Any], service: Service) -> Any:
    return _answer(service.reply(contest_id, payload))


@router.get("/contests")
def list_contests(
    service: Service,
    principal: Reader,
    status: Literal["open", "replied"] | None = None,
    target_type: Literal["ward", "booking"] | None = None,
    target_id: str | None = None,
    offset: Offset = 0,
    limit: Limit = ApiConfig.default_limit,
) -> dict[str, Any]:
    items, total = service.list_contests(
        status=status,
        target_type=target_type,
        target_id=target_id,
        filed_by=_own_id(principal),
        offset=offset,
        limit=limit,
    )
    return {"total": total, "offset": offset, "limit": limit, "items": items}


@router.get("/contests/{contest_id}")
def get_contest(contest_id: str, service: Service, principal: Reader) -> dict[str, Any]:
    own = _own_id(principal)
    contest = service.get_contest(contest_id)
    # Someone else's contest looks the same as a missing one.
    if contest is None or (own is not None and contest["filed_by"] != own):
        raise not_found("Contest")
    return contest
