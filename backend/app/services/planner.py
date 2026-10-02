"""Daily planner (A7, F8-F11 with the F17 gate): one plan per day, approved by an officer.

Order of the day's trips (one trip = one 5,000 l load):
1. Outage response (A5, F10): critical facilities first, then every outage to its floor, then
   targets, from at most `outage_max_fleet_share` of the day's trips. Never counts as debt.
2. Scheduled-supply reserve (A4, F9): `scheduled_reserve_share` of the trips when scheduled
   wards exist, shared by weighted max-min (A4 share_reserve). Routing to registered points is
   A4's plan_scheduled_supply.
3. Booked queue (A3, F8) at each filling station with the trips left. Outage and reserve trips
   come from every station in proportion to its trips (largest remainder). Water debt (A6)
   raises a group's turns: entitlement x (1 + debt_priority_weight x debt / cap).
4. Station trip sharing (station_sharing): a station's trips left after its own queue go to
   short stations within `station_sharing_radius_km`; the borrower keeps its fair order. Each
   booked trip is one load, so its route is station -> household -> station.
5. Routes: tier-0 critical stops, outage points and scheduled points are routed together by
   the S3 OR-Tools planner (A4's demands for scheduled points), with the tankers set aside
   for those trips (fleet sorted by id, enough for the outage + reserve trips). Priority:
   critical (100, mandatory) > outage (up to 90, floor stops mandatory) > scheduled (up to
   80). A need without a place (no location, no registered point) or without a fleet is
   listed in `unrouted`, never skipped silently.
6. Confidence (F17): a gate scores every group in the plan. Until P3's T9 lands, the
   ProvisionalGate flags groups whose need comes from the A3 fallback (no Census data).
7. Approval (F16/F17): a plan is a DRAFT until an officer approves it with a reason; every
   flagged group must first be marked "checked" with a reason. plan_created, ward_reviewed and
   plan_approved are ledger entries; reason text stays off the ledger (only its SHA-256), and
   the approval carries the digest of the exact plan built.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass, field, replace
from datetime import date, datetime, timedelta
from typing import Any, Protocol

from app.config.allocation import ALLOCATION_CONFIG
from app.services import fair_queue, outage, station_sharing, vrp
from app.services.ledger_port import LedgerPort
from app.services.scheduled_supply import (
    ScheduledWard,
    ServicePointRegistry,
    WardShare,
    scheduled_demands,
    share_reserve,
)
from app.services.water_debt import DebtAccount, cap_litres

SYSTEM = "system"


class PlanBlocked(ValueError):
    """Approval refused: flagged groups have not been checked by an officer."""


@dataclass(frozen=True)
class PlannerBooking:
    booking: fair_queue.QueueBooking
    station: str  # the filling station its token is assigned to (nearest)


@dataclass(frozen=True)
class PlanInputs:
    plan_id: str
    day: date
    capacity: Mapping[str, int]  # station -> trips today
    pending: Sequence[PlannerBooking]
    entitlement: Mapping[str, float]  # group -> A2/A3 entitlement
    queue_states: Mapping[str, fair_queue.QueueState] = field(default_factory=dict)
    debts: Mapping[str, DebtAccount] = field(default_factory=dict)  # group -> A6 account
    scheduled: Sequence[ScheduledWard] = ()
    outages: Sequence[outage.OutageEvent] = ()
    critical_stops: Sequence[outage.CriticalStop] = ()
    station_km: Mapping[tuple[str, str], float] = field(default_factory=dict)  # round trip
    sharing_radius_km: float = ALLOCATION_CONFIG.station_sharing_radius_km
    # Routing of outage and scheduled deliveries (optional: without a fleet, needs are listed)
    critical_locations: Mapping[str, vrp.Point] = field(default_factory=dict)  # stop -> point
    registry: ServicePointRegistry = field(default_factory=ServicePointRegistry)
    fleet: Sequence[vrp.Tanker] = ()
    depots: Sequence[vrp.Station] = ()
    routing_seconds: float | None = None
    shift_start: str = "06:00"


@dataclass(frozen=True)
class Assessment:
    confidence: float  # 0-1
    needs_check: bool
    reason: str
    basis: str


class ConfidenceGate(Protocol):
    def assess(self, groups: Iterable[str]) -> dict[str, Assessment]: ...


@dataclass(frozen=True)
class ProvisionalGate:
    """Stand-in for P3's T9: a group whose need comes from the A3 fallback (no Census data)
    has confidence 0 and needs an officer's check; every other group passes."""

    fallback_groups: frozenset[str] = frozenset()

    def assess(self, groups: Iterable[str]) -> dict[str, Assessment]:
        return {
            g: Assessment(0.0, True, "NO_CENSUS_NEED_DATA", "PROVISIONAL")
            if g in self.fallback_groups
            else Assessment(1.0, False, "OK", "PROVISIONAL")
            for g in sorted(set(groups))
        }


@dataclass(frozen=True)
class ServedBooking:
    booking_id: str
    group: str
    position: int
    reason: str  # TIER_0 | TIER_1 | DRR (A3)
    lender: str | None = None  # station whose spare trip serves it (sharing)


@dataclass(frozen=True)
class StationPlan:
    station: str
    trips: int  # capacity today
    booked_trips: int  # after outage and reserve trips
    lent: int
    borrowed: int
    served: tuple[ServedBooking, ...]
    waiting: tuple[str, ...]


@dataclass(frozen=True)
class SpecialStop:
    kind: str  # critical | outage | scheduled
    place_id: str  # critical stop id or service point id
    ward_id: str
    tanker_id: str
    trip: int
    sequence: int
    arrival: str  # HH:MM local
    litres: int


@dataclass(frozen=True)
class Unrouted:
    kind: str  # critical | outage | scheduled
    place_id: str  # critical stop id, outage id or ward id
    litres: float
    reason: str  # NEEDS_LOCATION | NEEDS_SERVICE_POINT | NO_FLEET_GIVEN | NOT_ROUTED


@dataclass(frozen=True)
class DailyPlan:
    plan_id: str
    day: date
    stations: dict[str, StationPlan]
    transfers: tuple[station_sharing.Transfer, ...]
    outage: outage.OutageResponse
    outage_trips: int
    scheduled: dict[str, WardShare]
    reserve_trips: int
    effective_entitlement: dict[str, float]
    flags: dict[str, Assessment]
    queue_states: dict[str, fair_queue.QueueState]
    digest: str
    routing: vrp.PlanResult | None = None
    special_stops: tuple[SpecialStop, ...] = ()
    unrouted: tuple[Unrouted, ...] = ()
    special_tankers: tuple[str, ...] = ()
    status: str = "DRAFT"  # DRAFT | APPROVED
    checked: dict[str, str] = field(default_factory=dict)  # group -> officer's reason
    approved_by: str | None = None
    approval_reason: str | None = None


def _take_trips(capacity: Mapping[str, int], trips: int) -> dict[str, int]:
    """Trips each station gives up, in proportion to its trips (largest remainder)."""
    total = sum(capacity.values())
    if trips <= 0 or total <= 0:
        return dict.fromkeys(capacity, 0)
    exact = {s: trips * c / total for s, c in capacity.items()}
    taken = {s: math.floor(v) for s, v in exact.items()}
    rest = sorted(capacity, key=lambda s: (-(exact[s] - taken[s]), s))
    for s in rest[: trips - sum(taken.values())]:
        taken[s] += 1
    return taken


def effective_entitlement(
    entitlement: Mapping[str, float], debts: Mapping[str, DebtAccount]
) -> dict[str, float]:
    weight = ALLOCATION_CONFIG.debt_priority_weight
    out = {}
    for group, value in entitlement.items():
        account = debts.get(group)
        share = 0.0
        if account is not None and account.debt_litres > 0:
            share = min(1.0, account.debt_litres / cap_litres(account))
        out[group] = value * (1 + weight * share)
    return out


def _digest(content: dict[str, Any]) -> str:
    text = json.dumps(content, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(text.encode()).hexdigest()


def _validate(data: PlanInputs) -> None:
    if any(c < 0 for c in data.capacity.values()):
        raise ValueError("Station capacity cannot be negative")
    unknown = sorted({p.station for p in data.pending} - set(data.capacity))
    if unknown:
        raise ValueError(f"Bookings at unknown station(s): {unknown}")
    if data.sharing_radius_km < 0:
        raise ValueError("sharing_radius_km cannot be negative")


def _special_demands(
    data: PlanInputs, response: outage.OutageResponse, scheduled: dict[str, WardShare]
) -> tuple[list[vrp.Demand], dict[str, tuple[str, str, str]], list[Unrouted]]:
    """Routing demands for critical stops, outage points and scheduled points; needs that
    have no place are returned as Unrouted."""
    load = ALLOCATION_CONFIG.tanker_load_litres
    demands: list[vrp.Demand] = []
    meta: dict[str, tuple[str, str, str]] = {}  # demand id -> (kind, place id, ward id)
    missing: list[Unrouted] = []
    names = {c.stop_id: c.name for c in data.critical_stops}
    for c in response.critical:
        if c.litres <= 0:
            continue
        point = data.critical_locations.get(c.stop_id)
        if point is None:
            missing.append(Unrouted("critical", c.stop_id, c.litres, "NEEDS_LOCATION"))
            continue
        stops = math.ceil(c.litres / load - 1e-9)
        demand_id = f"critical:{c.stop_id}"
        demands.append(vrp.Demand(demand_id, names[c.stop_id], 100.0, point, stops, stops))
        meta[demand_id] = ("critical", c.stop_id, c.ward_id)
    top = max((a.priority for a in response.allocations), default=1.0)
    for a in response.allocations:
        if a.litres <= 0:
            continue
        points = [p for w in a.ward_ids for p in data.registry.for_ward(w)]
        if not points:
            missing.append(Unrouted("outage", a.outage_id, a.litres, "NEEDS_SERVICE_POINT"))
            continue
        for p in points:
            stops = max(1, round(a.litres / len(points) / load))
            floor = min(stops, max(1, round(a.floor / len(points) / load)))
            demand_id = f"outage:{a.outage_id}:{p.point_id}"
            demands.append(
                vrp.Demand(demand_id, p.name, 90 * a.priority / top, (p.lat, p.lng), stops, floor)
            )
            meta[demand_id] = ("outage", p.point_id, p.ward_id)
    if scheduled:
        wards = [w for w in data.scheduled if w.ward_id in scheduled]
        plans, scheduled_list, points = scheduled_demands(wards, scheduled, data.registry)
        for ward_id, ward_plan in sorted(plans.items()):
            if ward_plan.status == "NEEDS_SERVICE_POINT" and ward_plan.litres > 0:
                missing.append(
                    Unrouted("scheduled", ward_id, ward_plan.litres, "NEEDS_SERVICE_POINT")
                )
        for d in scheduled_list:
            demand_id = f"scheduled:{d.id}"
            demands.append(replace(d, id=demand_id, priority=0.8 * d.priority))
            meta[demand_id] = ("scheduled", d.id, points[d.id].ward_id)
    return demands, meta, missing


def _route(
    data: PlanInputs,
    demands: list[vrp.Demand],
    meta: dict[str, tuple[str, str, str]],
    trips: int,
) -> tuple[vrp.PlanResult | None, tuple[SpecialStop, ...], list[Unrouted], tuple[str, ...]]:
    load = ALLOCATION_CONFIG.tanker_load_litres
    if not demands:
        return None, (), [], ()
    if not data.fleet or not data.depots:
        unrouted = [
            Unrouted(meta[d.id][0], meta[d.id][1], d.stops_wanted * load, "NO_FLEET_GIVEN")
            for d in demands
        ]
        return None, (), unrouted, ()
    needed = max(1, math.ceil(trips / ALLOCATION_CONFIG.max_trips_per_tanker))
    tankers = sorted(data.fleet, key=lambda t: t.id)[:needed]
    result = vrp.plan(demands, tankers, list(data.depots), time_limit_s=data.routing_seconds)
    start = datetime.strptime(data.shift_start, "%H:%M")
    stops = tuple(
        sorted(
            (
                SpecialStop(
                    kind=meta[stop.demand_id][0],
                    place_id=meta[stop.demand_id][1],
                    ward_id=meta[stop.demand_id][2],
                    tanker_id=route.tanker_id,
                    trip=stop.trip,
                    sequence=stop.sequence,
                    arrival=(start + timedelta(minutes=stop.eta_min)).strftime("%H:%M"),
                    litres=stop.litres,
                )
                for route in result.routes
                for stop in route.stops
            ),
            key=lambda s: (s.arrival, s.tanker_id, s.sequence),
        )
    )
    unrouted = [
        Unrouted(meta[str(d["demand_id"])][0], meta[str(d["demand_id"])][1], 0.0, "NOT_ROUTED")
        for d in result.dropped
    ]
    return result, stops, unrouted, tuple(t.id for t in tankers)


def build_plan(
    data: PlanInputs, gate: ConfidenceGate, ledger: LedgerPort, now: datetime
) -> DailyPlan:
    """Build today's DRAFT plan and record it (plan_created)."""
    _validate(data)
    cfg = ALLOCATION_CONFIG
    load = cfg.tanker_load_litres
    total = sum(data.capacity.values())

    budget = math.floor(total * cfg.outage_max_fleet_share) * load
    response = outage.plan_response(list(data.outages), list(data.critical_stops), budget, now)
    outage_trips = math.ceil((budget - response.unused_litres) / load - 1e-9)
    reserve_trips = (
        min(round(total * cfg.scheduled_reserve_share), total - outage_trips)
        if data.scheduled
        else 0
    )
    scheduled = share_reserve(list(data.scheduled), reserve_trips * load) if data.scheduled else {}
    taken = _take_trips(data.capacity, outage_trips + reserve_trips)
    booked = {s: c - taken[s] for s, c in sorted(data.capacity.items())}

    by_station: dict[str, list[fair_queue.QueueBooking]] = defaultdict(list)
    for p in data.pending:
        by_station[p.station].append(p.booking)
    spare = {s: max(0, booked[s] - len(by_station[s])) for s in booked}
    short = {s: max(0, len(by_station[s]) - booked[s]) for s in booked}
    max_km = 2 * data.sharing_radius_km * cfg.road_factor
    transfers = station_sharing.share_spare_trips(spare, short, data.station_km, max_km)
    lent_to: dict[str, list[str]] = defaultdict(list)
    lent_by: dict[str, int] = defaultdict(int)
    for t in sorted(transfers, key=lambda t: (t.borrower, t.round_trip_km, t.lender)):
        lent_to[t.borrower].extend([t.lender] * t.trips)
        lent_by[t.lender] += t.trips

    weights = effective_entitlement(data.entitlement, data.debts)
    stations: dict[str, StationPlan] = {}
    states: dict[str, fair_queue.QueueState] = {}
    for station in booked:
        lenders = lent_to.get(station, [])
        result = fair_queue.order_bookings(
            by_station[station],
            booked[station] + len(lenders),
            weights,
            data.queue_states.get(station, fair_queue.QueueState()),
        )
        states[station] = result.state
        served = tuple(
            ServedBooking(
                d.booking.booking_id,
                d.booking.group,
                d.position,
                d.reason,
                lenders[i - booked[station]] if i >= booked[station] else None,
            )
            for i, d in enumerate(result.served)
        )
        stations[station] = StationPlan(
            station,
            data.capacity[station],
            booked[station],
            lent_by.get(station, 0),
            len(lenders),
            served,
            tuple(b.booking_id for b in result.waiting),
        )

    demands, meta, missing = _special_demands(data, response, scheduled)
    routing, special_stops, not_routed, special_tankers = _route(
        data, demands, meta, outage_trips + reserve_trips
    )
    unrouted = tuple(missing + not_routed)

    groups = {b.group for p in stations.values() for b in p.served}
    groups |= {p.booking.group for p in data.pending}
    flags = {g: a for g, a in gate.assess(groups).items() if a.needs_check}

    content = {
        "plan_id": data.plan_id,
        "day": data.day.isoformat(),
        "stations": {s: asdict(p) for s, p in stations.items()},
        "transfers": [asdict(t) for t in transfers],
        "outage": {
            "critical": [asdict(c) for c in response.critical],
            "allocations": [asdict(a) for a in response.allocations],
            "trips": outage_trips,
        },
        "scheduled": {w: asdict(s) for w, s in sorted(scheduled.items())},
        "reserve_trips": reserve_trips,
        "effective_entitlement": {g: round(v, 9) for g, v in sorted(weights.items())},
        "flags": {g: asdict(a) for g, a in sorted(flags.items())},
        "special_stops": [asdict(s) for s in special_stops],
        "unrouted": [asdict(u) for u in unrouted],
        "special_tankers": list(special_tankers),
    }
    plan = DailyPlan(
        plan_id=data.plan_id,
        day=data.day,
        stations=stations,
        transfers=tuple(transfers),
        outage=response,
        outage_trips=outage_trips,
        scheduled=dict(sorted(scheduled.items())),
        reserve_trips=reserve_trips,
        effective_entitlement=weights,
        flags=dict(sorted(flags.items())),
        queue_states=states,
        digest=_digest(content),
        routing=routing,
        special_stops=special_stops,
        unrouted=unrouted,
        special_tankers=special_tankers,
    )
    ledger.append(
        "plan_created",
        {
            "entity_type": "plan",
            "entity_id": plan.plan_id,
            "day": plan.day.isoformat(),
            "at": now.isoformat(),
            "digest": plan.digest,
            "trips": total,
            "outage_trips": outage_trips,
            "reserve_trips": reserve_trips,
            "booked_served": sum(len(p.served) for p in stations.values()),
            "booked_waiting": sum(len(p.waiting) for p in stations.values()),
            "trips_lent": sum(t.trips for t in transfers),
            "flagged_groups": sorted(flags),
            "routing_status": routing.status if routing else "NOT_ROUTED",
            "routed_stops": len(special_stops),
            "route_km": routing.total_km if routing else 0.0,
            "unrouted_needs": len(unrouted),
        },
        SYSTEM,
    )
    return plan


def _reason_fields(reason: str) -> dict[str, Any]:
    if not reason or not reason.strip():
        raise ValueError("A reason is required")
    text = reason.strip()
    return {"reason_sha256": hashlib.sha256(text.encode()).hexdigest(), "reason_chars": len(text)}


def mark_checked(
    plan: DailyPlan, group: str, officer: str, reason: str, ledger: LedgerPort, now: datetime
) -> DailyPlan:
    """An officer marks a flagged (low-confidence) group as checked, with a reason."""
    if group not in plan.flags:
        raise ValueError(f"{group} is not flagged in plan {plan.plan_id}")
    fields = _reason_fields(reason)
    ledger.append(
        "ward_reviewed",
        {
            "entity_type": "plan",
            "entity_id": plan.plan_id,
            "group": group,
            "digest": plan.digest,
            "flag_reason": plan.flags[group].reason,
            "at": now.isoformat(),
            **fields,
        },
        officer,
    )
    return replace(plan, checked={**plan.checked, group: reason.strip()})


def approve_plan(
    plan: DailyPlan, officer: str, reason: str, ledger: LedgerPort, now: datetime
) -> DailyPlan:
    """Officer approval (require_operator_approval): needs a reason and no unchecked flags."""
    if plan.status == "APPROVED":
        raise ValueError(f"Plan {plan.plan_id} is already approved")
    fields = _reason_fields(reason)
    unchecked = sorted(set(plan.flags) - set(plan.checked))
    if unchecked:
        raise PlanBlocked(f"Low-confidence groups need an officer check first: {unchecked}")
    ledger.append(
        "plan_approved",
        {
            "entity_type": "plan",
            "entity_id": plan.plan_id,
            "digest": plan.digest,
            "checked_groups": sorted(plan.checked),
            "at": now.isoformat(),
            **fields,
        },
        officer,
    )
    return replace(plan, status="APPROVED", approved_by=officer, approval_reason=reason.strip())
