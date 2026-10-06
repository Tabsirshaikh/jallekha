"""Plan endpoints (T10): plan view, confidence (T9), officer check and approval (A7), and
explanations (T7). Shapes as in docs/api_shapes.md sections 8-10.

Plans come from the `PlanStore`: `POST /plans` builds the plan for a day of P2's replay
(SIMULATION) with the T9 gate and stores it (Wave 1, docs/api_additions/plans.md); an unknown
plan is 404, a stored plan that no longer rebuilds to its digest is 409.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict
from datetime import UTC, date, datetime
from functools import lru_cache
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, ConfigDict

from app.auth import require_roles
from app.config.allocation import ALLOCATION_CONFIG
from app.config.api import ApiConfig
from app.config.confidence import CONFIDENCE_CONFIG
from app.config.env import REPO_ROOT
from app.routers import evidence
from app.routers.common import csv_rows, invalid, not_found, page, typed
from app.routers.stores import (
    DebtStore,
    DeliveryStore,
    PlanConflict,
    PlanRecord,
    PlanStore,
    get_debt_store,
    get_delivery_store,
    get_plan_store,
)
from app.services import (
    confidence,
    explain,
    fair_queue,
    ledger_store,
    plan_builder,
    planner,
    section_plan,
    ward_locate,
)
from app.services.keyed_lock import KeyedLocks
from app.services.ledger_store import StoredLedger
from app.services.service_models import NeedWeights

router = APIRouter(tags=["plans"])

Officer = Depends(require_roles("officer"))
Reader = Depends(require_roles("officer", "resident", "councillor"))
Plans = Annotated[PlanStore, Depends(get_plan_store)]
Deliveries = Annotated[DeliveryStore, Depends(get_delivery_store)]
Debts = Annotated[DebtStore, Depends(get_debt_store)]


def get_plan_ledger() -> StoredLedger:
    return ledger_store.get_ledger()


Ledger = Annotated[StoredLedger, Depends(get_plan_ledger)]


# One change at a time per plan inside this process, so a check or approval and its ledger entry
# are never half-applied; the stored version refuses a stale write from another process (409).
_locks = KeyedLocks()


@contextmanager
def _guarded(plan_id: str) -> Iterator[None]:
    with _locks.hold(plan_id):
        try:
            yield
        except PlanConflict as exc:
            raise HTTPException(409, str(exc)) from exc


class Decision(BaseModel):
    officer_id: str
    reason: str


class WeightsIn(BaseModel):
    """Need weights for one plan (F7): all three, each between 0 and the configured maximum."""

    model_config = ConfigDict(extra="forbid")
    wad: float  # water-access deficit
    cad: float  # households with no phone
    hardship: float


class NewPlan(BaseModel):
    day: date  # a day of the replay window (YYYY-MM-DD)
    weights: WeightsIn | None = None  # absent: the configured default weights
    # The day's bookings, supplied by an officer (see docs/api_additions/plans.md). Absent: the
    # plan is built from the committed replay, which needs a day inside its window.
    bookings: list[dict[str, Any]] | None = None
    # "section": plan by HMWSSB section from the real monthly totals of the day's month divided by
    # the days (section_plan.py); `capacity` is then the fleet or the tight scenario.
    unit: Literal["ward", "section"] = "ward"
    capacity: Literal["fleet", "tight"] = "fleet"


def _record(plans: PlanStore, plan_id: str) -> PlanRecord:
    try:
        record = plans.get(plan_id)
    except plan_builder.PlanRebuildError as exc:
        raise HTTPException(409, str(exc)) from exc
    if record is None:
        raise not_found(f"Plan {plan_id}")
    return record


def _records(plans: PlanStore) -> Iterator[PlanRecord]:
    try:
        yield from plans.records()
    except plan_builder.PlanRebuildError as exc:
        raise HTTPException(409, str(exc)) from exc


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
    recipe = record.recipe or {}
    weights = recipe.get("weights")
    shown = NeedWeights(**weights) if weights else NeedWeights.default()
    stops = recipe.get("stops", [])
    litres = plan_builder.stop_litres(record.plan, [s["stop_id"] for s in stops])
    view.update(
        {
            "source": recipe.get("source", plan_builder.SOURCE),
            "unit": recipe.get("unit", "ward"),
            "capacity_scenario": recipe.get("capacity"),
            "trips_total": sum(st["trips"] for st in stations.values()),
            # Registered delivery stops the plan used (supplied plans) and its loads for each.
            "stops": [
                {
                    "stop_id": s["stop_id"],
                    "ward_id": s["ward_id"],
                    "ward_name": ward_locate.ward_name(s["ward_id"]),
                    "litres": litres[s["stop_id"]],
                }
                for s in stops
            ],
            "debts_used": len(recipe.get("debts", [])),
            "bookings_supplied": len(recipe["bookings"]) if "bookings" in recipe else None,
            "weights": {**shown.as_dict(), "is_default": weights is None},
            "group_names": plan_builder.group_names(list(full["effective_entitlement"])),
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


@router.post("/plans", dependencies=[Officer], status_code=201)
def create_plan(
    body: NewPlan,
    plans: Plans,
    ledger: Ledger,
    response: Response,
    deliveries: Deliveries,
    debts: Debts,
) -> dict[str, Any]:
    """Build and store a plan (T9 gate): from the bookings supplied in the request, or, without
    them, for a day of the committed replay. A supplied plan also uses the registered delivery
    stops (scheduled supply goes to the stops of its wards) and the saved water debt accounts.
    Idempotent: if the same plan is already stored it is returned as stored (200) and nothing is
    built or logged again."""
    try:
        weights = NeedWeights(**body.weights.model_dump()).validated() if body.weights else None
    except ValueError as exc:
        return invalid(str(exc))
    by_section = body.unit == "section"
    if by_section and body.bookings is not None:
        return invalid("A plan by section is made from the month's totals: do not supply bookings")
    supplied = body.bookings is not None
    stops: list[dict[str, Any]] = []
    owed: list[Any] = []
    if by_section:
        owed = list(debts.accounts().values())
    if supplied:
        stops = [
            {"stop_id": s.stop_id, "ward_id": s.ward_id, "lat": s.lat, "lon": s.lon}
            for s in deliveries.list_stops()
            if s.ward_id
        ]
        owed = list(debts.accounts().values())
    try:
        plan_id = (
            plan_builder.section_plan_id(body.day, body.capacity, weights)
            if by_section
            else plan_builder.supplied_plan_id(body.day, body.bookings, weights, stops, owed)
            if body.bookings is not None
            else plan_builder.plan_id_for(body.day, weights)
        )
    except plan_builder.InvalidBookings as exc:
        return invalid(str(exc))
    try:
        existing = plans.get(plan_id)
    except plan_builder.PlanRebuildError as exc:
        raise HTTPException(409, str(exc)) from exc
    if existing is not None:
        response.status_code = 200
        return plan_view(existing)
    try:
        built = (
            plan_builder.build_section_plan(body.day, body.capacity, weights, owed)
            if by_section
            else plan_builder.build_supplied_plan(
                body.day, body.bookings, weights=weights, stops=stops, debts=owed
            )
            if body.bookings is not None
            else plan_builder.build_replay_plan(body.day, weights=weights)
        )
    except plan_builder.InvalidBookings as exc:
        return invalid(str(exc))
    except plan_builder.ReplayDayUnavailable as exc:
        raise HTTPException(404, str(exc)) from exc
    record = PlanRecord(built.inputs, built.plan, built.basis, built.recipe)
    if not plans.put(record):  # stored by a concurrent request meanwhile
        response.status_code = 200
        return plan_view(_record(plans, built.plan.plan_id))
    for entry_type, payload, actor in built.events:  # plan_created, once
        if by_section:
            payload = {
                **payload,
                "source": plan_builder.SECTION,
                "unit": "section",
                "capacity": body.capacity,
            }
        if supplied:  # say where the bookings came from
            payload = {
                **payload,
                "source": plan_builder.SUPPLIED,
                "bookings": len(built.recipe["bookings"]),
                "stops": len(built.recipe.get("stops", [])),
                "debts": len(built.recipe.get("debts", [])),
            }
        if "weights" in built.recipe:  # every weight change is a ledger entry
            payload = {**payload, "weights": built.recipe["weights"]}
        ledger.append(entry_type, payload, actor)
    return plan_view(record)


@router.get("/plans", dependencies=[Officer])
def list_plans(
    plans: Plans, offset: evidence.Offset = 0, limit: evidence.Limit = ApiConfig.default_limit
) -> dict[str, Any]:
    # The sliders of a screen start at the defaults and stop at the largest allowed weight.
    return {
        **page(plans.summaries(), offset, limit),
        "default_weights": NeedWeights.default().as_dict(),
        "max_weight": ALLOCATION_CONFIG.need_weight_max,
    }


@router.get("/plans/{plan_id}/compare", dependencies=[Officer])
def compare_plan(plan_id: str, plans: Plans) -> dict[str, Any]:
    """Who gains and who loses booked trips under this plan's weights, against the default
    plan for the same day (SIMULATION). A plan with the default weights has no comparison."""
    record = _record(plans, plan_id)
    if not record.recipe:
        raise not_found(f"Comparison for plan {plan_id}")
    built = plan_builder.BuiltPlan(record.inputs, record.plan, record.basis, record.recipe, ())
    try:
        return plan_builder.compare_to_default(built)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.get("/plans/{plan_id}", dependencies=[Officer])
def get_plan(plan_id: str, plans: Plans) -> dict[str, Any]:
    return plan_view(_record(plans, plan_id))


@lru_cache(maxsize=1)
def _gate(mtime: float) -> confidence.T9Gate:
    return confidence.T9Gate(confidence.SignalTables.from_files(REPO_ROOT))


@router.get("/plans/{plan_id}/confidence", dependencies=[Officer])
def plan_confidence(plan_id: str, plans: Plans) -> dict[str, Any]:
    record = _record(plans, plan_id)
    groups = sorted({b.booking.group for b in record.inputs.pending})
    if (record.recipe or {}).get("source") == plan_builder.SECTION:
        return _section_confidence(groups)
    gate = _gate((REPO_ROOT / CONFIDENCE_CONFIG.evidence_path).stat().st_mtime)
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


def _section_confidence(groups: list[str]) -> dict[str, Any]:
    """Confidence of a plan by section: a section whose need or connection count is an estimate is
    flagged for an officer (section_plan.SectionGate); the T9 ward signals do not apply."""
    sections = section_plan.load_sections(REPO_ROOT)
    assessed = section_plan.SectionGate(sections).assess(groups)
    return {
        "threshold": 0.5,
        "threshold_basis": "ASSUMED (flagged when need or connections are an estimate)",
        "calibration": None,
        "groups": [
            {
                "group": g,
                "confidence": a.confidence,
                "needs_check": a.needs_check,
                "reason": a.reason,
                "used": ["need", "connections"] if not a.needs_check else [],
                "unavailable": [] if not a.needs_check else ["need or connections (estimated)"],
                "signals": [],
            }
            for g, a in assessed.items()
        ],
    }


@router.post("/plans/{plan_id}/groups/{group:path}/check", dependencies=[Officer])
def check_group(plan_id: str, group: str, body: Decision, plans: Plans, ledger: Ledger) -> Any:
    with _guarded(plan_id):
        record = _record(plans, plan_id)
        try:
            checked = planner.mark_checked(
                record.plan, group, body.officer_id, body.reason, ledger, datetime.now(UTC)
            )
        except ValueError as exc:
            return invalid(str(exc))
        record.plan = checked
        plans.save(record)
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
    with _guarded(plan_id):
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
        plans.save(record)
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
    for record in _records(plans):
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
