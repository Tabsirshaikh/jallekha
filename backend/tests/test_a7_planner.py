"""A7: the daily planner (F8-F11, F17 stand-in): outage response first, the scheduled-supply
reserve, then each station's fair queue (debt raises a group's turns; spare trips are shared
with neighbours), a confidence check, and officer approval that needs a reason."""

from __future__ import annotations

import dataclasses
import math
from datetime import UTC, date, datetime, timedelta

import pytest

from app.config.allocation import ALLOCATION_CONFIG
from app.services import fair_queue, outage, planner
from app.services.ledger_port import InMemoryLedger
from app.services.planner import PlanInputs, PlannerBooking, ProvisionalGate
from app.services.scheduled_supply import ScheduledWard
from app.services.water_debt import DebtAccount

CFG = ALLOCATION_CONFIG
LOAD = CFG.tanker_load_litres
NOW = datetime(2026, 5, 10, 5, 0, tzinfo=UTC)
DAY = date(2026, 5, 10)


@pytest.fixture
def chain() -> InMemoryLedger:
    return InMemoryLedger(key="test-ledger-key", clock=lambda: NOW)


def pending(station: str, group: str, n: int, start: int = 0) -> list[PlannerBooking]:
    return [
        PlannerBooking(
            fair_queue.QueueBooking(
                booking_id=f"{group}-{start + i:03d}",
                group=group,
                arrived_at=NOW - timedelta(hours=10) + timedelta(minutes=start + i),
                tier=2,
                consumer_id=f"c-{group}-{start + i}",
                category="domestic",
            ),
            station,
        )
        for i in range(n)
    ]


def inputs(**kw) -> PlanInputs:
    defaults = dict(
        plan_id="P-2026-05-10",
        day=DAY,
        capacity={"S1": 10},
        pending=pending("S1", "ward:A", 8) + pending("S1", "ward:B", 8, start=100),
        entitlement={"ward:A": 1.0, "ward:B": 1.0},
    )
    return PlanInputs(**(defaults | kw))


def build(chain, gate=None, **kw):
    return planner.build_plan(inputs(**kw), gate or ProvisionalGate(), chain, NOW)


def served_ids(plan, station="S1") -> list[str]:
    return [s.booking_id for s in plan.stations[station].served]


def test_without_extras_each_station_is_the_a3_fair_queue(chain) -> None:
    plan = build(chain)
    direct = fair_queue.order_bookings(
        [p.booking for p in inputs().pending], 10, inputs().entitlement, fair_queue.QueueState()
    )
    assert served_ids(plan) == [d.booking.booking_id for d in direct.served]
    assert plan.stations["S1"].booked_trips == 10
    assert len(plan.stations["S1"].waiting) == 6
    assert plan.queue_states["S1"] == direct.state  # carried to tomorrow


def test_outage_response_takes_trips_first(chain) -> None:
    event, _ = outage.create_outage(
        "O1",
        ["W9"],
        NOW - timedelta(hours=30),
        None,
        "officer",
        "Main burst",
        "off-1",
        {"W9"},
        people_affected=1000,
    )
    stop = outage.CriticalStop("H1", "Hospital", "W9", 4000)
    plan = build(chain, capacity={"S1": 20}, outages=(event,), critical_stops=(stop,))
    budget = math.floor(20 * CFG.outage_max_fleet_share) * LOAD
    assert plan.outage.critical[0].litres == 4000  # tier 0 first
    used = budget - plan.outage.unused_litres
    assert plan.outage_trips == math.ceil(used / LOAD)
    assert plan.stations["S1"].booked_trips == 20 - plan.outage_trips
    assert plan.outage.counts_toward_water_debt is False


def test_scheduled_reserve_is_set_aside_before_bookings(chain) -> None:
    wards = (ScheduledWard("W5", people_off_premises=2000.0, need_weight=2.0),)
    plan = build(chain, capacity={"S1": 40}, scheduled=wards)
    reserve = round(40 * CFG.scheduled_reserve_share)
    assert plan.reserve_trips == reserve
    assert plan.scheduled["W5"].litres == pytest.approx(reserve * LOAD)
    assert plan.stations["S1"].booked_trips == 40 - reserve


def test_water_debt_gives_a_group_more_turns(chain) -> None:
    """Same entitlement and queue; B carries debt at the cap, so B gets more of the trips."""
    debt = DebtAccount(
        "ward:B",
        daily_entitlement_litres=LOAD,
        debt_litres=CFG.water_debt_cap_days * LOAD,
    )
    plan = build(chain, debts={"ward:B": debt})
    served = served_ids(plan)
    assert sum(s.startswith("ward:B") for s in served) > sum(s.startswith("ward:A") for s in served)
    assert plan.effective_entitlement["ward:B"] == pytest.approx(
        1.0 * (1 + CFG.debt_priority_weight)
    )
    assert plan.effective_entitlement["ward:A"] == 1.0


def test_spare_trips_go_to_a_short_neighbour_within_the_radius(chain) -> None:
    km_3 = 2 * 2.0 * CFG.road_factor  # stations 2 km apart, as round-trip road km
    kw = dict(
        capacity={"S1": 4, "S2": 6},
        pending=pending("S1", "ward:A", 7) + pending("S2", "ward:B", 2, start=100),
        station_km={("S1", "S2"): km_3},
    )
    plan = build(chain, **kw)
    assert len(plan.stations["S2"].served) == 2  # the lender's own queue first
    lent = [s for s in plan.stations["S1"].served if s.lender == "S2"]
    assert len(lent) == 3 and len(plan.stations["S1"].served) == 7
    far = build(InMemoryLedger(key="k", clock=lambda: NOW), sharing_radius_km=1.0, **kw)
    assert len(far.stations["S1"].served) == 4


def test_trips_are_never_overspent(chain) -> None:
    event, _ = outage.create_outage(
        "O1",
        ["W9"],
        NOW - timedelta(hours=5),
        None,
        "officer",
        "Burst",
        "off-1",
        {"W9"},
        people_affected=50_000,
    )
    plan = build(
        chain,
        capacity={"S1": 7, "S2": 5},
        pending=pending("S1", "ward:A", 30) + pending("S2", "ward:B", 30, start=100),
        outages=(event,),
        scheduled=(ScheduledWard("W5", 9000.0, 1.0),),
    )
    booked = sum(p.booked_trips for p in plan.stations.values())
    assert booked + plan.outage_trips + plan.reserve_trips == 12
    assert all(p.booked_trips >= 0 for p in plan.stations.values())
    for station, p in plan.stations.items():
        assert len(p.served) == p.booked_trips + p.borrowed - p.lent, station


def test_low_confidence_groups_are_flagged_and_block_approval(chain) -> None:
    gate = ProvisionalGate(fallback_groups=frozenset({"ward:B"}))
    plan = build(chain, gate=gate)
    assert set(plan.flags) == {"ward:B"}
    assert plan.flags["ward:B"].basis == "PROVISIONAL"
    with pytest.raises(planner.PlanBlocked, match="ward:B"):
        planner.approve_plan(plan, "officer-1", "Checked queue against yesterday", chain, NOW)


@pytest.mark.parametrize("reason", ["", "   "])
def test_approval_and_checks_need_a_reason(chain, reason) -> None:
    gate = ProvisionalGate(fallback_groups=frozenset({"ward:B"}))
    plan = build(chain, gate=gate)
    with pytest.raises(ValueError, match="reason"):
        planner.mark_checked(plan, "ward:B", "officer-1", reason, chain, NOW)
    checked = planner.mark_checked(plan, "ward:B", "officer-1", "Visited, data fine", chain, NOW)
    with pytest.raises(ValueError, match="reason"):
        planner.approve_plan(checked, "officer-1", reason, chain, NOW)
    with pytest.raises(ValueError, match="not flagged"):
        planner.mark_checked(plan, "ward:A", "officer-1", "x", chain, NOW)


def test_end_to_end_plan_check_approve_and_ledger(chain) -> None:
    event, _ = outage.create_outage(
        "O1",
        ["W9"],
        NOW - timedelta(hours=12),
        None,
        "notice",
        "Pipeline work",
        "off-1",
        {"W9"},
        people_affected=500,
    )
    plan = build(
        chain,
        gate=ProvisionalGate(fallback_groups=frozenset({"section:X"})),
        capacity={"S1": 12, "S2": 8},
        pending=pending("S1", "ward:A", 9)
        + pending("S1", "section:X", 4, start=50)
        + pending("S2", "ward:B", 3, start=100),
        entitlement={"ward:A": 2.0, "ward:B": 1.0, "section:X": 1.0},
        outages=(event,),
        scheduled=(ScheduledWard("W5", 1000.0, 1.5),),
        station_km={("S1", "S2"): 5.0},
    )
    assert plan.status == "DRAFT" and set(plan.flags) == {"section:X"}
    checked = planner.mark_checked(
        plan, "section:X", "officer-1", "Section mapped by hand", chain, NOW
    )
    approved = planner.approve_plan(checked, "officer-1", "Matches field reports", chain, NOW)
    assert approved.status == "APPROVED" and approved.approved_by == "officer-1"
    assert approved.digest == plan.digest  # approval binds the exact plan that was built
    with pytest.raises(ValueError, match="already approved"):
        planner.approve_plan(approved, "officer-1", "again", chain, NOW)
    entries = [e for e in chain.entries if e.entity_id == plan.plan_id]
    assert [e.event_type for e in entries] == ["plan_created", "ward_reviewed", "plan_approved"]
    assert entries[0].payload["digest"] == entries[2].payload["digest"] == plan.digest
    assert entries[0].payload["flagged_groups"] == ["section:X"]
    assert "Matches field reports" not in str(entries[2].payload)  # text kept off the ledger
    assert len(entries[2].payload["reason_sha256"]) == 64
    assert chain.verify().valid


def test_the_plan_is_deterministic(chain) -> None:
    a = build(chain, capacity={"S1": 5, "S2": 5}, station_km={("S1", "S2"): 5.0})
    b = build(
        InMemoryLedger(key="k", clock=lambda: NOW),
        capacity={"S1": 5, "S2": 5},
        station_km={("S1", "S2"): 5.0},
    )
    assert a.digest == b.digest
    changed = build(chain, capacity={"S1": 6, "S2": 5}, station_km={("S1", "S2"): 5.0})
    assert changed.digest != a.digest


def test_unknown_station_or_bad_capacity_is_rejected(chain) -> None:
    with pytest.raises(ValueError, match="station"):
        build(chain, pending=pending("S9", "ward:A", 1))
    with pytest.raises(ValueError, match="capacity"):
        build(chain, capacity={"S1": -1})


def test_inputs_are_not_mutated(chain) -> None:
    states = {"S1": fair_queue.QueueState()}
    data = inputs(queue_states=states)
    planner.build_plan(data, ProvisionalGate(), chain, NOW)
    assert data.queue_states == {"S1": fair_queue.QueueState()}
    assert dataclasses.is_dataclass(data)
