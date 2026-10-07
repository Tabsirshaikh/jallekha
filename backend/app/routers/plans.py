"""Plan endpoints (T10): plan view, confidence (T9), officer check and approval (A7), and
explanations (T7). Shapes as in docs/api_shapes.md sections 8-10.

Plans come from the `PlanStore`: `POST /plans` builds the plan for a day of P2's replay
(SIMULATION) with the T9 gate and stores it (Wave 1, docs/api_additions/plans.md); an unknown
plan is 404, a stored plan that no longer rebuilds to its digest is 409.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict
from datetime import UTC, date, datetime
from functools import lru_cache
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import require_roles
from app.config.allocation import ALLOCATION_CONFIG
from app.config.api import ApiConfig
from app.config.confidence import CONFIDENCE_CONFIG
from app.config.env import REPO_ROOT
from app.models import SupplyNotice
from app.routers import evidence
from app.routers.common import csv_rows, invalid, not_found, page, typed
from app.routers.notices import get_notice_service
from app.routers.section_outcomes import Reviews
from app.routers.stores import (
    DebtStore,
    DeliveryStore,
    PlanConflict,
    PlanRecord,
    PlanStore,
    get_booking_store,
    get_debt_store,
    get_delivery_store,
    get_plan_store,
)
from app.services import (
    booking_dispatch,
    confidence,
    explain,
    fair_queue,
    ledger_store,
    plan_builder,
    plan_overview,
    planner,
    route_schedule,
    section_plan,
    ward_locate,
)
from app.services import bookings as bk
from app.services.keyed_lock import KeyedLocks
from app.services.ledger_store import StoredLedger
from app.services.notices import NoticeService
from app.services.service_models import NeedWeights
from app.services.supply_reviews import current_sections

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
    # For a plan by section (section_plan.py): estimated priority classes, scheduled supply for the
    # sections the F4 screen flags, and carry-over from the days before. Outages come from the
    # supply notices that overlap the day.
    priority: bool = True
    scheduled: Literal["f4", "none"] = "f4"
    carry_over: bool = True
    # For a plan by section (feat/responsive-allocation): A, turns follow the last 7 days of
    # service; B, trips follow the bookings waiting at each station. On unless switched off.
    responsive: bool = True
    rebalance: bool = True


def _notice_outages(notices: NoticeService, day: date) -> list[dict[str, Any]]:
    """Supply notices overlapping the day, as outages by section (stored in the plan's recipe)."""
    with Session(notices.engine) as session:
        rows = session.execute(
            select(
                SupplyNotice.id,
                SupplyNotice.ward_ids_json,
                SupplyNotice.start_at,
                SupplyNotice.end_at,
            )
        ).all()

    def aware(moment: datetime) -> datetime:
        return moment if moment.tzinfo else moment.replace(tzinfo=UTC)

    found = [
        {"id": r[0], "ward_ids": json.loads(r[1]), "start": aware(r[2]), "end": aware(r[3])}
        for r in rows
    ]
    return section_plan.outages_from_notices(REPO_ROOT, found, day)  # type: ignore[arg-type]


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
    group_of = {p.booking.booking_id: p.booking.group for p in record.inputs.pending}
    group_totals: dict[str, dict[str, int]] = {}
    for st in record.plan.stations.values():
        for b in st.served:
            group_totals.setdefault(b.group, {"served": 0, "waiting": 0})["served"] += 1
        for booking_id in st.waiting:
            group_totals.setdefault(group_of[booking_id], {"served": 0, "waiting": 0})[
                "waiting"
            ] += 1
    by_ward = unplaced = overview = None
    if recipe.get("source") == plan_builder.SECTION:
        by_ward, unplaced = section_plan.ward_totals(REPO_ROOT, group_totals)
        weights_of = recipe.get("weights")
        overview = plan_overview.section_overview(
            REPO_ROOT, record.inputs, record.plan, recipe.get("capacity"),
            NeedWeights(**weights_of) if weights_of else None,
        )  # fmt: skip
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
            # Served and waiting bookings per group; for a plan by section also per ward (shared
            # by building share, an estimate) and what no ward could take.
            "group_totals": group_totals,
            "ward_totals": by_ward,
            "ward_unplaced": unplaced,
            # A plan by section in figures an officer can read (plan_overview.py); else null.
            "overview": overview,
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
    notices: Annotated[NoticeService, Depends(get_notice_service)],
    bookings_: Annotated[bk.BookingStore, Depends(get_booking_store)],
    reviews: Reviews,
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
    recipe: dict[str, Any] = {}
    if by_section:
        # bookings made through JalLekha, unless an officer supplies the day's bookings
        live = (
            []
            if body.bookings is not None
            else [bk.as_plan_booking(r, body.priority) for r in bookings_.waiting_for(body.day)]
        )
        try:
            recipe = plan_builder.section_recipe(
                body.day, body.capacity, weights, owed, body.priority, body.scheduled,
                body.carry_over, _notice_outages(notices, body.day), live,
                body.rebalance, body.responsive,
            )  # fmt: skip
            if body.bookings is not None:
                recipe["bookings"] = plan_builder.normalise_bookings(
                    body.day, body.bookings, by_section=True
                )
                recipe["carry_over"] = False
            values = current_sections(body.day, reviews, deliveries, bookings=bookings_)
            known = {g: v for g, v in values.items() if v["status"] != "UNKNOWN"}
            if known:
                recipe["weekly_priority"] = known
        except plan_builder.InvalidBookings as exc:
            return invalid(str(exc))
        except plan_builder.ReplayDayUnavailable as exc:
            raise HTTPException(404, str(exc)) from exc
    try:
        plan_id = (
            plan_builder.section_plan_id(body.day, body.capacity, weights, recipe)
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
            plan_builder._build_section(recipe)
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


_ROUTES: dict[tuple[str, str], dict[str, Any]] = {}


def routes_of(record: PlanRecord) -> dict[str, Any]:
    """The tanker routes of a plan by section (route_schedule.py), cached per plan digest."""
    key = (record.plan.plan_id, record.plan.digest)
    if key not in _ROUTES:
        if len(_ROUTES) >= 8:
            _ROUTES.pop(next(iter(_ROUTES)))
        sections = section_plan.static_sections(REPO_ROOT)
        _ROUTES[key] = route_schedule.build_routes(REPO_ROOT, record.plan, record.inputs, sections)
    return _ROUTES[key]


@router.get("/plans/{plan_id}/routes", dependencies=[Officer])
def plan_routes(
    plan_id: str, plans: Plans, station: str | None = None, compact: bool = False
) -> dict[str, Any]:
    """Tanker routes of a plan by section (route_schedule.py): the summary and every station's
    figures; with `station`, also that station's tankers and their trips (a day has about 6,000
    trips, so the trips of other stations are not sent); with `compact`, every tanker's trips in
    a small form (`paths`) for the city-wide animation. Computed from the plan, never stored."""
    record = _record(plans, plan_id)
    if (record.recipe or {}).get("source") != plan_builder.SECTION:
        raise HTTPException(409, "Routes are made for plans by section")
    full = routes_of(record)
    if station is not None and station not in {r["station_id"] for r in full["stations"]}:
        raise not_found(f"Station {station}")
    return {
        "plan_id": plan_id,
        "day": record.plan.day.isoformat(),
        "station": station,
        "summary": full["summary"],
        "stations": full["stations"],
        "tankers": [t for t in full["tankers"] if t["station_id"] == station] if station else [],
        "unscheduled": [
            u for u in full["unscheduled"] if station is None or u["station_id"] == station
        ][:200],
        "unscheduled_total": len(full["unscheduled"]),
        "paths": route_schedule.compact_paths(full) if compact else None,
        "basis": full["basis"],
    }


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
def approve(
    plan_id: str,
    body: Decision,
    plans: Plans,
    ledger: Ledger,
    deliveries: Deliveries,
    bookings_: Annotated[bk.BookingStore, Depends(get_booking_store)],
) -> Any:
    """Approve a plan (A7). For a plan by section, every served booking made through JalLekha is
    then given its tanker and a delivery stop (booking_dispatch.py), so the driver sees it."""
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
        if (record.recipe or {}).get("source") == plan_builder.SECTION:
            booking_dispatch.assign_from_routes(plan_id, routes_of(record), bookings_, deliveries)
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
