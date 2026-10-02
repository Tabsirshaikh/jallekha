"""S3: OR-Tools route planner with reloads, ported from v1 (straight-line legs, no network)."""

from __future__ import annotations

import time

from app.config.allocation import ALLOCATION_CONFIG
from app.services import vrp

LOAD = ALLOCATION_CONFIG.tanker_load_litres
DEPOT_W = (17.44, 78.35)
DEPOT_E = (17.41, 78.55)


def demand(name: str, priority: float, lat: float, lng: float, wanted: int = 2, mandatory: int = 0):
    return vrp.Demand(
        id=name,
        name=name,
        priority=priority,
        point=(lat, lng),
        stops_wanted=wanted,
        mandatory_stops=mandatory,
    )


def fleet(n_small: int = 2, n_big: int = 1):
    tankers = [vrp.Tanker(id=f"S{i}", capacity=LOAD, depot=DEPOT_W) for i in range(n_small)]
    tankers += [vrp.Tanker(id=f"B{i}", capacity=2 * LOAD, depot=DEPOT_E) for i in range(n_big)]
    return tankers, [vrp.Station(id="W", point=DEPOT_W), vrp.Station(id="E", point=DEPOT_E)]


def city(n: int = 12):
    return [
        demand(f"D{i}", 90 - i * 6, 17.36 + (i % 4) * 0.03, 78.38 + (i // 4) * 0.06, wanted=3)
        for i in range(n)
    ]


def test_capacity_and_trip_limit_never_exceeded() -> None:
    tankers, stations = fleet()
    result = vrp.plan(city(), tankers, stations, time_limit_s=3)
    assert result.status in ("OPTIMIZED", "FEASIBLE_RELAXED")
    assert result.total_litres > 0
    capacity = {t.id: t.capacity for t in tankers}
    for route in result.routes:
        assert route.trips <= ALLOCATION_CONFIG.max_trips_per_tanker
        per_trip: dict[int, int] = {}
        for stop in route.stops:
            per_trip[stop.trip] = per_trip.get(stop.trip, 0) + stop.litres
        assert all(litres <= capacity[route.tanker_id] for litres in per_trip.values())


def test_mandatory_minimum_served_when_feasible() -> None:
    tankers, stations = fleet()
    demands = city()
    demands[-1] = demand("NEEDY", 55, 17.35, 78.47, wanted=2, mandatory=2)
    result = vrp.plan(demands, tankers, stations, time_limit_s=3)
    assert result.served_units.get("NEEDY", 0) >= 2
    assert result.relaxed_minimum == []


def test_low_priority_stops_dropped_first() -> None:
    tankers, stations = fleet(n_small=1, n_big=0)
    result = vrp.plan(city(12), tankers, stations, time_limit_s=3)
    served = set(result.served_units)
    dropped = {d["demand_id"] for d in result.dropped}
    assert dropped, "a single small tanker cannot serve 12 places"
    priority = {d.id: d.priority for d in city(12)}
    assert min(priority[d] for d in served) >= max(priority[d] for d in dropped) - 20


def test_infeasible_minimum_is_relaxed_and_recorded() -> None:
    tankers, stations = fleet(n_small=1, n_big=0)
    demands = [
        demand(f"M{i}", 60 + i, 17.36 + i * 0.01, 78.45, wanted=4, mandatory=4) for i in range(6)
    ]
    result = vrp.plan(demands, tankers, stations, time_limit_s=3)
    assert result.relaxed_minimum, "24 mandatory loads cannot fit on one tanker with 4 trips"
    assert result.status == "FEASIBLE_RELAXED"


def test_nothing_to_plan_and_no_resources() -> None:
    tankers, stations = fleet()
    assert vrp.plan([], tankers, stations).status == "NOTHING_TO_PLAN"
    result = vrp.plan(city(2), [], stations)
    assert result.status == "NO_RESOURCES" and len(result.dropped) == 2


def test_solver_respects_time_limit() -> None:
    tankers, stations = fleet()
    started = time.perf_counter()
    vrp.plan(city(), tankers, stations, time_limit_s=2)
    assert time.perf_counter() - started < 6
