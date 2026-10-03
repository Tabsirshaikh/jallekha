"""Thin intake endpoints (F14, T4; auth and areas T10): offline batch, SMS webhook, missed call.

The work is in `services/intake_pipeline.py`. Responses never echo phone numbers. Agreed with P4
(docs/api_shapes.md): batch items get their own status; a single invalid report (SMS, missed call)
is 422; reports carry a stable `ward_id` and / or `section_id` checked against P1's area tables,
not a free-text `area_id`. Voice upload needs `python-multipart`, which is not installed (OPEN).
"""

from __future__ import annotations

from dataclasses import asdict
from functools import lru_cache
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.auth import require_gateway, require_roles
from app.config.intake import INTAKE_CONFIG
from app.routers.common import csv_rows, invalid
from app.services.intake_pipeline import IntakeResult, IntakeService, default_service

router = APIRouter(prefix="/intake", tags=["intake"])

WARDS = "data/derived/evidence/ward_evidence.csv"
SECTIONS = "data/derived/crosswalk/section_to_ward_2016.csv"


def get_intake_service() -> IntakeService:
    return default_service()


Service = Annotated[IntakeService, Depends(get_intake_service)]


class BatchRequest(BaseModel):
    items: list[dict[str, Any]] = Field(max_length=INTAKE_CONFIG.max_batch_items)


@lru_cache(maxsize=1)
def _known() -> tuple[frozenset[str], frozenset[str]]:
    return (
        frozenset(r["ward_id"] for r in csv_rows(WARDS)),
        frozenset(r["section"] for r in csv_rows(SECTIONS)),
    )


def _with_area(item: Any) -> tuple[Any, str | None]:
    """Check `ward_id` / `section_id` and pass them to the service as its `area_id` text."""
    if not isinstance(item, dict):
        return item, None  # the service reports the bad item
    if "area_id" in item:
        return item, "area_id is not accepted; send ward_id and / or section_id"
    wards, sections = _known()
    ward, section = item.get("ward_id"), item.get("section_id")
    if ward is not None and ward not in wards:
        return item, f"Unknown ward_id {ward!r}"
    if section is not None and section not in sections:
        return item, f"Unknown section_id {section!r}"
    rest = {k: v for k, v in item.items() if k not in ("ward_id", "section_id")}
    parts = [f"ward:{ward}"] if ward else []
    parts += [f"section:{section}"] if section else []
    if parts:
        rest["area_id"] = ";".join(parts)
    return rest, None


@router.post("/batch", dependencies=[Depends(require_roles("resident", "field_worker"))])
def batch(body: BatchRequest, service: Service) -> dict[str, Any]:
    """App / field-worker / offline items; one status per item, in the same order."""
    results = []
    for item in body.items:
        prepared, error = _with_area(item)
        if error:
            client_id = item.get("client_id") if isinstance(item.get("client_id"), str) else None
            results.append(asdict(IntakeResult("invalid", client_id, error=error)))
        else:
            results.append(asdict(service.receive_json(prepared)))
    return {"results": results}


def _single(result: IntakeResult) -> Any:
    return invalid(result.error) if result.status == "invalid" else asdict(result)


@router.post("/sms", dependencies=[Depends(require_gateway)])
def sms_webhook(payload: dict[str, Any], service: Service) -> Any:
    """Inbound SMS from any gateway (sender and text field names vary by provider)."""
    return _single(service.receive_sms(payload))


@router.post("/missed-call", dependencies=[Depends(require_gateway)])
def missed_call(payload: dict[str, Any], service: Service) -> Any:
    """Missed call: creates a no-water complaint (ASSUMED) and asks back for the location."""
    return _single(service.receive_missed_call(payload))
