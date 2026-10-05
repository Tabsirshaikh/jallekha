"""Stop endpoints for delivery proof (F12): an officer registers a stop, officers and drivers read.

A stop carries its 2-3 representatives (who receive the delivery OTP) and its residents (from
whom 3-5 are sampled after each delivery). Phone numbers are stored (services/delivery_store.py)
and never returned: a response shows counts and, for representatives, whom the driver picks for
the OTP, the last 2 digits. Request errors never echo submitted values, so a mistyped phone
number is not sent back either.
"""

from __future__ import annotations

import re
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    ValidationError,
    field_validator,
    model_validator,
)

from app.auth import require_roles
from app.config.access import ACCESS_CONFIG
from app.config.api import ApiConfig
from app.config.stops import STOP_CONFIG
from app.config.trust import TRUST_CONFIG
from app.errors import error_response
from app.routers.common import invalid, not_found, page
from app.routers.deliveries import phone_key
from app.routers.stores import DeliveryStore, Stop, get_delivery_store
from app.services import delivery as dl
from app.services import ward_locate
from app.services.delivery_store import StopConflict

router = APIRouter(prefix="/stops", tags=["stops"])

Store = Annotated[DeliveryStore, Depends(get_delivery_store)]
Offset = Annotated[int, Query(ge=0)]
Limit = Annotated[int, Query(ge=1, le=ApiConfig.max_limit)]


StopId = Annotated[
    str,
    StringConstraints(
        min_length=1, max_length=STOP_CONFIG.stop_id_max, pattern=STOP_CONFIG.id_pattern
    ),
]
RepresentativeId = Annotated[
    str,
    StringConstraints(
        min_length=1, max_length=STOP_CONFIG.representative_id_max, pattern=STOP_CONFIG.id_pattern
    ),
]
ResidentId = Annotated[
    str,
    StringConstraints(
        min_length=1, max_length=STOP_CONFIG.resident_id_max, pattern=STOP_CONFIG.id_pattern
    ),
]


class Person(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: ResidentId
    phone: str
    language: str

    @field_validator("phone")
    @classmethod
    def _phone(cls, value: str) -> str:
        if not re.fullmatch(STOP_CONFIG.phone_pattern, value):
            raise ValueError("phone must be an E.164 number: + then 8-15 digits, nothing else")
        return value

    @field_validator("language")
    @classmethod
    def _language(cls, value: str) -> str:
        if value not in ACCESS_CONFIG.supported_languages:
            raise ValueError(f"language must be one of {list(ACCESS_CONFIG.supported_languages)}")
        return value


class RepresentativeIn(Person):
    id: RepresentativeId


class StopIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stop_id: StopId
    lat: float = Field(ge=-90, le=90, allow_inf_nan=False)
    lon: float = Field(ge=-180, le=180, allow_inf_nan=False)
    representatives: list[RepresentativeIn] = Field(
        min_length=TRUST_CONFIG.delivery_representatives_min,
        max_length=TRUST_CONFIG.delivery_representatives_max,
    )
    residents: list[Person] = Field(max_length=STOP_CONFIG.residents_max)
    basis: Literal["REAL", "SYNTHETIC"]
    # The ward the stop serves (F20). Absent: placed on the 2016 ward polygons (DERIVED).
    ward_id: str | None = Field(default=None, max_length=64)

    @model_validator(mode="after")
    def _people(self) -> StopIn:
        for people, keys in (
            ("representative ids", [r.id for r in self.representatives]),
            ("resident ids", [r.id for r in self.residents]),
            # Replies are matched on the phone number, so two residents cannot share one.
            ("resident phone numbers", [phone_key(r.phone) for r in self.residents]),
        ):
            if len(set(keys)) != len(keys):
                raise ValueError(f"{people} must be unique within a stop")
        reps = {r.id for r in self.representatives}
        askable = [r for r in self.residents if r.id not in reps]  # reps are never sampled
        low = TRUST_CONFIG.delivery_residents_min
        if len(askable) < low:
            raise ValueError(f"A stop needs at least {low} residents besides its representatives")
        return self


def _errors(exc: ValidationError) -> list[dict[str, Any]]:
    """Where and why, never the submitted value (it may be a phone number)."""
    return [
        {"loc": list(e["loc"]), "msg": e["msg"], "type": e["type"]}
        for e in exc.errors(include_url=False, include_context=False, include_input=False)
    ]


def view(stop: Stop) -> dict[str, Any]:
    return {
        "stop_id": stop.stop_id,
        "lat": stop.lat,
        "lon": stop.lon,
        "basis": stop.basis,
        "ward_id": stop.ward_id,
        "ward_name": ward_locate.ward_name(stop.ward_id),
        "ward_basis": stop.ward_basis,
        "representatives": [
            {"id": r.id, "language": r.language, "phone_last2": phone_key(r.phone)[-2:]}
            for r in stop.representatives
        ],
        "representatives_count": len(stop.representatives),
        "residents_count": len(stop.residents),
    }


@router.post("", dependencies=[Depends(require_roles("officer"))])
def register(payload: Annotated[Any, Body()], store: Store) -> Any:
    try:
        body = StopIn.model_validate(payload)
    except ValidationError as exc:
        return error_response(422, "validation_error", "Request is not valid", _errors(exc))
    try:
        ward_id, ward_basis = ward_locate.place(body.lat, body.lon, body.ward_id)
    except ValueError as exc:
        return invalid(str(exc))
    stop = Stop(
        body.stop_id,
        body.lat,
        body.lon,
        tuple(
            dl.Representative(r.id, body.stop_id, r.phone, r.language) for r in body.representatives
        ),
        tuple(dl.Resident(r.id, r.phone, r.language) for r in body.residents),
        body.basis,
        ward_id,
        ward_basis,
    )
    try:
        store.put_stop(stop)
    except StopConflict as exc:
        raise HTTPException(409, str(exc)) from exc
    except ValueError as exc:
        return invalid(str(exc))
    saved = store.get_stop(stop.stop_id)
    assert saved is not None
    return view(saved)


@router.get("", dependencies=[Depends(require_roles("officer", "driver"))])
def list_stops(
    store: Store, offset: Offset = 0, limit: Limit = ApiConfig.default_limit
) -> dict[str, Any]:
    return page([view(s) for s in store.list_stops()], offset, limit)


@router.get("/{stop_id}", dependencies=[Depends(require_roles("officer", "driver"))])
def get_stop(stop_id: str, store: Store) -> dict[str, Any]:
    stop = store.get_stop(stop_id)
    if stop is None:
        raise not_found(f"Stop {stop_id}")
    return view(stop)
