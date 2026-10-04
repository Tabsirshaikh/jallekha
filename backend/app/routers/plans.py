"""Plan endpoints (T10): plan view, confidence (T9), officer check and approval (A7), and
explanations (T7). Shapes as in docs/api_shapes.md sections 8-10.

Plans come from the in-memory `PlanStore` (no plan store on `main`, OPEN): an unknown plan is 404.
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime
from functools import lru_cache
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel

from app.auth import require_roles
from app.config.confidence import CONFIDENCE_CONFIG
from app.config.env import REPO_ROOT
from app.routers import evidence
from app.routers.common import csv_rows, invalid, not_found, typed
from app.routers.stores import PlanRecord, PlanStore, get_plan_store
from app.services import confidence, explain, fair_queue, ledger_store, planner
from app.services.ledger_store import StoredLedger

router = APIRouter(tags=["plans"])

Officer = Depends(require_roles("officer"))
Reader = Depends(require_roles("officer", "resident"))
Plans = Annotated[PlanStore, Depends(get_plan_store)]


def get_plan_ledger() -> StoredLedger:
    return ledger_store.get_ledger()


Ledger = Annotated[StoredLedger, Depends(get_plan_ledger)]


class Decision(BaseModel):
    officer_id: str
    reason: str


def _record(plans: PlanStore, plan_id: str) -> PlanRecord:
    record = plans.plans.get(plan_id)
    if record is None:
        raise not_found(f"Plan {plan_id}")
    return record


def plan_view(record: PlanRecord) -> dict[str, Any]:
    full = jsonable_encoder(asdict(record.plan))
    stations = {}
    for name, station in sorted(full["stations"].items()):
        stations[name] = {
            **station,
            "served_total": len(station["served"]),
            "waiting_total": len(station["waiting"]),
        }
    view = {
        k: full[k]
        for k in (
            "plan_id", "day", "status", "digest", "reserve_trips", "outage_trips",
            "special_tankers", "approved_by", "approval_reason",
        )
    }  # fmt: skip
    view.update(
        {
            "stations": stations,
            "stations_total": len(stations),
            "transfers": full["transfers"],
            "transfers_total": len(full["transfers"]),
            "scheduled": full["scheduled"],
            "scheduled_total": len(full["scheduled"]),
            "outage": full["outage"],
            "effective_entitlement": full["effective_entitlement"],
            "flags": full["flags"],
            "flags_total": len(full["flags"]),
            "checked": full["checked"],
            "unrouted": full["unrouted"],
            "unrouted_total": len(full["unrouted"]),
            "special_stops": full["special_stops"],
            "routing": full["routing"],
            "basis": record.basis,
        }
    )
    return view


@router.get("/plans/{plan_id}", dependencies=[Officer])
def get_plan(plan_id: str, plans: Plans) -> dict[str, Any]:
    return plan_view(_record(plans, plan_id))


@lru_cache(maxsize=1)
def _gate(mtime: float) -> confidence.T9Gate:
    return confidence.T9Gate(confidence.SignalTables.from_files(REPO_ROOT))


@router.get("/plans/{plan_id}/confidence", dependencies=[Officer])
def plan_confidence(plan_id: str, plans: Plans) -> dict[str, Any]:
    record = _record(plans, plan_id)
    gate = _gate((REPO_ROOT / CONFIDENCE_CONFIG.evidence_path).stat().st_mtime)
    groups = sorted({b.booking.group for b in record.inputs.pending})
    items = []
    for group in groups:
        c = gate.explain(group)
        items.append(
            {
                "group": group,
                "confidence": c.confidence,
                "needs_check": c.confidence < gate.threshold,
                "reason": c.reason,
                "used": list(c.used),
                "unavailable": list(c.unavailable),
                "signals": [asdict(s) for s in c.signals],
            }
        )
    selection = next(
        (r for r in csv_rows(CONFIDENCE_CONFIG.calibration_path) if r["row_type"] == "selection"),
        None,
    )
    return {
        "threshold": gate.threshold,
        "threshold_basis": gate.config.threshold_basis,
        "calibration": typed(selection) if selection else None,
        "groups": items,
    }


@router.post("/plans/{plan_id}/groups/{group:path}/check", dependencies=[Officer])
def check_group(plan_id: str, group: str, body: Decision, plans: Plans, ledger: Ledger) -> Any:
    record = _record(plans, plan_id)
    try:
        checked = planner.mark_checked(
            record.plan, group, body.officer_id, body.reason, ledger, datetime.now(UTC)
        )
    except ValueError as exc:
        return invalid(str(exc))
    record.plan = checked
    entry = ledger.entries[-1]
    return {
        "plan_id": plan_id,
        "group": group,
        "checked": True,
        "unchecked_flags": sorted(set(checked.flags) - set(checked.checked)),
        "ledger_seq": entry.seq,
        "ledger_event": entry.event_type,
    }


@router.post("/plans/{plan_id}/approve", dependencies=[Officer])
def approve(plan_id: str, body: Decision, plans: Plans, ledger: Ledger) -> Any:
    record = _record(plans, plan_id)
    if record.plan.status == "APPROVED":
        raise HTTPException(409, f"Plan {plan_id} is already approved")
    if not body.reason.strip():
        return invalid("A reason is required")
    try:
        record.plan = planner.approve_plan(
            record.plan, body.officer_id, body.reason, ledger, datetime.now(UTC)
        )
    except planner.PlanBlocked as exc:
        raise HTTPException(409, str(exc)) from exc
    except ValueError as exc:
        return invalid(str(exc))
    return plan_view(record)


# --- explanations (T7) ---------------------------------------------------------------------------


@router.get("/explain/wards/{ward_id:path}", dependencies=[Reader])
def explain_ward(ward_id: str) -> dict[str, Any]:
    row = evidence._ward(ward_id)
    return {
        "explanation": jsonable_encoder(asdict(explain.explain_ward(row, evidence._need(ward_id))))
    }


@router.get("/explain/bookings/{booking_id:path}", dependencies=[Reader])
def explain_booking(booking_id: str, plans: Plans) -> dict[str, Any]:
    for record in plans.plans.values():
        station = next(
            (p.station for p in record.inputs.pending if p.booking.booking_id == booking_id), None
        )
        if station is None:
            continue
        sp = record.plan.stations[station]
        # A7 serves the booked queue with booked_trips (capacity after the scheduled reserve).
        day = explain.QueueDay(
            [p.booking for p in record.inputs.pending if p.station == station],
            sp.booked_trips,
            record.inputs.entitlement,
            record.inputs.queue_states.get(station, fair_queue.QueueState()),
        )
        be = explain.explain_booking(day, booking_id, now=datetime.now(UTC))
        cf = explain.find_counterfactual(day, booking_id)
        return {
            "explanation": jsonable_encoder(asdict(be)),
            "counterfactual": jsonable_encoder(asdict(cf)),
        }
    raise not_found(f"Booking {booking_id}")
