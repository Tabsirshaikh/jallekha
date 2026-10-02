"""A4: scheduled supply (F9): officer service points (start empty), weighted max-min with a
15 lpcd floor, routing with distance as a cost only, and a timetable."""

from __future__ import annotations

import pytest

from app.config.allocation import ALLOCATION_CONFIG
from app.services import ledger, vrp
from app.services import scheduled_supply as ss

CFG = ALLOCATION_CONFIG
DEPOT = (17.44, 78.40)


def sw(ward_id: str, people: float, weight: float = 1.0, lpcd: float | None = None):
    return ss.ScheduledWard(
        ward_id=ward_id, people_off_premises=people, need_weight=weight, lpcd=lpcd
    )


def point(point_id: str, ward_id: str, lat: float = 17.40, lng: float = 78.45):
    return ss.ServicePoint(
        point_id,
        ward_id,
        f"Point {point_id}",
        lat,
        lng,
        "officer-1",
        "Community tap stand registered after field visit",
    )


# ---------------- service points ----------------


def test_service_point_list_starts_empty() -> None:
    registry = ss.ServicePointRegistry()
    assert registry.points == ()
    assert not hasattr(ss, "SEED_POINTS")


def test_registering_a_point_needs_reason_valid_location_and_known_ward() -> None:
    registry = ss.ServicePointRegistry()
    registry, event = registry.register(point("P1", "W1"), known_wards={"W1"})
    assert [p.point_id for p in registry.points] == ["P1"]
    entry = ledger.next_entry(None, **event, created_at_iso="2026-10-02T06:00:00+00:00", key="k")
    assert entry.payload["action"] == "service_point_registered"
    with pytest.raises(ValueError, match="reason"):
        registry.register(ss.ServicePoint("P2", "W1", "x", 17.4, 78.4, "o", " "), {"W1"})
    with pytest.raises(ValueError, match="coordinate"):
        registry.register(ss.ServicePoint("P2", "W1", "x", 95.0, 78.4, "o", "ok"), {"W1"})
    with pytest.raises(ValueError, match="ward"):
        registry.register(point("P2", "NOPE"), known_wards={"W1"})
    with pytest.raises(ValueError, match="already"):
        registry.register(point("P1", "W1"), known_wards={"W1"})


# ---------------- targets and sharing ----------------


def test_target_is_people_off_premises_times_norm_with_15_lpcd_floor() -> None:
    assert ss.target_litres(sw("W", 1000)) == 1000 * CFG.minimum_litres_per_person_day
    assert ss.target_litres(sw("W", 1000, lpcd=20)) == 20_000
    with pytest.raises(ValueError, match="15"):
        ss.target_litres(sw("W", 1000, lpcd=10))


def test_enough_reserve_meets_every_target() -> None:
    shares = ss.share_reserve([sw("A", 1000), sw("B", 500)], reserve_litres=100_000)
    assert shares["A"].litres == 15_000 and shares["B"].litres == 7_500
    assert all(s.status == "TARGET_MET" for s in shares.values())


def test_floors_first_then_extra_by_need_weight_without_exceeding_targets() -> None:
    wards = [sw("A", 1000, weight=2.0, lpcd=30), sw("B", 1000, weight=1.0, lpcd=30)]
    # floors 15,000 each; targets 30,000 each; 10,000 extra to share 2:1
    shares = ss.share_reserve(wards, reserve_litres=40_000)
    assert shares["A"].litres == pytest.approx(15_000 + 10_000 * 2 / 3)
    assert shares["B"].litres == pytest.approx(15_000 + 10_000 * 1 / 3)
    assert all(s.status == "FLOOR_MET" for s in shares.values())


def test_capped_ward_releases_its_extra_to_others() -> None:
    wards = [sw("A", 1000, weight=5.0, lpcd=16), sw("B", 1000, weight=1.0, lpcd=40)]
    shares = ss.share_reserve(wards, reserve_litres=50_000)
    assert shares["A"].litres == pytest.approx(16_000)  # its target, not more
    assert shares["B"].litres == pytest.approx(34_000)
    assert sum(s.litres for s in shares.values()) == pytest.approx(50_000)


def test_too_little_reserve_gives_every_ward_the_same_fraction_of_its_floor() -> None:
    shares = ss.share_reserve([sw("A", 1000, weight=3.0), sw("B", 3000)], reserve_litres=30_000)
    assert shares["A"].litres / 15_000 == pytest.approx(shares["B"].litres / 45_000)
    assert sum(s.litres for s in shares.values()) == pytest.approx(30_000)
    assert all(s.status == "FLOOR_NOT_MET" for s in shares.values())


def test_sharing_does_not_depend_on_location() -> None:
    """Distance has no role in how much water a ward gets (only in routing cost)."""
    assert "lat" not in ss.ScheduledWard.__dataclass_fields__
    assert "distance" not in str(ss.share_reserve.__annotations__)


# ---------------- plan, routing and timetable ----------------


def fleet():
    return [vrp.Tanker("T1", CFG.tanker_load_litres, DEPOT)], [vrp.Station("S1", DEPOT)]


def test_ward_without_a_service_point_is_reported_not_skipped() -> None:
    tankers, stations = fleet()
    plan = ss.plan_scheduled_supply(
        [sw("A", 1000)],
        ss.ServicePointRegistry(),
        tankers,
        stations,
        reserve_litres=20_000,
        time_limit_s=1,
    )
    assert plan.timetable == []
    assert plan.wards["A"].status == "NEEDS_SERVICE_POINT"


def test_plan_routes_points_and_publishes_a_timetable() -> None:
    tankers, stations = fleet()
    registry = ss.ServicePointRegistry()
    registry, _ = registry.register(point("P1", "A", 17.41, 78.42), {"A", "B"})
    registry, _ = registry.register(point("P2", "B", 17.43, 78.44), {"A", "B"})
    plan = ss.plan_scheduled_supply(
        [sw("A", 1000, weight=2.0), sw("B", 600)],
        registry,
        tankers,
        stations,
        reserve_litres=40_000,
        time_limit_s=2,
    )
    assert plan.wards["A"].litres == 15_000 and plan.wards["B"].litres == 9_000
    assert {row.point_id for row in plan.timetable} == {"P1", "P2"}
    for row in plan.timetable:
        assert row.tanker_id == "T1" and row.litres > 0
        assert row.arrival.startswith("06:") or row.arrival[:2].isdigit()
    delivered = sum(row.litres for row in plan.timetable)
    assert delivered == sum(stop.litres for r in plan.routing.routes for stop in r.stops)


def test_far_away_point_changes_routing_cost_but_not_the_share() -> None:
    tankers, stations = fleet()
    near, far = ss.ServicePointRegistry(), ss.ServicePointRegistry()
    near, _ = near.register(point("P1", "A", 17.441, 78.401), {"A"})
    far, _ = far.register(point("P1", "A", 17.50, 78.55), {"A"})
    a = ss.plan_scheduled_supply([sw("A", 300)], near, tankers, stations, 10_000, time_limit_s=1)
    b = ss.plan_scheduled_supply([sw("A", 300)], far, tankers, stations, 10_000, time_limit_s=1)
    assert a.wards["A"].litres == b.wards["A"].litres
    assert b.routing.total_km > a.routing.total_km


# ---------------- real data: which wards are scheduled ----------------


def test_scheduled_wards_from_a2_and_officer_confirmed_candidates() -> None:
    from pathlib import Path

    from app.services import service_models

    root = Path(__file__).resolve().parents[2]
    evidence = service_models.load_evidence(root)
    needs = service_models.build_ward_needs(evidence, ())
    # The Census rule routes no ward to scheduled supply, so nothing is scheduled until an
    # officer confirms a candidate.
    assert ss.scheduled_wards(needs, evidence, confirmed=set()) == []
    candidates = [n for n in needs if n.scheduled_supply_candidate]
    chosen = {candidates[0].ward_id, candidates[1].ward_id}
    wards = ss.scheduled_wards(needs, evidence, confirmed=chosen)
    assert {w.ward_id for w in wards} == chosen
    row = next(r for r in evidence if r["ward_id"] == candidates[0].ward_id)
    first = next(w for w in wards if w.ward_id == candidates[0].ward_id)
    assert first.people_off_premises == pytest.approx(float(row["population"]) * float(row["wad"]))
    assert first.need_weight == candidates[0].need_weight
    with pytest.raises(ValueError, match="candidate"):
        ss.scheduled_wards(needs, evidence, confirmed={"relation/does-not-exist"})
