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
    totals = plan["group_totals"]
    assert sum(t["served"] + t["waiting"] for t in totals.values()) == served + waiting
    by_ward = sum(w["served"] + w["waiting"] for w in plan["ward_totals"].values())
    placed = by_ward + plan["ward_unplaced"]["served"] + plan["ward_unplaced"]["waiting"]
    assert abs(placed - (served + waiting)) < 5  # shared over wards by building share, rounded
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


def _served_reasons(plan: dict) -> dict[str, int]:
    out: dict[str, int] = {}
    for station in plan["stations"].values():
        for booking in station["served"]:
            out[booking["reason"]] = out.get(booking["reason"], 0) + 1
    return out


def test_priority_classes_scheduled_supply_and_carry_over(client) -> None:  # type: ignore[no-untyped-def]
    base = {"day": "2025-05-15", "unit": "section", "capacity": "tight"}
    full = client.post("/plans", json=base, headers=auth("officer")).json()
    plain = client.post(
        "/plans",
        json={**base, "priority": False, "scheduled": "none", "carry_over": False},
        headers=auth("officer"),
    )
    assert plain.status_code == 201
    plain = plain.json()
    assert plain["plan_id"] != full["plan_id"]  # options other than the defaults change the id
    # estimated priority classes: hospital bookings first, then the no-water share
    reasons = _served_reasons(full)
    assert reasons.get("TIER_0", 0) > 0 and reasons.get("TIER_1", 0) > 0
    assert set(_served_reasons(plain)) == {"DRR"}
    # scheduled supply for the sections the field-check screen flags
    assert full["scheduled_total"] == 12 and plain["scheduled_total"] == 0
    assert all(k.startswith("section:") for k in full["scheduled"])

    # carry-over: bookings left waiting on the days before are planned again today
    def booked(p: dict) -> int:
        return sum(s["served_total"] + s["waiting_total"] for s in p["stations"].values())

    assert booked(full) > booked(plain)
    assert "carried over" in full["basis"]["plan"]


def test_a_supply_notice_makes_an_outage_response_by_section(client) -> None:  # type: ignore[no-untyped-def]
    notice = {
        "source": "hmwssb_press_release",
        "raw_text": "Water supply will be interrupted in Gachibowli for pipeline works.",
        "area_names": ["Gachibowli"],
        "start": "2025-05-14T06:00:00+05:30",
        "end": "2025-05-16T06:00:00+05:30",
        "entered_by": "officer-7",
        "is_synthetic": True,
    }
    assert client.post("/notices", json=notice, headers=auth("officer")).status_code == 200
    body = {"day": "2025-05-15", "unit": "section", "capacity": "fleet", "carry_over": False}
    plan = client.post("/plans", json=body, headers=auth("officer")).json()
    assert plan["outage"]["allocations"], plan["outage"]
    cut = plan["outage"]["allocations"][0]
    assert all(g.startswith("section:") for g in cut["ward_ids"])
    assert plan["outage_trips"] > 0 and plan["outage"]["critical"]  # critical facilities first
    assert "outage notices" in plan["basis"]["plan"]


def _approve(client, plan: dict) -> None:  # type: ignore[no-untyped-def]
    plan_id = plan["plan_id"]
    for group in plan["flags"]:
        checked = client.post(
            f"/plans/{plan_id}/groups/{group}/check",
            json={"officer_id": "officer-01", "reason": "Checked for the test"},
            headers=auth("officer"),
        )
        assert checked.status_code == 200, checked.text
    approved = client.post(
        f"/plans/{plan_id}/approve",
        json={"officer_id": "officer-01", "reason": "Approved for the test"},
        headers=auth("officer"),
    )
    assert approved.status_code == 200, approved.text


def test_closing_a_day_settles_section_debt_and_the_next_plan_uses_it(client) -> None:  # type: ignore[no-untyped-def]
    body = {"day": "2025-05-15", "unit": "section", "capacity": "fleet", "carry_over": False}
    plan = client.post("/plans", json=body, headers=auth("officer")).json()
    _approve(client, plan)
    closed = client.post(
        "/debt/days/2025-05-15/close",
        json={"plan_id": plan["plan_id"], "officer_id": "officer-01", "reason": "Day over"},
        headers=auth("officer"),
    )
    assert closed.status_code == 200, closed.text
    sections = closed.json()["wards"]
    assert len(sections) > 100 and all(w["ward_id"].startswith("section:") for w in sections)
    # nothing was confirmed delivered, so each section keeps what it booked as debt
    owed = sections[0]
    assert owed["credited_litres"] == 0 and owed["debt_after"] == owed["planned_litres"] > 0
    accounts = client.get("/debt/accounts?limit=200", headers=auth("officer")).json()["items"]
    assert accounts and all(a["unit"] == "section" for a in accounts)
    assert accounts[0]["ward_id"] is None and accounts[0]["ward_name"]
    # the next day's plan reads those accounts: a section in debt gets more turns
    nxt = {**body, "day": "2025-05-16"}
    after = client.post("/plans", json=nxt, headers=auth("officer"))
    assert after.status_code == 201, after.text
    after = after.json()
    assert after["debts_used"] > 100  # the saved section accounts reach the plan
    group = "section:" + owed["ward_name"]
    assert after["effective_entitlement"][group] > plan["effective_entitlement"][group]


def test_tanker_routes_of_a_plan_by_section(client) -> None:  # type: ignore[no-untyped-def]
    body = {"day": "2025-05-15", "unit": "section", "capacity": "tight", "carry_over": False}
    plan = client.post("/plans", json=body, headers=auth("officer")).json()
    served = sum(s["served_total"] for s in plan["stations"].values())
    routes = client.get(f"/plans/{plan['plan_id']}/routes", headers=auth("officer"))
    assert routes.status_code == 200, routes.text
    data = routes.json()
    summary = data["summary"]
    # every served booking and every reserved scheduled-supply load is driven, none dropped
    assert summary["unscheduled"] == 0 and summary["trips"] >= served
    assert summary["tankers"] <= summary["fleet"] == 1150
    assert summary["special_trips"] > 0 and data["tankers"] == []  # trips only for one station
    # one station's tankers: named, with timed round trips inside the working day
    station = data["stations"][0]["station_id"]
    one = client.get(
        f"/plans/{plan['plan_id']}/routes?station={station}", headers=auth("officer")
    ).json()
    assert one["tankers"] and all(t["station_id"] == station for t in one["tankers"])
    trip = one["tankers"][0]["trips"][0]
    assert trip["depart"] >= "06:00" and trip["back"] <= "22:00" and trip["km"] > 0
    assert trip["leg_basis"] in ("OSRM", "ESTIMATE")
    for tanker in one["tankers"]:
        times = [t["back"] for t in tanker["trips"]]
        assert times == sorted(times)  # a tanker's trips follow one another
    assert (
        client.get(
            f"/plans/{plan['plan_id']}/routes?station=NOPE", headers=auth("officer")
        ).status_code
        == 404
    )
    # every tanker's day in a small form for the city-wide animation
    city = client.get(
        f"/plans/{plan['plan_id']}/routes?compact=true", headers=auth("officer")
    ).json()
    assert data["paths"] is None and len(city["paths"]) == summary["tankers"]
    trips = [t for p in city["paths"] for t in p["trips"]]
    assert 0 <= summary["trips"] - len(trips) < 10  # trips to a place with no location left out
    assert all(t[2] < t[3] <= t[4] < t[5] <= 22 * 60 for t in trips)


def test_routes_are_only_for_plans_by_section(client) -> None:  # type: ignore[no-untyped-def]
    made = client.post("/plans", json={"day": "2025-05-01"}, headers=auth("officer")).json()
    refused = client.get(f"/plans/{made['plan_id']}/routes", headers=auth("officer"))
    assert refused.status_code == 409


def test_overview_of_a_plan_by_section_adds_up(client) -> None:  # type: ignore[no-untyped-def]
    body = {"day": "2025-05-15", "unit": "section", "capacity": "tight"}
    plan = client.post("/plans", json=body, headers=auth("officer")).json()
    overview = plan["overview"]
    facts, sections = overview["facts"], overview["sections"]
    served = sum(s["served_total"] for s in plan["stations"].values())
    waiting = sum(s["waiting_total"] for s in plan["stations"].values())
    # the figures are the plan's own: bookings, served and waiting, priority classes
    assert facts["served"] == served and facts["waiting"] == waiting
    assert facts["bookings"] == served + waiting == sum(facts["tiers"])
    assert 0 < facts["carried"] < facts["bookings"]
    assert facts["trips"] == plan["trips_total"]
    assert facts["reserve_trips"] == plan["reserve_trips"] >= facts["reserve_used_trips"] > 0
    assert facts["served_tiers"][0] <= facts["tiers"][0] and facts["served_tiers"][1] > 0
    # every section has a row and a service type; scheduled ones carry their water
    assert len(sections) == 197
    kinds = {s["category"] for s in sections}
    assert kinds <= {"cut", "scheduled", "heavy", "normal", "unknown"}
    assert {"scheduled", "heavy", "normal"} <= kinds
    scheduled = [s for s in sections if s["category"] == "scheduled"]
    assert len(scheduled) == facts["scheduled_sections"] == 12
    assert all(s["scheduled"]["litres"] > 0 and s["scheduled"]["loads"] > 0 for s in scheduled)
    for s in sections:
        assert s["served"] + s["waiting"] == s["bookings"] == sum(s["tiers"])
    # each station's bookings by section add up to the day's bookings
    held = sum(sum(st["bookings"].values()) for st in overview["stations"])
    assert held == facts["bookings"]
    # a plan by ward has no overview
    ward = client.post("/plans", json={"day": "2025-05-01"}, headers=auth("officer")).json()
    assert ward["overview"] is None
