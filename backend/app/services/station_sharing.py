"""Station trip sharing (A8 follow-up; A7 uses it): spare trips help a neighbour's queue.

HMWSSB ties every token to its nearest filling station, so on busy days a few stations build
backlogs while others have trips left (July 2026: 8 of 95 stations had pending bookings,
NewsMeter 2026-07-14). Here a station lends only the trips it has **left after its own
queue**, so its own customers never wait longer, and only to stations within `max_km`
(limited flexibility: a few neighbour links give most of the gain of full pooling, Jordan &
Graves 1995; Bassamboo, Randhawa & Van Mieghem 2012).

Who lends to whom is a min-cost max-flow (OR-Tools): move as many spare trips as possible,
then use the least extra km. The borrowing station still serves its own queue in its own
order (the A3 fair queue in JalLekha), so lending changes how many are served, never who
goes first.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from ortools.graph.python import min_cost_flow

KM_SCALE = 1000  # OR-Tools costs are integers: metres


@dataclass(frozen=True, order=True)
class Transfer:
    lender: str
    borrower: str
    trips: int
    round_trip_km: float  # extra km per lent trip (lender to borrower and back)


def station_km(km: Mapping[tuple[str, str], float], a: str, b: str) -> float | None:
    """Symmetric lookup of the round-trip km between two stations."""
    return km.get((a, b), km.get((b, a)))


def share_spare_trips(
    spare: Mapping[str, int],
    shortfall: Mapping[str, int],
    km: Mapping[tuple[str, str], float],
    max_km: float,
) -> list[Transfer]:
    if max_km < 0:
        raise ValueError("max_km cannot be negative")
    if any(v < 0 for v in (*spare.values(), *shortfall.values())):
        raise ValueError("spare and shortfall trips cannot be negative")
    lenders = sorted(s for s, n in spare.items() if n > 0)
    borrowers = sorted(s for s, n in shortfall.items() if n > 0)
    arcs = [
        (lender, borrower, distance)
        for lender in lenders
        for borrower in borrowers
        if lender != borrower
        and (distance := station_km(km, lender, borrower)) is not None
        and distance <= max_km
    ]
    if not arcs:
        return []
    flow = min_cost_flow.SimpleMinCostFlow()
    source, sink = 0, 1
    node = {s: i + 2 for i, s in enumerate(sorted({*lenders, *borrowers}))}
    total = sum(spare[s] for s in lenders)
    for lender in lenders:
        flow.add_arc_with_capacity_and_unit_cost(source, node[lender], spare[lender], 0)
    for borrower in borrowers:
        flow.add_arc_with_capacity_and_unit_cost(node[borrower], sink, shortfall[borrower], 0)
    arc_ids = [
        flow.add_arc_with_capacity_and_unit_cost(
            node[lender], node[borrower], total, round(distance * KM_SCALE)
        )
        for lender, borrower, distance in arcs
    ]
    flow.set_node_supply(source, total)
    flow.set_node_supply(sink, -total)
    status = flow.solve_max_flow_with_min_cost()
    if status != flow.OPTIMAL:
        raise RuntimeError(f"Trip sharing solver failed with status {status}")
    return sorted(
        (
            Transfer(lender, borrower, flow.flow(arc), distance)
            for (lender, borrower, distance), arc in zip(arcs, arc_ids, strict=True)
            if flow.flow(arc) > 0
        ),
        key=lambda t: (t.borrower, t.round_trip_km, t.lender),
    )
