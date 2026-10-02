"""A8: policy sandbox (F19). Six policies (B1-B5, JL) plus JL_F8 (queue only) on the same
replayed bookings, station capacities and seeds; four PS11 measures against B1."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.services import fair_queue, sandbox
from app.services.sandbox import Network, Setting, SimBooking
from app.services.scheduled_supply import ScheduledWard

T0 = datetime(2025, 3, 1, tzinfo=UTC)


def booking(i: int, section: str, day: int = 0, group: str | None = None) -> SimBooking:
    return SimBooking(
        booking_id=f"b{i:03d}",
        section=section,
        group=group or f"g:{section}",
        day=day,
        arrived_at=T0 + timedelta(days=day, minutes=i),
    )


# Two stations 10 km apart; sections near (1 km) and far (4 km) from S1, and one at S2.
NETWORK = Network(
    round_trip_km={
        ("near", "S1"): 2.0,
        ("far", "S1"): 8.0,
        ("other", "S2"): 2.0,
        ("near", "S2"): 20.0,
        ("far", "S2"): 14.0,
        ("other", "S1"): 20.0,
    },
    home={"near": "S1", "far": "S1", "other": "S2"},
)


def setting(capacity, **kw) -> Setting:
    defaults = dict(
        days=1,
        capacity=capacity,
        entitlement={"g:near": 1.0, "g:far": 1.0, "g:other": 1.0},
        need_weight={"g:near": 1.0, "g:far": 1.0, "g:other": 1.0},
        expiry_days=3,
        litres_per_trip=5000,
    )
    return Setting(**(defaults | kw))


def served_ids(result) -> list[str]:
    return [s.booking.booking_id for s in result.served]


def test_b1_is_first_come_first_served_per_station_within_capacity() -> None:
    bookings = [booking(1, "far"), booking(2, "near"), booking(3, "near"), booking(4, "other")]
    result = sandbox.run("B1", bookings, NETWORK, setting({"S1": 2, "S2": 0}, days=1))
    first_day = [s.booking.booking_id for s in result.served if s.day == 0]
    assert first_day == ["b001", "b002"]
    assert all(s.station == NETWORK.home[s.booking.section] for s in result.served)


def test_unserved_bookings_expire_and_every_booking_resolves() -> None:
    bookings = [booking(i, "near") for i in range(5)]
    result = sandbox.run("B1", bookings, NETWORK, setting({"S1": 1, "S2": 0}, expiry_days=2))
    # waits 0 and 1 allowed: day 0 serves b000, day 1 serves b001, the rest expire
    assert served_ids(result) == ["b000", "b001"]
    assert [s.wait_days for s in result.served] == [0, 1]
    assert sorted(b.booking_id for b in result.unmet) == ["b002", "b003", "b004"]
    assert len(result.served) + len(result.unmet) == len(bookings)


def test_capacity_is_never_exceeded_and_never_idle_while_work_waits() -> None:
    bookings = [booking(i, "near", day=i % 3) for i in range(30)]
    cfg = setting({"S1": 4, "S2": 0}, days=3)
    for policy in sandbox.POLICIES:
        result = sandbox.run(policy, bookings, NETWORK, cfg)
        per_day = {}
        for s in result.served:
            per_day[s.day] = per_day.get(s.day, 0) + 1
        assert max(per_day.values()) <= 4, policy
        if policy != "JL":  # JL first moves its reserve to scheduled supply
            assert per_day[0] == 4, policy


def test_b2_serves_the_nearest_bookings_first() -> None:
    bookings = [booking(1, "far"), booking(2, "near")]
    result = sandbox.run("B2", bookings, NETWORK, setting({"S1": 1, "S2": 0}))
    assert result.served[0].booking.booking_id == "b002"


def test_b3_serves_the_section_with_most_pending_bookings_first() -> None:
    bookings = [booking(1, "far"), booking(2, "near"), booking(3, "near")]
    result = sandbox.run("B3", bookings, NETWORK, setting({"S1": 2, "S2": 0}))
    assert [s.booking.booking_id for s in result.served if s.day == 0] == ["b002", "b003"]


def test_b5_serves_the_highest_need_first() -> None:
    bookings = [booking(1, "near"), booking(2, "far")]
    weights = {"g:near": 1.0, "g:far": 2.5, "g:other": 1.0}
    result = sandbox.run("B5", bookings, NETWORK, setting({"S1": 1, "S2": 0}, need_weight=weights))
    assert result.served[0].booking.booking_id == "b002"


def test_b4_pools_stations_and_picks_the_cheapest_trips() -> None:
    """S2 has spare trips; B4 may use them for S1's bookings, cheapest first."""
    bookings = [booking(1, "near"), booking(2, "far"), booking(3, "near")]
    result = sandbox.run("B4", bookings, NETWORK, setting({"S1": 1, "S2": 1}))
    trips = {(s.booking.booking_id, s.station) for s in result.served if s.day == 0}
    assert trips == {("b001", "S1"), ("b002", "S2")}  # 2 km at S1, then 14 km beats 20 km


def test_jl_f8_is_the_a3_fair_queue() -> None:
    """Same order as calling fair_queue.order_bookings directly for the station-day."""
    bookings = [booking(i, "near", group="A") for i in range(6)] + [
        booking(10 + i, "far", group="B") for i in range(6)
    ]
    entitlement = {"A": 3.0, "B": 1.0}
    cfg = setting({"S1": 4, "S2": 0}, entitlement=entitlement, need_weight={"A": 1, "B": 1})
    result = sandbox.run("JL_F8", bookings, NETWORK, cfg)
    pending = [sandbox.queue_booking(b) for b in bookings]
    direct = fair_queue.order_bookings(pending, 4, entitlement, fair_queue.QueueState())
    day0 = [s.booking.booking_id for s in result.served if s.day == 0]
    assert day0 == [d.booking.booking_id for d in direct.served]
    assert sum(b.startswith("b00") for b in day0) == 3  # A gets 3 of 4 turns


def test_jl_moves_its_reserve_to_scheduled_supply() -> None:
    bookings = [booking(i, "near") for i in range(20)]
    wards = [ScheduledWard("W9", people_off_premises=1000.0, need_weight=2.0)]
    cfg = setting({"S1": 10, "S2": 10}, scheduled=wards, reserve_share=0.1)
    result = sandbox.run("JL", bookings, NETWORK, cfg)
    assert sum(s.day == 0 for s in result.served) == 9  # 10 trips less the 10% reserve
    # reserve 2 trips/day x 5000 l, but W9's target is 1000 people x 15 l = 15,000 l
    assert result.scheduled_litres == {"W9": pytest.approx(10000.0)}
    assert result.reserve_trips_per_day == 2


def test_runs_are_deterministic() -> None:
    bookings = [booking(i, ("near", "far", "other")[i % 3], day=i % 2) for i in range(40)]
    cfg = setting({"S1": 5, "S2": 3}, days=2)
    for policy in sandbox.POLICIES:
        assert sandbox.run(policy, bookings, NETWORK, cfg) == sandbox.run(
            policy, bookings, NETWORK, cfg
        )


def test_unknown_policy_is_rejected() -> None:
    with pytest.raises(ValueError, match="policy"):
        sandbox.run("B9", [], NETWORK, setting({"S1": 1, "S2": 1}))


def test_inequality_indices() -> None:
    assert sandbox.gini([1, 1, 1, 1]) == pytest.approx(0.0)
    assert sandbox.gini([0, 0, 0, 1]) == pytest.approx(0.75)
    assert sandbox.jain([1, 1, 1, 1]) == pytest.approx(1.0)
    assert sandbox.jain([1, 0, 0, 0]) == pytest.approx(0.25)  # Jain et al. 1984: 1/n worst


def test_measures() -> None:
    bookings = [booking(i, "near") for i in range(4)] + [booking(10, "far")]
    weights = {"g:near": 1.0, "g:far": 3.0, "g:other": 1.0}
    cfg = setting({"S1": 1, "S2": 0}, expiry_days=1, need_weight=weights)
    result = sandbox.run("B1", bookings, NETWORK, cfg)  # one trip: b000 served, rest unmet
    m = sandbox.measures(result, bookings, NETWORK, cfg, min_group_bookings=1)
    assert m["booked"] == 5 and m["served"] == 1 and m["unmet"] == 4
    assert m["unmet_share"] == pytest.approx(0.8)
    assert m["need_weighted_unmet_share"] == pytest.approx((3 * 1 + 1 * 3) / (4 * 1 + 1 * 3))
    assert m["mean_wait_days"] == 0.0
    assert m["tanker_km"] == pytest.approx(2.0)
    assert m["km_per_kl"] == pytest.approx(2.0 / 5.0)
    assert m["capacity_trips"] == 1 and m["unused_capacity_share"] == 0.0
    assert m["worst_group_fill_rate"] == 0.0  # far got nothing
    assert m["gini_fill_rate"] == pytest.approx(sandbox.gini([0.25, 0.0]))
    assert m["jain_fill_rate"] == pytest.approx(sandbox.jain([0.25, 0.0]))


def test_compare_reports_paired_differences_against_b1() -> None:
    rows = [
        {"policy": "B1", "seed": 0, "unmet_share": 0.10},
        {"policy": "B1", "seed": 1, "unmet_share": 0.20},
        {"policy": "JL", "seed": 0, "unmet_share": 0.05},
        {"policy": "JL", "seed": 1, "unmet_share": 0.25},
    ]
    summary = sandbox.compare(rows, ["unmet_share"])
    jl = summary["JL"]["unmet_share"]
    assert jl["mean"] == pytest.approx(0.15)
    assert (jl["min"], jl["max"]) == (0.05, 0.25)
    assert jl["diff_vs_b1_mean"] == pytest.approx(0.0)
    assert (jl["diff_vs_b1_min"], jl["diff_vs_b1_max"]) == pytest.approx((-0.05, 0.05))
    assert jl["seeds"] == 2


def test_need_coverage_counts_every_ward_including_those_that_never_book() -> None:
    """Litres per day per unit of entitlement (households x need weight), over every ward
    group, with scheduled supply included. A ward that never books gets 0 unless JL's
    reserve reaches it."""
    net = Network(round_trip_km={("s1", "S1"): 2.0}, home={"s1": "S1"})
    bookings = [booking(i, "s1", group="ward:W1") for i in range(4)]
    entitlement = {"ward:W1": 1.0, "ward:W2": 1.0, "section:X": 5.0}
    weights = dict.fromkeys(entitlement, 1.0)
    wards = (ScheduledWard("W2", people_off_premises=1000.0, need_weight=1.0),)
    cfg = setting(
        {"S1": 10},
        entitlement=entitlement,
        need_weight=weights,
        scheduled=wards,
        reserve_share=0.1,
    )
    b1 = sandbox.measures(sandbox.run("B1", bookings, net, cfg), bookings, net, cfg, 1)
    assert b1["coverage_groups"] == 2  # section fallback groups have no need data
    assert b1["zero_water_ward_share"] == 0.5  # W2 never books
    assert b1["gini_need_coverage"] == pytest.approx(sandbox.gini([20000.0, 0.0]))
    jl = sandbox.measures(sandbox.run("JL", bookings, net, cfg), bookings, net, cfg, 1)
    assert jl["zero_water_ward_share"] == 0.0  # 1 reserve trip = 5,000 l/day to W2
    assert jl["gini_need_coverage"] == pytest.approx(sandbox.gini([20000.0, 5000.0]))
    assert jl["jain_need_coverage"] == pytest.approx(sandbox.jain([20000.0, 5000.0]))
