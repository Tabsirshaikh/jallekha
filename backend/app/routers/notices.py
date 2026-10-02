"""Thin officer-entry endpoint for HMWSSB supply notices (F15, T5).

The work is in `services/notices.py`. Authentication comes with T10.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from fastapi.encoders import jsonable_encoder

from app.services.notices import NoticeService, default_service

router = APIRouter(prefix="/notices", tags=["notices"])


def get_notice_service() -> NoticeService:
    return default_service()


Service = Annotated[NoticeService, Depends(get_notice_service)]


@router.post("")
def enter_notice(payload: dict[str, Any], service: Service) -> dict[str, Any]:
    """Officer entry: matched wards create an outage (A5); flagged areas need an officer."""
    return jsonable_encoder(asdict(service.enter(payload)))
