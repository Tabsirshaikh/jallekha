"""Plans by HMWSSB section from a month's real totals divided by days (section_plan.py)."""

from __future__ import annotations

import calendar
from pathlib import Path

from conftest import auth

from app.services import section_plan

ROOT = Path(__file__).resolve().parents[3]


def test_daily_counts_add_up_to_the_month_total_and_differ_by_at_most_one() -> None:
    for total in (0, 1, 7, 412, 116195):
        days = calendar.monthrange(2025, 5)[1]
        counts = [section_plan.daily_count(total, days, i) for i in range(days)]
        assert sum(counts) == total
        assert max(counts) - min(counts) <= 1


def test_every_section_has_a_station_connections_and_flagged_estimates() -> None:
    sections = section_plan.load_sections(ROOT)
    assert len(sections) == 197
    assert all(s.connections > 0 and s.station for s in sections.values())
    own = [s for s in sections.values() if s.need_basis == section_plan.NEED_OWN]
    estimated = [s for s in sections.values() if s.need_basis != section_plan.NEED_OWN]
    assert len(own) == 170 and len(estimated) == 27
    gate = section_plan.SectionGate(sections).assess([s.group for s in sections.values()])
    assert {g for g, a in gate.items() if a.needs_check} >= {s.group for s in estimated}


def test_station_capacity_adds_up_to_the_trips_of_the_scenario() -> None:
    sections = section_plan.load_sections(ROOT)
    assert sum(section_plan.station_capacity(ROOT, sections, "fleet").values()) == 10350
    tight = section_plan.station_capacity(ROOT, sections, "tight")
    assert sum(tight.values()) == section_plan.total_trips(ROOT, "tight") < 10350


def test_section_plan_through_the_api(client) -> None:  # type: ignore[no-untyped-def]
    body = {"day": "2025-05-15", "unit": "section", "capacity": "tight"}
    first = client.post("/plans", json=body, headers=auth("officer"))
    assert first.status_code == 201, first.text
    plan = first.json()
    assert plan["plan_id"] == "section-2025-05-15-tight" and plan["unit"] == "section"
    assert plan["status"] == "DRAFT" and plan["flags_total"] > 0
    served = sum(s["served_total"] for s in plan["stations"].values())
    waiting = sum(s["waiting_total"] for s in plan["stations"].values())
    assert served + waiting > 6000 and waiting > 0  # the tight scenario leaves some waiting
    assert all(g.startswith("section:") for g in plan["effective_entitlement"])
    # the same request again returns the stored plan, nothing new is built
    again = client.post("/plans", json=body, headers=auth("officer"))
    assert again.status_code == 200 and again.json()["digest"] == plan["digest"]
    # the plan reads back (rebuilt from its recipe, digest checked)
    assert client.get(f"/plans/{plan['plan_id']}", headers=auth("officer")).status_code == 200
    # flagged sections are the ones with an estimated need; approval waits for their checks
    confidence = client.get(f"/plans/{plan['plan_id']}/confidence", headers=auth("officer")).json()
    assert any(g["needs_check"] for g in confidence["groups"])
    approve = {"officer_id": "officer-01", "reason": "Reviewed for the test"}
    blocked = client.post(
        f"/plans/{plan['plan_id']}/approve", json=approve, headers=auth("officer")
    )
    assert blocked.status_code == 409


def test_section_plan_rejects_other_years_and_supplied_bookings(client) -> None:  # type: ignore[no-untyped-def]
    other = client.post(
        "/plans", json={"day": "2026-05-15", "unit": "section"}, headers=auth("officer")
    )
    assert other.status_code == 404
    both = client.post(
        "/plans",
        json={"day": "2025-05-15", "unit": "section", "bookings": [{"booking_id": "x"}]},
        headers=auth("officer"),
    )
    assert both.status_code == 422
