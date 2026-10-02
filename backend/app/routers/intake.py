"""Thin intake endpoints (F14, T4): offline batch, SMS webhook, missed-call webhook.

The work is in `services/intake_pipeline.py`. Voice upload (multipart) and authentication come
with T10. Responses never echo phone numbers.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.config.intake import INTAKE_CONFIG
from app.services.intake_pipeline import IntakeService, default_service

router = APIRouter(prefix="/intake", tags=["intake"])


def get_intake_service() -> IntakeService:
    return default_service()


Service = Annotated[IntakeService, Depends(get_intake_service)]


class BatchRequest(BaseModel):
    items: list[dict[str, Any]] = Field(max_length=INTAKE_CONFIG.max_batch_items)


@router.post("/batch")
def batch(body: BatchRequest, service: Service) -> dict[str, Any]:
    """App / field-worker / offline items; one status per item, in the same order."""
    return {"results": [asdict(result) for result in service.receive_batch(body.items)]}


@router.post("/sms")
def sms_webhook(payload: dict[str, Any], service: Service) -> dict[str, Any]:
    """Inbound SMS from any gateway (sender and text field names vary by provider)."""
    return asdict(service.receive_sms(payload))


@router.post("/missed-call")
def missed_call(payload: dict[str, Any], service: Service) -> dict[str, Any]:
    """Missed call: creates a no-water complaint (ASSUMED) and asks back for the location."""
    return asdict(service.receive_missed_call(payload))
