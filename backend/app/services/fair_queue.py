"""Fair queue for booked tankers (A3, F8), and today's first-come-first-served baseline (B1).

Today (HMWSSB tracking page): each booking goes to its nearest filling station and waits by
serial number. The fair queue keeps the per-station queue and daily trip capacity, but serves:

1. tier 0, critical facilities, first come first served;
2. tier 1, households declaring no water on premises and assisted-channel bookings, FCFS;
3. everyone else by deficit round robin (Shreedhar & Varghese 1996) across groups, each group
   getting turns in proportion to its entitlement (A2: households x need weight).

A group is whatever unit carries an entitlement (a ward, or a section once sections are mapped
to wards); the queue does not need to know which. Deficits and the round-robin position carry
over to the next day while a group is still waiting, so small groups are never starved. Travel
distance is never used.

HMWSSB booking caps per consumer category are checked when bookings arrive (apply_caps).
"""

from __future__ import annotations

from collections import defaultdict, deque
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date, datetime

from app.config.allocation import ALLOCATION_CONFIG

EPSILON = 1e-9  # deficits are sums of fractional quanta


@dataclass(frozen=True)
class QueueBooking:
    booking_id: str
    group: str
    arrived_at: datetime
    tier: int  # 0 critical facility, 1 no water on premises or assisted channel, 2 other
    consumer_id: str
    category: str  # a key of ALLOCATION_CONFIG.booking_caps


@dataclass(frozen=True)
class Decision:
    booking: QueueBooking
    position: int  # 1-based order of service at this station today
    reason: str  # TIER_0 | TIER_1 | DRR | FCFS
    arrival_rank: int  # 1-based rank by arrival among today's pending bookings
    entitlement: float | None
    quantum: float | None  # share of a round-robin turn (largest group = 1)
    deficit_before: float | None


@dataclass(frozen=True)
class QueueState:
    deficits: dict[str, float] = field(default_factory=dict)
    cursor: str | None = None  # group whose round-robin turn comes next
    turn_open: bool = False  # cursor's turn began yesterday (its quantum is already added)


@dataclass(frozen=True)
class QueueResult:
    served: list[Decision]
    waiting: list[QueueBooking]
    state: QueueState


def _by_arrival(bookings: list[QueueBooking]) -> list[QueueBooking]:
    return sorted(bookings, key=lambda b: (b.arrived_at, b.booking_id))


def order_fcfs(pending: list[QueueBooking], capacity: int) -> QueueResult:
    """Baseline B1: serve in arrival order up to capacity."""
    ordered = _by_arrival(pending)
    served = [
        Decision(b, i + 1, "FCFS", i + 1, None, None, None)
        for i, b in enumerate(ordered[:capacity])
    ]
    return QueueResult(served, ordered[capacity:], QueueState())


def order_bookings(
    pending: list[QueueBooking],
    capacity: int,
    entitlement: Mapping[str, float],
    state: QueueState,
) -> QueueResult:
    """Order one filling station's pending bookings for one day of trip capacity."""
    ordered = _by_arrival(pending)
    rank = {b.booking_id: i + 1 for i, b in enumerate(ordered)}
    drr = [b for b in ordered if b.tier not in (0, 1)]
    for group in {b.group for b in drr}:
        if entitlement.get(group, 0) <= 0:
            raise ValueError(f"No positive entitlement for group {group}")

    served: list[Decision] = []

    def serve(booking: QueueBooking, reason: str, **explain: float | None) -> None:
        served.append(
            Decision(
                booking,
                len(served) + 1,
                reason,
                rank[booking.booking_id],
                explain.get("entitlement", entitlement.get(booking.group)),
                explain.get("quantum"),
                explain.get("deficit_before"),
            )
        )

    for tier, reason in ((0, "TIER_0"), (1, "TIER_1")):
        for booking in ordered:
            if booking.tier == tier and len(served) < capacity:
                serve(booking, reason)

    queues: dict[str, deque[QueueBooking]] = defaultdict(deque)
    for booking in drr:
        queues[booking.group].append(booking)
    deficits = {g: d for g, d in state.deficits.items() if g in queues}
    groups = sorted(queues, key=lambda g: (queues[g][0].arrived_at, g))
    largest = max((entitlement[g] for g in groups), default=1.0)
    quantum = {g: entitlement[g] / largest for g in groups}

    cursor, turn_open = state.cursor, state.turn_open
    index = groups.index(cursor) if cursor in groups else 0
    if cursor not in groups:
        turn_open = False
    while len(served) < capacity and any(queues.values()):
        group = groups[index]
        if queues[group]:
            if not turn_open:
                deficits[group] = deficits.get(group, 0.0) + quantum[group]
            turn_open = False
            while deficits[group] >= 1 - EPSILON and queues[group] and len(served) < capacity:
                serve(
                    queues[group].popleft(),
                    "DRR",
                    entitlement=entitlement[group],
                    quantum=quantum[group],
                    deficit_before=deficits[group],
                )
                deficits[group] -= 1
            if not queues[group]:
                deficits[group] = 0.0
            elif len(served) >= capacity and deficits[group] >= 1 - EPSILON:
                cursor, turn_open = group, True  # out of capacity mid-turn: resume it tomorrow
                break
        index = (index + 1) % len(groups)
        cursor = groups[index]

    served_ids = {d.booking.booking_id for d in served}
    waiting = _by_arrival(
        [b for b in ordered if b.tier in (0, 1) and b.booking_id not in served_ids]
        + [b for g in groups for b in queues[g]]
    )
    still_waiting = {b.group for b in waiting}
    new_state = QueueState(
        deficits={g: round(d, 12) for g, d in deficits.items() if g in still_waiting and d > 0},
        cursor=cursor if cursor in still_waiting else None,
        turn_open=turn_open and cursor in still_waiting,
    )
    return QueueResult(served, waiting, new_state)


# ---------------------------------------------------------------------------
# HMWSSB booking caps
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Rejection:
    booking: QueueBooking
    reason: str  # CAP_DAYS_BETWEEN | CAP_PER_DAY | CAP_PER_MONTH


@dataclass
class CapHistory:
    accepted: dict[str, list[date]] = field(default_factory=lambda: defaultdict(list))


def apply_caps(
    bookings: list[QueueBooking], history: CapHistory
) -> tuple[list[QueueBooking], list[Rejection]]:
    """Accept or reject new bookings under the HMWSSB caps; history is updated in place."""
    caps = ALLOCATION_CONFIG.booking_caps
    accepted: list[QueueBooking] = []
    rejected: list[Rejection] = []
    for booking in _by_arrival(bookings):
        if booking.category not in caps:
            raise ValueError(f"Unknown consumer category: {booking.category}")
        rule = caps[booking.category]
        day = booking.arrived_at.date()
        earlier = history.accepted[booking.consumer_id]
        reason = None
        if (
            "min_days_between" in rule
            and earlier
            and (day - earlier[-1]).days < rule["min_days_between"]
        ):
            reason = "CAP_DAYS_BETWEEN"
        elif "per_day" in rule and sum(d == day for d in earlier) >= rule["per_day"]:
            reason = "CAP_PER_DAY"
        elif sum((d.year, d.month) == (day.year, day.month) for d in earlier) >= rule["per_month"]:
            reason = "CAP_PER_MONTH"
        if reason:
            rejected.append(Rejection(booking, reason))
        else:
            earlier.append(day)
            accepted.append(booking)
    return accepted, rejected
