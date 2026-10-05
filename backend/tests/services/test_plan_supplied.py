"""Plans from bookings an officer supplies (not the committed replay).

There is no live booking feed: HMWSSB publishes monthly totals only. So the bookings of a day are
supplied (by an officer, or later by an import job) and planned with the same A7 planner and T9
gate. The bookings are stored in the recipe, so the plan rebuilds exactly. Capacity and need come
from the same ASSUMED fleet scenario and Census 2011 evidence as the replay.
"""

from __future__ import annotations

from datetime import date
from typing import Any

import pytest

from app.services import plan_builder
from app.services.service_models import NeedWeights

DAY = date(2026, 10, 3)  # outside the replay window on purpose


def _sections(count: int) -> list[str]:
    setup = plan_builder._setup()
    return [s for s in sorted(setup.ctx.network.home) if s in setup.ctx.mapping][:count]


def _bookings(count: int = 30, **overrides: Any) -> list[dict[str, Any]]:
    sections = _sections(3)
    rows = []
    for i in range(count):
        row = {
            "booking_id": f"B-2026-10-03-{i:04d}",
            "section": sections[i % len(sections)],
            "arrived_at": f"2026-10-03T03:{i % 60:02d}:00+05:30",
        }
        row.update(overrides)
        rows.append(row)
    return rows


def test_a_plan_is_built_from_supplied_bookings_on_any_day() -> None:
    bookings = _bookings(30)
    built = plan_builder.build_supplied_plan(DAY, bookings)
    plan = built.plan
    assert (
        plan.plan_id.startswith("plan-2026-10-03-")
        and len(plan.plan_id) == len("plan-2026-10-03-") + 8
    )
    assert built.recipe["source"] == "supplied_bookings" and built.recipe["day"] == "2026-10-03"
    assert len(built.recipe["bookings"]) == 30
    served = sum(len(s.served) for s in plan.stations.values())
    waiting = sum(len(s.waiting) for s in plan.stations.values())
    assert served + waiting == 30  # every supplied booking is either served or waiting
    assert "supplied" in built.basis["plan"].lower() and "ASSUMED" in built.basis["plan"]
    assert built.events and built.events[0][0] == "plan_created"


def test_the_order_of_the_input_does_not_change_the_plan() -> None:
    bookings = _bookings(24)
    a = plan_builder.build_supplied_plan(DAY, bookings)
    b = plan_builder.build_supplied_plan(DAY, list(reversed(bookings)))
    assert (a.plan.plan_id, a.plan.digest) == (b.plan.plan_id, b.plan.digest)


def test_different_bookings_make_a_different_plan() -> None:
    a = plan_builder.build_supplied_plan(DAY, _bookings(24))
    b = plan_builder.build_supplied_plan(DAY, _bookings(25))
    assert a.plan.plan_id != b.plan.plan_id


def test_a_supplied_plan_rebuilds_to_the_same_digest() -> None:
    built = plan_builder.build_supplied_plan(DAY, _bookings(24))
    again = plan_builder.rebuild(built.recipe)
    assert (again.plan.plan_id, again.plan.digest) == (built.plan.plan_id, built.plan.digest)


def test_category_tier_and_consumer_are_taken_from_the_bookings() -> None:
    rows = _bookings(6)
    rows[0].update(tier=0, category="commercial", consumer_id="c-hospital-1")
    built = plan_builder.build_supplied_plan(DAY, rows)
    by_id = {b.booking.booking_id: b.booking for b in built.inputs.pending}
    first = by_id[rows[0]["booking_id"]]
    assert (first.tier, first.category, first.consumer_id) == (0, "commercial", "c-hospital-1")
    other = by_id[rows[1]["booking_id"]]
    assert (other.tier, other.category, other.consumer_id) == (2, "domestic", rows[1]["booking_id"])


def test_a_critical_facility_booking_is_served_first_at_its_station() -> None:
    rows = _bookings(30)
    rows[7].update(tier=0)
    built = plan_builder.build_supplied_plan(DAY, rows)
    station = next(
        s
        for s in built.plan.stations.values()
        if rows[7]["booking_id"] in {b.booking_id for b in s.served}
    )
    assert station.served[0].booking_id == rows[7]["booking_id"]
    assert station.served[0].reason == "TIER_0"


def test_weights_make_a_separate_supplied_plan_that_can_be_compared() -> None:
    rows = _bookings(60)
    default = plan_builder.build_supplied_plan(DAY, rows)
    weighted = plan_builder.build_supplied_plan(DAY, rows, weights=NeedWeights(5.0, 0.0, 0.0))
    assert weighted.plan.plan_id == f"{default.plan.plan_id}-w5-0-0"
    assert weighted.recipe["weights"] == {"wad": 5.0, "cad": 0.0, "hardship": 0.0}
    result = plan_builder.compare_to_default(weighted)
    assert result["against"] == default.plan.plan_id
    assert sum(r["change"] for r in result["all_changes"]) == 0
    assert plan_builder.rebuild(weighted.recipe).plan.digest == weighted.plan.digest


@pytest.mark.parametrize(
    ("mutate", "words"),
    [
        (lambda rows: rows.clear(), "at least one"),
        (lambda rows: rows[1].update(booking_id=rows[0]["booking_id"]), "twice"),
        (lambda rows: rows[0].update(section="NO SUCH SECTION"), "section"),
        (lambda rows: rows[0].update(category="industrial"), "category"),
        (lambda rows: rows[0].update(tier=3), "tier"),
        (lambda rows: rows[0].update(arrived_at="2026-10-03T03:00:00"), "time zone"),
        (lambda rows: rows[0].update(arrived_at="yesterday"), "arrived_at"),
        (lambda rows: rows[0].update(arrived_at="2026-10-04T03:00:00+05:30"), "after"),
        (lambda rows: rows[0].update(consumer_id="c" * 65), "consumer_id"),
        (lambda rows: rows[0].update(booking_id="bad;id\n"), "booking_id"),
        (lambda rows: rows[0].pop("section"), "section"),
    ],
)
def test_unusable_bookings_are_refused_with_the_reason(mutate: Any, words: str) -> None:
    rows = _bookings(6)
    mutate(rows)
    with pytest.raises(plan_builder.InvalidBookings, match=words):
        plan_builder.build_supplied_plan(DAY, rows)


def test_too_many_bookings_are_refused() -> None:
    from app.config.plans import PLAN_STORE_CONFIG

    rows = _bookings(3)
    rows = [
        {**rows[i % 3], "booking_id": f"B-{i}"}
        for i in range(PLAN_STORE_CONFIG.max_supplied_bookings + 1)
    ]
    with pytest.raises(plan_builder.InvalidBookings, match="at most"):
        plan_builder.build_supplied_plan(DAY, rows)


def test_the_problems_of_all_bad_rows_are_listed_up_to_a_limit() -> None:
    rows = _bookings(6)
    for row in rows:
        row["category"] = "industrial"
    with pytest.raises(plan_builder.InvalidBookings) as info:
        plan_builder.build_supplied_plan(DAY, rows)
    assert str(info.value).count("category") >= 3
