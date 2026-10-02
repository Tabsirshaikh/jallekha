"""A3: fair queue (F8): tiers, deficit round robin, HMWSSB caps and the FCFS baseline."""

from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timedelta

import pytest

from app.services import fair_queue as fq

T0 = datetime(2025, 4, 1, 6, 0)
DAY = date(2025, 4, 1)


def booking(n: int, group: str = "A", tier: int = 2, minutes: int | None = None, **kw):
    return fq.QueueBooking(
        booking_id=f"b{n:04d}",
        group=group,
        arrived_at=T0 + timedelta(minutes=n if minutes is None else minutes),
        tier=tier,
        consumer_id=kw.get("consumer_id", f"c{n:04d}"),
        category=kw.get("category", "domestic"),
    )


def served_ids(result: fq.QueueResult) -> list[str]:
    return [d.booking.booking_id for d in result.served]


def test_tier_0_then_tier_1_then_round_robin_whatever_the_arrival_order() -> None:
    pending = [booking(1, tier=2), booking(2, tier=1), booking(3, tier=0), booking(4, tier=2)]
    result = fq.order_bookings(pending, 4, {"A": 1.0}, fq.QueueState())
    assert served_ids(result) == ["b0003", "b0002", "b0001", "b0004"]
    assert [d.reason for d in result.served] == ["TIER_0", "TIER_1", "DRR", "DRR"]


def test_round_robin_shares_capacity_by_entitlement() -> None:
    pending = [booking(i, "A") for i in range(60)] + [booking(100 + i, "B") for i in range(60)]
    result = fq.order_bookings(pending, 30, {"A": 2.0, "B": 1.0}, fq.QueueState())
    counts = Counter(d.booking.group for d in result.served)
    assert counts["A"] + counts["B"] == 30
    assert abs(counts["A"] - 20) <= 1 and abs(counts["B"] - 10) <= 1


def test_first_come_first_served_inside_each_group() -> None:
    pending = [booking(i, "A", minutes=60 - i) for i in range(5)]
    result = fq.order_bookings(pending, 5, {"A": 1.0}, fq.QueueState())
    assert served_ids(result) == ["b0004", "b0003", "b0002", "b0001", "b0000"]


def test_capacity_respected_and_the_rest_wait_in_order() -> None:
    pending = [booking(i) for i in range(10)]
    result = fq.order_bookings(pending, 4, {"A": 1.0}, fq.QueueState())
    assert len(result.served) == 4
    assert [b.booking_id for b in result.waiting] == [f"b{i:04d}" for i in range(4, 10)]


def test_small_group_is_not_starved_over_days() -> None:
    """Deficit carries over between days while a group is backlogged (long-run fairness)."""
    state = fq.QueueState()
    pending = [booking(i, "BIG") for i in range(200)] + [
        booking(500 + i, "SMALL") for i in range(5)
    ]
    small_served_on = None
    for day in range(1, 12):
        result = fq.order_bookings(pending, 3, {"BIG": 10.0, "SMALL": 1.0}, state)
        if small_served_on is None and any(d.booking.group == "SMALL" for d in result.served):
            small_served_on = day
        pending, state = result.waiting, result.state
    assert small_served_on is not None and small_served_on <= 4


def test_empty_group_does_not_bank_turns() -> None:
    state = fq.QueueState(deficits={"A": 5.0})
    result = fq.order_bookings([booking(1, "B")], 1, {"A": 1.0, "B": 1.0}, state)
    assert result.state.deficits.get("A", 0.0) == 0.0


def test_missing_entitlement_is_an_error() -> None:
    with pytest.raises(ValueError, match="entitlement"):
        fq.order_bookings([booking(1, "Z")], 1, {"A": 1.0}, fq.QueueState())


def test_decision_carries_explanation_fields() -> None:
    result = fq.order_bookings(
        [booking(1, "A"), booking(2, "B")], 2, {"A": 3.0, "B": 1.0}, fq.QueueState()
    )
    decision = result.served[0]
    assert decision.position == 1
    assert decision.entitlement == 3.0
    assert decision.quantum == pytest.approx(1.0)
    assert decision.arrival_rank == 1


def test_fcfs_baseline_ignores_tiers_and_need() -> None:
    pending = [booking(1, "A", tier=2), booking(2, "B", tier=0), booking(3, "A")]
    result = fq.order_fcfs(pending, 2)
    assert served_ids(result) == ["b0001", "b0002"]
    assert all(d.reason == "FCFS" for d in result.served)


def test_same_inputs_same_order() -> None:
    pending = [booking(i, "AB"[i % 2]) for i in range(40)]
    first = fq.order_bookings(pending, 15, {"A": 1.5, "B": 1.0}, fq.QueueState())
    second = fq.order_bookings(list(reversed(pending)), 15, {"A": 1.5, "B": 1.0}, fq.QueueState())
    assert served_ids(first) == served_ids(second)


# ---- HMWSSB caps (domestic 1 per 2 days or 8 per month; apartments; commercial) ----


def at(day_offset: int, consumer: str = "c1", category: str = "domestic", n: int = 0):
    return fq.QueueBooking(
        booking_id=f"{consumer}-{day_offset}-{n}",
        group="A",
        arrived_at=T0 + timedelta(days=day_offset, minutes=n),
        tier=2,
        consumer_id=consumer,
        category=category,
    )


def test_domestic_one_booking_per_two_days() -> None:
    accepted, rejected = fq.apply_caps([at(0), at(1), at(2)], fq.CapHistory())
    assert [b.booking_id for b in accepted] == ["c1-0-0", "c1-2-0"]
    assert [(r.booking.booking_id, r.reason) for r in rejected] == [("c1-1-0", "CAP_DAYS_BETWEEN")]


def test_domestic_eight_per_month() -> None:
    bookings = [at(2 * i) for i in range(10)]  # every second day of April
    accepted, rejected = fq.apply_caps(bookings, fq.CapHistory())
    assert len(accepted) == 8
    assert {r.reason for r in rejected} == {"CAP_PER_MONTH"}


def test_large_apartment_three_per_day() -> None:
    bookings = [at(0, "apt", "apartment_25_200", n) for n in range(4)]
    accepted, rejected = fq.apply_caps(bookings, fq.CapHistory())
    assert len(accepted) == 3 and rejected[0].reason == "CAP_PER_DAY"


def test_caps_remember_earlier_days() -> None:
    history = fq.CapHistory()
    fq.apply_caps([at(0)], history)
    accepted, rejected = fq.apply_caps([at(1)], history)
    assert accepted == [] and rejected[0].reason == "CAP_DAYS_BETWEEN"


def test_unknown_category_is_an_error() -> None:
    with pytest.raises(ValueError, match="category"):
        fq.apply_caps([at(0, category="hotel")], fq.CapHistory())


def test_caps_come_from_config() -> None:
    from app.config.allocation import ALLOCATION_CONFIG

    assert ALLOCATION_CONFIG.booking_caps["domestic"] == {"min_days_between": 2, "per_month": 8}
    assert DAY.month == 4
