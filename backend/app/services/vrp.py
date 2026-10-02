"""Tanker route planner with reloads, using OR-Tools. Ported from v1's allocation planner (S3).

Inputs are generic: A3 (fair queue) and A4 (scheduled supply) decide which places need water
and how urgently; this module only fits those stops onto tankers and roads.

Model
- A stop is one tanker load (ALLOCATION_CONFIG.tanker_load_litres) at a demand point. A tanker
  of twice that size delivers two stops per trip.
- Tankers start full at their depot station and can reload at any station (optional reload
  nodes with negative demand and capacity slack, the OR-Tools "CVRP with reloads" pattern),
  so several trips per shift work.
- Time: shift length, travel time, unloading time per stop, refill time per reload.
- Mandatory stops (a minimum share) carry a dominant penalty instead of being hard
  constraints; if one still cannot fit, that demand's minimum is relaxed and recorded.
- Optional stops: dropping one costs (priority/100)^2 x penalty_scale x decay^k for the k-th
  extra stop of the same demand, so low-priority stops go first and one place cannot take
  the whole fleet.
- Travel distance is only a cost here; it never changes a demand's priority.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field

from ortools.constraint_solver import pywrapcp, routing_enums_pb2

from app.config.allocation import ALLOCATION_CONFIG
from app.services import routing

Point = tuple[float, float]  # (lat, lng)


@dataclass(frozen=True)
class Tanker:
    id: str
    capacity: int  # litres
    depot: Point  # its home filling station


@dataclass(frozen=True)
class Station:
    id: str
    point: Point


@dataclass(frozen=True)
class Demand:
    id: str
    name: str
    priority: float  # 0-100, set by A3/A4
    point: Point
    stops_wanted: int
    mandatory_stops: int = 0


@dataclass
class PlannedStop:
    demand_id: str
    litres: int
    sequence: int
    trip: int
    eta_min: float
    mandatory: bool


@dataclass
class PlannedRoute:
    tanker_id: str
    points: list[Point]  # depot -> ... -> depot, reloads included
    stops: list[PlannedStop]
    km: float
    minutes: float
    trips: int


@dataclass
class PlanResult:
    status: str
    seconds: float
    routes: list[PlannedRoute]
    served_units: dict[str, int] = field(default_factory=dict)
    dropped: list[dict[str, object]] = field(default_factory=list)
    relaxed_minimum: list[str] = field(default_factory=list)
    mandatory: list[str] = field(default_factory=list)
    objective: int | None = None

    @property
    def total_litres(self) -> int:
        return sum(stop.litres for route in self.routes for stop in route.stops)

    @property
    def total_km(self) -> float:
        return round(sum(route.km for route in self.routes), 2)


class _Model:
    def __init__(
        self,
        demands: list[Demand],
        tankers: list[Tanker],
        stations: list[Station],
        mandatory: set[str],
        horizon_minutes: int,
    ):
        cfg = ALLOCATION_CONFIG
        self.load = cfg.tanker_load_litres
        self.demands = demands
        self.tankers = tankers
        self.stations = stations
        self.mandatory = mandatory
        self.shift = horizon_minutes
        self.max_cap = max(t.capacity for t in tankers)

        # nodes: stations (depots) | reload copies | stops
        self.points: list[Point] = [s.point for s in stations]
        self.kind: list[str] = ["depot"] * len(stations)
        self.demand_of: list[Demand | None] = [None] * len(stations)
        self.stop_rank: list[int] = [0] * len(stations)
        reloads_per_station = max(2, cfg.max_trips_per_tanker - 1) * len(tankers)
        for station in stations:
            for _ in range(reloads_per_station):
                self.points.append(station.point)
                self.kind.append("reload")
                self.demand_of.append(None)
                self.stop_rank.append(0)
        for demand in demands:
            for k in range(demand.stops_wanted):
                self.points.append(demand.point)
                self.kind.append("stop")
                self.demand_of.append(demand)
                self.stop_rank.append(k)

        self.km, self.mins = routing.matrix(self.points, allow_network=False)
        depot_index = {s.point: i for i, s in enumerate(stations)}
        self.starts = [depot_index.get(t.depot, 0) for t in tankers]

    def solve(self, time_limit_s: float):
        cfg = ALLOCATION_CONFIG
        n = len(self.points)
        manager = pywrapcp.RoutingIndexManager(n, len(self.tankers), self.starts, self.starts)
        model = pywrapcp.RoutingModel(manager)

        def dist_cb(i: int, j: int) -> int:
            a, b = manager.IndexToNode(i), manager.IndexToNode(j)
            return int(self.km[a][b] * cfg.arc_cost_per_km)

        model.SetArcCostEvaluatorOfAllVehicles(model.RegisterTransitCallback(dist_cb))

        def demand_cb(i: int) -> int:
            kind = self.kind[manager.IndexToNode(i)]
            return self.load if kind == "stop" else (-self.max_cap if kind == "reload" else 0)

        model.AddDimensionWithVehicleCapacity(
            model.RegisterUnaryTransitCallback(demand_cb),
            self.max_cap,
            [t.capacity for t in self.tankers],
            True,
            "Capacity",
        )
        cap_dim = model.GetDimensionOrDie("Capacity")

        # at most max_trips_per_tanker loads per shift (the starting load + reloads)
        def reload_cb(i: int) -> int:
            return 1 if self.kind[manager.IndexToNode(i)] == "reload" else 0

        model.AddDimension(
            model.RegisterUnaryTransitCallback(reload_cb),
            0,
            cfg.max_trips_per_tanker - 1,
            True,
            "Reloads",
        )

        def time_cb(i: int, j: int) -> int:
            a, b = manager.IndexToNode(i), manager.IndexToNode(j)
            kind = self.kind[a]
            if kind == "stop":
                same_place = self.kind[b] == "stop" and self.demand_of[b] is self.demand_of[a]
                service = 0 if same_place else cfg.service_minutes
            elif kind == "reload":
                service = cfg.fill_minutes
            else:
                service = 0
            return service + int(math.ceil(self.mins[a][b]))

        model.AddDimension(model.RegisterTransitCallback(time_cb), 0, self.shift, True, "Time")
        self.time_dim = model.GetDimensionOrDie("Time")

        for node in range(len(self.stations), n):
            index = manager.NodeToIndex(node)
            if self.kind[node] == "reload":
                model.AddDisjunction([index], 0)
                continue
            cap_dim.SlackVar(index).SetValue(0)
            demand = self.demand_of[node]
            assert demand is not None
            k = self.stop_rank[node]
            if demand.id in self.mandatory and k < demand.mandatory_stops:
                model.AddDisjunction([index], cfg.mandatory_penalty)
                continue
            penalty = int(
                (max(demand.priority, 1.0) / 100) ** 2
                * cfg.penalty_scale
                * (cfg.extra_stop_decay**k)
            )
            model.AddDisjunction([index], max(1, penalty))

        params = pywrapcp.DefaultRoutingSearchParameters()
        params.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
        params.local_search_metaheuristic = (
            routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
        )
        params.time_limit.FromMilliseconds(int(time_limit_s * 1000))
        return manager, model, model.SolveWithParameters(params)

    def extract(self, manager, model, solution) -> list[PlannedRoute]:
        routes = []
        for v, tanker in enumerate(self.tankers):
            index = model.Start(v)
            points: list[Point] = []
            stops: list[PlannedStop] = []
            trip = 1
            sequence = 0
            km = 0.0
            last_was_reload = False
            while True:
                node = manager.IndexToNode(index)
                points.append(self.points[node])
                kind = self.kind[node]
                if kind == "reload":
                    last_was_reload = True
                elif kind == "stop":
                    if last_was_reload and stops:
                        trip += 1
                    last_was_reload = False
                    demand = self.demand_of[node]
                    assert demand is not None
                    eta = solution.Min(self.time_dim.CumulVar(index))
                    if stops and stops[-1].demand_id == demand.id and stops[-1].trip == trip:
                        stops[-1].litres += self.load
                    else:
                        sequence += 1
                        stops.append(
                            PlannedStop(
                                demand_id=demand.id,
                                litres=self.load,
                                sequence=sequence,
                                trip=trip,
                                eta_min=float(eta),
                                mandatory=demand.id in self.mandatory
                                and self.stop_rank[node] < demand.mandatory_stops,
                            )
                        )
                if model.IsEnd(index):
                    break
                nxt = solution.Value(model.NextVar(index))
                km += self.km[node][manager.IndexToNode(nxt)]
                index = nxt
            end_time = solution.Min(self.time_dim.CumulVar(model.End(v)))
            routes.append(
                PlannedRoute(
                    tanker_id=tanker.id,
                    points=_collapse(points) if stops else [tanker.depot],
                    stops=stops,
                    km=round(km, 2) if stops else 0.0,
                    minutes=float(end_time) if stops else 0.0,
                    trips=trip if stops else 0,
                )
            )
        return routes


def _collapse(points: list[Point]) -> list[Point]:
    out: list[Point] = []
    for point in points:
        if not out or out[-1] != point:
            out.append(point)
    return out


def plan(
    demands: list[Demand],
    tankers: list[Tanker],
    stations: list[Station],
    time_limit_s: float | None = None,
    horizon_minutes: int | None = None,
) -> PlanResult:
    started = time.perf_counter()
    cfg = ALLOCATION_CONFIG
    time_limit_s = time_limit_s if time_limit_s is not None else cfg.solver_seconds
    demands = [d for d in demands if d.stops_wanted > 0]
    if not tankers or not stations or not demands:
        return PlanResult(
            status="NO_RESOURCES" if demands else "NOTHING_TO_PLAN",
            seconds=0.0,
            routes=[],
            dropped=[
                {"demand_id": d.id, "reason": "No active tankers or filling stations"}
                for d in demands
            ],
        )

    mandatory = {d.id for d in demands if d.mandatory_stops > 0}
    budget = max(1.0, time_limit_s - (time.perf_counter() - started) - 0.2)
    model_ = _Model(demands, tankers, stations, mandatory, horizon_minutes or cfg.shift_minutes)
    manager, model, solution = model_.solve(budget)
    if solution is None:
        return PlanResult(
            status="INFEASIBLE",
            seconds=round(time.perf_counter() - started, 2),
            routes=[],
            mandatory=sorted(mandatory),
        )

    routes = model_.extract(manager, model, solution)
    served: dict[str, int] = {}
    for route in routes:
        for stop in route.stops:
            served[stop.demand_id] = served.get(stop.demand_id, 0) + stop.litres // model_.load
    relaxed = sorted(
        (d for d in demands if d.id in mandatory and served.get(d.id, 0) < d.mandatory_stops),
        key=lambda d: d.priority,
    )
    dropped: list[dict[str, object]] = [
        {
            "demand_id": d.id,
            "reason": "Fleet capacity used by higher-priority stops",
            "wanted_stops": d.stops_wanted,
        }
        for d in demands
        if served.get(d.id, 0) == 0
    ]
    return PlanResult(
        status="FEASIBLE_RELAXED" if relaxed else "OPTIMIZED",
        seconds=round(time.perf_counter() - started, 2),
        routes=routes,
        served_units=served,
        dropped=dropped,
        relaxed_minimum=[d.id for d in relaxed],
        mandatory=sorted(mandatory),
        objective=solution.ObjectiveValue(),
    )
