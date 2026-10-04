"""Thin officer-entry endpoint for HMWSSB supply notices (F15, T5).

The work is in `services/notices.py`. Officers only (T10); an invalid notice is 422 (agreed with
P4, docs/api_shapes.md).
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from fastapi.encoders import jsonable_encoder

from app.auth import require_roles
from app.routers.common import invalid
from app.services.notices import NoticeService, default_service

router = APIRouter(prefix="/notices", tags=["notices"])


def get_notice_service() -> NoticeService:
    return default_service()


Service = Annotated[NoticeService, Depends(get_notice_service)]


@router.post("", dependencies=[Depends(require_roles("officer"))])
def enter_notice(payload: dict[str, Any], service: Service) -> Any:
    """Officer entry: matched wards create an outage (A5); flagged areas need an officer."""
    result = service.enter(payload)
    if result.status == "invalid":
        return invalid(result.error)
    return jsonable_encoder(asdict(result))
