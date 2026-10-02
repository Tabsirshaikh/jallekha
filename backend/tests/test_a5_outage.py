"""A5: outage response (F10): one creation function, detection from de-duplicated complaints,
deprivation-cost priority, tier 0 first, 10-15 lpcd, no water debt."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app.config.allocation import ALLOCATION_CONFIG
from app.services import dedup, ledger, outage, service_models

CFG = ALLOCATION_CONFIG
T0 = datetime(2026, 5, 10, 6, 0, tzinfo=UTC)  # T1 requires timezone-aware times
WARDS = {"W1", "W2", "W3"}


def make(oid: str = "O1", wards=("W1",), hours_ago: float = 6, people: float = 1000, **kw):
    event, _ = outage.create_outage(
        outage_id=oid,
        ward_ids=wards,
        start=T0 - timedelta(hours=hours_ago),
        end=kw.get("end"),
        source=kw.get("source", "officer"),
        reason=kw.get("reason", "Main line burst near reservoir"),
        created_by="officer-1",
        known_wards=WARDS,
        people_affected=people,
    )
    return event


# ---------------- creation (also used by T5 notices) ----------------


def test_create_outage_records_area_hours_source_and_a_ledger_entry() -> None:
    event, args = outage.create_outage(
        outage_id="O1",
        ward_ids=("W1", "W2"),
        start=T0,
        end=T0 + timedelta(hours=24),
        source="notice",
        reason="HMWSSB notice: 24 h shutdown for pipeline work",
        created_by="t5-notice-feed",
        known_wards=WARDS,
        people_affected=5000,
    )
    assert event.ward_ids == ("W1", "W2") and event.source == "notice"
    assert event.planned_hours == 24
    entry = ledger.next_entry(None, **args, created_at_iso="2026-05-10T06:00:00+00:00", key="k")
    assert entry.event_type == "outage_created"
    assert entry.payload["source"] == "notice" and entry.payload["ward_ids"] == ["W1", "W2"]


@pytest.mark.parametrize(
    "changes,message",
    [
        ({"ward_ids": ("NOPE",)}, "ward"),
        ({"ward_ids": ()}, "ward"),
        ({"source": "rumour"}, "source"),
        ({"reason": " "}, "reason"),
        ({"end": T0 - timedelta(hours=1)}, "end"),
        ({"people_affected": -5}, "people"),
    ],
)
def test_bad_outage_is_rejected(changes: dict, message: str) -> None:
    args = {
        "outage_id": "O1",
        "ward_ids": ("W1",),
        "start": T0,
        "end": None,
        "source": "officer",
        "reason": "Burst main",
        "created_by": "o-1",
        "known_wards": WARDS,
        "people_affected": 100,
    }
    args.update(changes)
    with pytest.raises(ValueError, match=message):
        outage.create_outage(**args)


# ---------------- detection from complaints (T1 duplicates removed) ----------------


def complaint(i: int, ward: str = "W1", minutes: int = 0, lat: float = 17.40, lon: float = 78.40):
    return dedup.ComplaintRecord(
        id=f"c{i}",
        category="no_water",
        lat=lat,
        lon=lon,
        created_at=T0 + timedelta(minutes=minutes),
        household_id=f"h{i}",
        area=ward,
    )


def spread(i: int, ward: str = "W1", minutes: int = 0):
    # 1 km apart, so T1 does not merge them
    return complaint(i, ward, minutes, lat=17.40 + i * 0.01, lon=78.40)


def test_enough_distinct_no_water_reports_make_a_candidate() -> None:
    reports = [spread(i, minutes=i * 30) for i in range(CFG.outage_min_distinct_reports)]
    candidates = outage.detect_from_complaints(reports, now=T0 + timedelta(hours=3))
    assert [c.ward_id for c in candidates] == ["W1"]
    assert candidates[0].distinct_reports == CFG.outage_min_distinct_reports
    assert candidates[0].needs_officer_confirmation


def test_duplicates_do_not_count_twice() -> None:
    # same household, same place: T1 links them, so they are one report
    reports = [complaint(0, minutes=m) for m in range(0, 50, 10)]
    reports = [
        dedup.ComplaintRecord(
            r.id + str(k), r.category, r.lat, r.lon, r.created_at, "same-house", area="W1"
        )
        for k, r in enumerate(reports)
    ]
    assert outage.detect_from_complaints(reports, now=T0 + timedelta(hours=1)) == []


def test_old_or_other_category_reports_are_ignored() -> None:
    window = CFG.outage_detection_window_hours
    old = [spread(i, minutes=-int(window * 60) - 60 - i) for i in range(10)]
    leaks = [
        dedup.ComplaintRecord(f"l{i}", "leak", 17.40 + i * 0.01, 78.40, T0, f"lh{i}", area="W1")
        for i in range(10)
    ]
    assert outage.detect_from_complaints(old + leaks, now=T0) == []


# ---------------- priority and response ----------------


def test_deprivation_weight_rises_faster_the_longer_people_wait() -> None:
    w = [outage.deprivation_weight(h) for h in (0, 12, 24, 48, 72)]
    assert w == sorted(w) and w[0] > 0
    assert (w[4] - w[3]) > (w[2] - w[1])  # convex: each extra day costs more


def test_longer_outage_is_served_first_when_water_is_short() -> None:
    short, long = make("SHORT", hours_ago=4), make("LONG", ("W2",), hours_ago=40)
    floor = 1000 * CFG.outage_floor_lpcd
    plan = outage.plan_response([short, long], [], capacity_litres=floor, now=T0)
    by_id = {a.outage_id: a for a in plan.allocations}
    assert by_id["LONG"].litres == floor and by_id["SHORT"].litres == 0
    assert by_id["LONG"].priority > by_id["SHORT"].priority


def test_critical_facilities_come_first() -> None:
    hospital = outage.CriticalStop("H1", "Area hospital", "W1", litres=10_000)
    plan = outage.plan_response([make()], [hospital], capacity_litres=10_000, now=T0)
    assert plan.critical[0].litres == 10_000
    assert plan.allocations[0].litres == 0


def test_floor_for_everyone_then_top_up_to_target_never_more() -> None:
    a, b = make("A", hours_ago=30), make("B", ("W2",), hours_ago=5)
    plenty = outage.plan_response([a, b], [], capacity_litres=1_000_000, now=T0)
    assert all(x.litres == 1000 * CFG.outage_target_lpcd for x in plenty.allocations)
    assert all(x.status == "TARGET_MET" for x in plenty.allocations)
    floors_plus = 2 * 1000 * CFG.outage_floor_lpcd + 2000
    some = outage.plan_response([a, b], [], capacity_litres=floors_plus, now=T0)
    by_id = {x.outage_id: x for x in some.allocations}
    assert by_id["A"].litres == 1000 * CFG.outage_floor_lpcd + 2000  # longer outage tops up first
    assert by_id["B"].litres == 1000 * CFG.outage_floor_lpcd
    assert by_id["B"].status == "FLOOR_MET"


def test_ended_outage_needs_nothing() -> None:
    ended = make("E", end=T0 - timedelta(hours=1))
    plan = outage.plan_response([ended], [], capacity_litres=50_000, now=T0)
    assert plan.allocations == [] and plan.ended == ["E"]


def test_outage_water_never_counts_toward_debt() -> None:
    plan = outage.plan_response([make()], [], capacity_litres=50_000, now=T0)
    assert plan.counts_toward_water_debt is False


def test_people_affected_from_ward_population() -> None:
    root = Path(__file__).resolve().parents[2]
    evidence = service_models.load_evidence(root)
    ward = next(r for r in evidence if r["population"])
    assert outage.people_in_wards([ward["ward_id"]], evidence) == float(ward["population"])
