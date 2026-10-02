"""Scheduled supply to fixed points for unconnected areas (A4, F9).

1. Wards: those A2 routes to scheduled supply (officer-set no_connection) plus candidates an
   officer confirms. People off premises = population x WAD (Census 2011 via E2).
2. Target litres/day = people off premises x norm (15 l/person/day floor, Sphere 2018; an
   officer may raise the norm, never lower it).
3. The fleet reserve for scheduled supply is shared: every ward's floor first (if the reserve
   cannot cover the floors, every ward gets the same fraction of its floor), then the extra by
   weighted max-min fairness (progressive filling by need weight, never above a target).
4. Stops are officer-registered fixed points only. The list starts empty (Delhi Jal Board
   publishes fixed-point schedules chosen with local representatives); a ward without a point
   is reported, not skipped.
5. Points are routed with the S3 OR-Tools planner. Distance is only a routing cost: it never
   changes how much water a ward is given.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from app.config.allocation import ALLOCATION_CONFIG
from app.services import vrp

EPSILON = 1e-6


@dataclass(frozen=True)
class ScheduledWard:
    ward_id: str
    people_off_premises: float
    need_weight: float  # A2
    lpcd: float | None = None  # officer-raised norm; None = the 15 lpcd floor


@dataclass(frozen=True)
class ServicePoint:
    point_id: str
    ward_id: str
    name: str
    lat: float
    lng: float
    registered_by: str
    reason: str


@dataclass(frozen=True)
class ServicePointRegistry:
    points: tuple[ServicePoint, ...] = ()

    def register(
        self, point: ServicePoint, known_wards: set[str]
    ) -> tuple[ServicePointRegistry, dict[str, Any]]:
        """Add an officer-registered point; returns the new registry and ledger entry args."""
        if not point.reason.strip():
            raise ValueError("A service point needs a written reason")
        if not (
            math.isfinite(point.lat)
            and math.isfinite(point.lng)
            and -90 <= point.lat <= 90
            and -180 <= point.lng <= 180
        ):
            raise ValueError(f"Invalid coordinate: {point.lat}, {point.lng}")
        if point.ward_id not in known_wards:
            raise ValueError(f"Unknown ward: {point.ward_id}")
        if any(p.point_id == point.point_id for p in self.points):
            raise ValueError(f"Service point {point.point_id} is already registered")
        event = {
            "event_type": "service_point_registered",
            "entity_type": "service_point",
            "entity_id": point.point_id,
            "payload": {
                "action": "service_point_registered",
                "ward_id": point.ward_id,
                "lat": point.lat,
                "lng": point.lng,
                "registered_by": point.registered_by,
                "reason": point.reason,
            },
        }
        return ServicePointRegistry(self.points + (point,)), event

    def for_ward(self, ward_id: str) -> list[ServicePoint]:
        return [p for p in self.points if p.ward_id == ward_id]


def scheduled_wards(
    needs: list[Any], evidence: list[dict[str, str]], confirmed: set[str]
) -> list[ScheduledWard]:
    """Wards for scheduled supply: A2 route "scheduled" plus officer-confirmed candidates.

    `needs` are A2 WardNeed rows; `confirmed` are ward ids an officer confirmed from the
    scheduled_supply_candidate list. People off premises = population x WAD (E2)."""
    candidates = {n.ward_id for n in needs if n.scheduled_supply_candidate}
    unknown = confirmed - candidates
    if unknown:
        raise ValueError(f"Not a scheduled-supply candidate: {sorted(unknown)}")
    population = {r["ward_id"]: r.get("population", "") for r in evidence}
    wards = []
    for need in needs:
        if need.service_route != "scheduled" and need.ward_id not in confirmed:
            continue
        if need.need_weight is None or need.wad is None or not population.get(need.ward_id):
            continue  # no Census values: the officer check list already carries this ward
        wards.append(
            ScheduledWard(
                ward_id=need.ward_id,
                people_off_premises=float(population[need.ward_id]) * need.wad,
                need_weight=need.need_weight,
            )
        )
    return wards


@dataclass(frozen=True)
class WardShare:
    ward_id: str
    litres: float
    floor: float
    target: float
    status: str  # TARGET_MET | FLOOR_MET | FLOOR_NOT_MET


def floor_litres(ward: ScheduledWard) -> float:
    return ward.people_off_premises * ALLOCATION_CONFIG.minimum_litres_per_person_day


def target_litres(ward: ScheduledWard) -> float:
    minimum = ALLOCATION_CONFIG.minimum_litres_per_person_day
    lpcd = minimum if ward.lpcd is None else ward.lpcd
    if lpcd < minimum:
        raise ValueError(f"Norm {lpcd} lpcd is below the {minimum} lpcd floor")
    return ward.people_off_premises * lpcd


def _water_fill(
    room: dict[str, float], weights: dict[str, float], budget: float
) -> dict[str, float]:
    """Weighted max-min: raise every open ward at a rate proportional to its weight until it
    reaches its room or the budget runs out."""
    given = dict.fromkeys(room, 0.0)
    open_wards = {w for w, r in room.items() if r > EPSILON}
    while budget > EPSILON and open_wards:
        total_weight = sum(weights[w] for w in open_wards)
        step = min(
            budget / total_weight,
            min((room[w] - given[w]) / weights[w] for w in open_wards),
        )
        for w in open_wards:
            given[w] += weights[w] * step
        budget -= total_weight * step
        open_wards = {w for w in open_wards if room[w] - given[w] > EPSILON}
    return given


def share_reserve(wards: list[ScheduledWard], reserve_litres: float) -> dict[str, WardShare]:
    floors = {w.ward_id: floor_litres(w) for w in wards}
    targets = {w.ward_id: target_litres(w) for w in wards}
    total_floor = sum(floors.values())
    if reserve_litres < total_floor - EPSILON:
        fraction = reserve_litres / total_floor if total_floor else 0.0
        litres = {w: floors[w] * fraction for w in floors}
    else:
        extra = _water_fill(
            {w: targets[w] - floors[w] for w in floors},
            {w.ward_id: w.need_weight for w in wards},
            reserve_litres - total_floor,
        )
        litres = {w: floors[w] + extra[w] for w in floors}
    shares = {}
    for w in floors:
        if litres[w] >= targets[w] - EPSILON:
            status = "TARGET_MET"
        elif litres[w] >= floors[w] - EPSILON:
            status = "FLOOR_MET"
        else:
            status = "FLOOR_NOT_MET"
        shares[w] = WardShare(w, litres[w], floors[w], targets[w], status)
    return shares


@dataclass(frozen=True)
class WardPlan:
    ward_id: str
    litres: float  # share of the reserve
    floor: float
    target: float
    status: str  # a WardShare status, or NEEDS_SERVICE_POINT
    point_ids: tuple[str, ...]


@dataclass(frozen=True)
class TimetableRow:
    point_id: str
    point_name: str
    ward_id: str
    tanker_id: str
    trip: int
    sequence: int
    arrival: str  # HH:MM, local time
    litres: int


@dataclass
class ScheduledPlan:
    wards: dict[str, WardPlan]
    timetable: list[TimetableRow]
    routing: vrp.PlanResult
    basis: dict[str, str] = field(
        default_factory=lambda: {
            "people_off_premises": "DERIVED (Census 2011 via E2)",
            "norm": "ASSUMED (Sphere 2018 floor)",
            "service_points": "OFFICER",
        }
    )


def plan_scheduled_supply(
    wards: list[ScheduledWard],
    registry: ServicePointRegistry,
    tankers: list[vrp.Tanker],
    stations: list[vrp.Station],
    reserve_litres: float,
    time_limit_s: float | None = None,
    shift_start: str = "06:00",
) -> ScheduledPlan:
    load = ALLOCATION_CONFIG.tanker_load_litres
    shares = share_reserve(wards, reserve_litres)
    weights = {w.ward_id: w.need_weight for w in wards}
    top_weight = max(weights.values(), default=1.0)
    plans: dict[str, WardPlan] = {}
    demands: list[vrp.Demand] = []
    points_by_id: dict[str, ServicePoint] = {}
    for ward in wards:
        share = shares[ward.ward_id]
        points = registry.for_ward(ward.ward_id)
        status = share.status if points else "NEEDS_SERVICE_POINT"
        plans[ward.ward_id] = WardPlan(
            ward.ward_id,
            share.litres,
            share.floor,
            share.target,
            status,
            tuple(p.point_id for p in points),
        )
        for point in points:
            litres = share.litres / len(points)
            stops = round(litres / load)
            if stops == 0:
                continue
            floor_stops = min(stops, max(1, round(share.floor / len(points) / load)))
            points_by_id[point.point_id] = point
            demands.append(
                vrp.Demand(
                    id=point.point_id,
                    name=point.name,
                    priority=100 * weights[ward.ward_id] / top_weight,
                    point=(point.lat, point.lng),
                    stops_wanted=stops,
                    mandatory_stops=floor_stops,
                )
            )
    routing = vrp.plan(demands, tankers, stations, time_limit_s=time_limit_s)
    start = datetime.strptime(shift_start, "%H:%M")
    timetable = [
        TimetableRow(
            point_id=stop.demand_id,
            point_name=points_by_id[stop.demand_id].name,
            ward_id=points_by_id[stop.demand_id].ward_id,
            tanker_id=route.tanker_id,
            trip=stop.trip,
            sequence=stop.sequence,
            arrival=(start + timedelta(minutes=stop.eta_min)).strftime("%H:%M"),
            litres=stop.litres,
        )
        for route in routing.routes
        for stop in route.stops
    ]
    timetable.sort(key=lambda row: (row.arrival, row.tanker_id, row.sequence))
    return ScheduledPlan(plans, timetable, routing)
