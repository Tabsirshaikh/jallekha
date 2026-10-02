"""Policy sandbox (A8, F19): replayed bookings under one capacity, served by each policy.

Every booking is one tanker trip from a filling station. Each day, each station serves at most
its capacity of pending bookings; a booking waiting `expiry_days` days is unmet. After the last
arrival day the replay keeps running for `expiry_days` days so every booking is resolved.

Policies (all on the same bookings, stations and capacities):
- B1 FCFS at the nearest station (today, HMWSSB tracking page).
- B2 nearest bookings first at each station (distance-greedy dispatcher).
- B3 largest bookers first: the section with most pending bookings at the station first.
- B4 minimum cost: stations are pooled; each day the cheapest (booking, station) trips are
  taken first among each booking's nearby stations.
- B5 need first: highest ward need weight first (pure priority).
- JL_F8 the A3 fair queue (deficit round robin by entitlement) at each station.
- JL JL_F8 plus the F9 reserve: a share of every station's trips goes to scheduled supply
  (A4 share_reserve), so fewer trips are left for bookings.
- JL_POOL JL plus station trip sharing (station_sharing): a station's trips left after its own
  queue go to short stations within sharing_max_km; the borrower keeps its fair order. A lent
  trip's km is the lender-section km when known (its nearest stations), else the borrower's
  trip + the lender-borrower round trip (APPROXIMATE upper bound).
Replay bookings carry no tier, so all are tier 2 in the queue. Outputs are SIMULATION.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.services import fair_queue, station_sharing
from app.services.booking_groups import WARD_PREFIX, ward_group
from app.services.scheduled_supply import ScheduledWard, share_reserve

POLICIES = ("B1", "B2", "B3", "B4", "B5", "JL_F8", "JL", "JL_POOL")
RESERVE_POLICIES = ("JL", "JL_POOL")
FAIR_QUEUE_POLICIES = ("JL_F8", "JL", "JL_POOL")
BASELINE = "B1"


@dataclass(frozen=True, slots=True)
class SimBooking:
    booking_id: str
    section: str
    group: str  # fair-queue group (A3 booking_groups)
    day: int  # arrival day index from the start of the replay
    arrived_at: datetime


@dataclass(frozen=True)
class Network:
    # (section, station) -> round-trip km; the entries are also B4's candidate stations
    round_trip_km: Mapping[tuple[str, str], float]
    home: Mapping[str, str]  # section -> nearest station (where its tokens queue today)
    # (station, station) -> round-trip km, for JL_POOL trip sharing (symmetric lookup)
    station_km: Mapping[tuple[str, str], float] = field(default_factory=dict)


@dataclass(frozen=True)
class Setting:
    days: int  # arrival days
    capacity: Mapping[str, int]  # station -> trips per day
    entitlement: Mapping[str, float]  # group -> A2/A3 entitlement
    need_weight: Mapping[str, float]  # group -> A2 need weight
    expiry_days: int
    litres_per_trip: float
    scheduled: tuple[ScheduledWard, ...] = ()
    reserve_share: float = 0.0
    sharing_max_km: float = 0.0  # JL_POOL: lend spare trips to stations this close


@dataclass(frozen=True, slots=True)
class Served:
    booking: SimBooking
    day: int
    station: str
    wait_days: int
    km: float


@dataclass(frozen=True)
class RunResult:
    policy: str
    served: tuple[Served, ...]
    unmet: tuple[SimBooking, ...]
    capacity_trips: int  # station trips over the arrival days (reserve included)
    reserve_trips_per_day: int
    scheduled_litres: dict[str, float] = field(default_factory=dict)  # per ward per day


def queue_booking(booking: SimBooking) -> fair_queue.QueueBooking:
    return fair_queue.QueueBooking(
        booking_id=booking.booking_id,
        group=booking.group,
        arrived_at=booking.arrived_at,
        tier=2,
        consumer_id=booking.booking_id,
        category="domestic",
    )


def _arrival(b: SimBooking) -> tuple[datetime, str]:
    return b.arrived_at, b.booking_id


def _station_order(
    policy: str,
    station: str,
    pending: list[SimBooking],
    capacity: int,
    network: Network,
    setting: Setting,
    states: dict[str, fair_queue.QueueState],
) -> list[SimBooking]:
    if capacity <= 0 or not pending:
        return []
    if policy == "B1":
        ordered = sorted(pending, key=_arrival)
    elif policy == "B2":
        ordered = sorted(
            pending, key=lambda b: (network.round_trip_km[(b.section, station)], *_arrival(b))
        )
    elif policy == "B3":
        counts = Counter(b.section for b in pending)
        ordered = sorted(pending, key=lambda b: (-counts[b.section], *_arrival(b)))
    elif policy == "B5":
        ordered = sorted(pending, key=lambda b: (-setting.need_weight[b.group], *_arrival(b)))
    else:  # FAIR_QUEUE_POLICIES
        by_id = {b.booking_id: b for b in pending}
        result = fair_queue.order_bookings(
            [queue_booking(b) for b in pending],
            capacity,
            setting.entitlement,
            states.get(station, fair_queue.QueueState()),
        )
        states[station] = result.state
        return [by_id[d.booking.booking_id] for d in result.served]
    return ordered[:capacity]


def _pooled_order(
    pending: list[SimBooking], spare: dict[str, int], network: Network
) -> list[tuple[SimBooking, str]]:
    """B4: cheapest (booking, station) trips first, each station up to its spare trips."""
    by_section: dict[str, list[tuple[str, float]]] = defaultdict(list)
    for (section, station), km in network.round_trip_km.items():
        by_section[section].append((station, km))
    pairs = sorted(
        (km, b.arrived_at, b.booking_id, station, b)
        for b in pending
        for station, km in by_section[b.section]
    )
    taken: set[str] = set()
    chosen = []
    for _km, _at, booking_id, station, booking in pairs:
        if booking_id in taken or spare.get(station, 0) <= 0:
            continue
        spare[station] -= 1
        taken.add(booking_id)
        chosen.append((booking, station))
    return chosen


def run(
    policy: str, bookings: Iterable[SimBooking], network: Network, setting: Setting
) -> RunResult:
    if policy not in POLICIES:
        raise ValueError(f"Unknown policy {policy}; expected one of {POLICIES}")
    reserve = dict.fromkeys(setting.capacity, 0)
    scheduled_litres: dict[str, float] = {}
    if policy in RESERVE_POLICIES and setting.scheduled:
        reserve = {s: round(c * setting.reserve_share) for s, c in setting.capacity.items()}
        litres = sum(reserve.values()) * setting.litres_per_trip
        shares = share_reserve(list(setting.scheduled), litres)
        scheduled_litres = {w: share.litres for w, share in sorted(shares.items())}
    booked_capacity = {s: c - reserve[s] for s, c in setting.capacity.items()}

    arriving: dict[int, list[SimBooking]] = defaultdict(list)
    for b in sorted(bookings, key=_arrival):
        arriving[b.day].append(b)
    pending: dict[str, list[SimBooking]] = defaultdict(list)
    states: dict[str, fair_queue.QueueState] = {}
    served: list[Served] = []
    unmet: list[SimBooking] = []

    def serve(b: SimBooking, day: int, station: str, lent_to: str | None = None, detour=0.0):
        """lent_to: the borrowing station whose queue a lent trip serves. A lent trip uses
        the direct lender-section km when known, else the borrower's trip plus the detour."""
        direct = network.round_trip_km.get((b.section, station))
        km = direct if direct is not None else network.round_trip_km[(b.section, lent_to)] + detour
        served.append(Served(b, day, station, day - b.day, km))

    for day in range(setting.days + setting.expiry_days):
        for station in list(pending):
            keep = []
            for b in pending[station]:
                (unmet if day - b.day >= setting.expiry_days else keep).append(b)
            pending[station] = keep
        for b in arriving.get(day, ()):
            pending[network.home[b.section]].append(b)
        if policy == "B4":
            pool = sorted((b for queue in pending.values() for b in queue), key=_arrival)
            chosen = _pooled_order(pool, dict(booked_capacity), network)
            done = {b.booking_id for b, _ in chosen}
            for b, station in chosen:
                serve(b, day, station)
            for station in pending:
                pending[station] = [b for b in pending[station] if b.booking_id not in done]
            continue
        lent: dict[str, list[tuple[float, str]]] = defaultdict(list)
        if policy == "JL_POOL":
            spare, short = {}, {}
            for station, capacity in booked_capacity.items():
                waiting = len(pending.get(station, ()))
                spare[station], short[station] = (
                    max(0, capacity - waiting),
                    max(0, waiting - capacity),
                )
            for t in station_sharing.share_spare_trips(
                spare, short, network.station_km, setting.sharing_max_km
            ):
                lent[t.borrower].extend([(t.round_trip_km, t.lender)] * t.trips)
        for station in sorted(pending):
            own = booked_capacity.get(station, 0)
            extra = sorted(lent.get(station, ()))
            chosen = _station_order(
                policy,
                station,
                pending[station],
                own + len(extra),
                network,
                setting,
                states,
            )
            done = {b.booking_id for b in chosen}
            for i, b in enumerate(chosen):
                if i < own:
                    serve(b, day, station)
                else:
                    detour, lender = extra[i - own]
                    serve(b, day, lender, lent_to=station, detour=detour)
            pending[station] = [b for b in pending[station] if b.booking_id not in done]
    unmet.extend(b for queue in pending.values() for b in queue)
    return RunResult(
        policy=policy,
        served=tuple(served),
        unmet=tuple(sorted(unmet, key=_arrival)),
        capacity_trips=sum(setting.capacity.values()) * setting.days,
        reserve_trips_per_day=sum(reserve.values()),
        scheduled_litres=scheduled_litres,
    )


def gini(values: list[float]) -> float:
    """Mean absolute difference over twice the mean; 0 = all equal."""
    n = len(values)
    mean = sum(values) / n if n else 0.0
    if mean <= 0:
        return 0.0
    ordered = sorted(values)
    weighted = sum((2 * (i + 1) - n - 1) * x for i, x in enumerate(ordered))
    return weighted / (n * n * mean)


def jain(values: list[float]) -> float:
    """Jain, Chiu & Hawe (1984): (sum x)^2 / (n sum x^2), from 1/n (worst) to 1 (equal)."""
    squares = sum(x * x for x in values)
    if not values or squares <= 0:
        return 1.0
    return sum(values) ** 2 / (len(values) * squares)


def _percentile(values: list[int], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return float(ordered[min(len(ordered) - 1, int(q * len(ordered)))])


def measures(
    result: RunResult,
    bookings: list[SimBooking],
    network: Network,
    setting: Setting,
    min_group_bookings: int,
) -> dict[str, Any]:
    """The PS11 measures of one run (duplicates are not part of the booking replay).

    Two views of balance: fill rate (served / booked) among groups that book, and need
    coverage (litres per day per unit of entitlement, scheduled supply included) over every
    ward group, so wards that never book are counted."""
    booked = len(bookings)
    weight = setting.need_weight
    booked_by_group = Counter(b.group for b in bookings)
    served_by_group = Counter(s.booking.group for s in result.served)
    need_booked = sum(weight[g] * n for g, n in booked_by_group.items())
    need_unmet = sum(weight[b.group] for b in result.unmet)
    waits = [s.wait_days for s in result.served]
    km = sum(s.km for s in result.served)
    kilolitres = len(result.served) * setting.litres_per_trip / 1000
    used = sum(s.day < setting.days for s in result.served)
    used += result.reserve_trips_per_day * setting.days
    capacity = result.capacity_trips
    fill = {
        g: served_by_group[g] / n
        for g, n in sorted(booked_by_group.items())
        if n >= min_group_bookings
    }
    rates = list(fill.values())
    worst = min(fill, key=lambda g: (fill[g], g)) if fill else None
    litres = {g: n * setting.litres_per_trip / setting.days for g, n in served_by_group.items()}
    for ward_id, daily in result.scheduled_litres.items():
        litres[ward_group(ward_id)] = litres.get(ward_group(ward_id), 0.0) + daily
    coverage = [
        litres.get(g, 0.0) / e
        for g, e in sorted(setting.entitlement.items())
        if g.startswith(WARD_PREFIX) and e > 0
    ]
    return {
        "booked": booked,
        "served": len(result.served),
        "unmet": len(result.unmet),
        "served_share": len(result.served) / booked if booked else 0.0,
        "unmet_share": len(result.unmet) / booked if booked else 0.0,
        "need_weighted_unmet_share": need_unmet / need_booked if need_booked else 0.0,
        "mean_wait_days": sum(waits) / len(waits) if waits else 0.0,
        "p90_wait_days": _percentile(waits, 0.9),
        "tanker_km": km,
        "km_per_kl": km / kilolitres if kilolitres else 0.0,
        "capacity_trips": capacity,
        "unused_capacity_share": max(0, capacity - used) / capacity if capacity else 0.0,
        "groups_compared": len(fill),
        "gini_fill_rate": gini(rates),
        "jain_fill_rate": jain(rates),
        "worst_group_fill_rate": fill[worst] if worst else 0.0,
        "worst_group": worst or "",
        "coverage_groups": len(coverage),
        "gini_need_coverage": gini(coverage),
        "jain_need_coverage": jain(coverage),
        "zero_water_ward_share": (
            sum(c <= 0 for c in coverage) / len(coverage) if coverage else 0.0
        ),
        "scheduled_litres_per_day": sum(result.scheduled_litres.values()),
        "scheduled_wards": len(result.scheduled_litres),
    }


def compare(rows: list[dict[str, Any]], metrics: list[str]) -> dict[str, dict[str, Any]]:
    """Mean and range per policy, and paired (same seed) differences against B1."""
    by_policy: dict[str, dict[int, dict[str, Any]]] = defaultdict(dict)
    for row in rows:
        by_policy[row["policy"]][row["seed"]] = row
    baseline = by_policy[BASELINE]
    summary: dict[str, dict[str, Any]] = {}
    for policy, seeds in by_policy.items():
        summary[policy] = {}
        for metric in metrics:
            values = [seeds[s][metric] for s in sorted(seeds)]
            diffs = [seeds[s][metric] - baseline[s][metric] for s in sorted(seeds) if s in baseline]
            summary[policy][metric] = {
                "mean": sum(values) / len(values),
                "min": min(values),
                "max": max(values),
                "diff_vs_b1_mean": sum(diffs) / len(diffs) if diffs else None,
                "diff_vs_b1_min": min(diffs) if diffs else None,
                "diff_vs_b1_max": max(diffs) if diffs else None,
                "seeds": len(values),
            }
    return summary
