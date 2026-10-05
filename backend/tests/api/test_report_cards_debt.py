"""The F20 loop over the API: a stop in a scheduled ward, a supplied plan that gives it loads, the
day's deliveries, an officer closing the day (water debt, A6), the next plan carrying the debt,
and the ward report card showing deliveries, debt and schedule. All data here is SYNTHETIC.
"""

from __future__ import annotations

import copy
import json
from dataclasses import replace
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pytest
from conftest import auth
from fastapi.testclient import TestClient

from app.config.allocation import ALLOCATION_CONFIG
from app.config.report_cards import REPORT_CARD_CONFIG
from app.db import create_all, make_engine
from app.main import app
from app.routers.common import get_now
from app.routers.stores import DeliveryStore, PlanStore, get_debt_store, get_plan_store
from app.services import delivery as dl
from app.services import plan_builder
from app.services.debt_store import DebtStore
from app.services.ledger_port import InMemoryLedger

DAY = "2026-10-03"
NEXT = "2026-10-04"
NOW = datetime(2026, 10, 5, 6, 0, tzinfo=UTC)
WARD = "relation/7848824"  # Ward 105 Gachibowli, scheduled supply
LOAD = ALLOCATION_CONFIG.tanker_load_litres
STOP: dict[str, Any] = {
    "stop_id": "stop-g1",
    "lat": 17.44437,
    "lon": 78.31387,
    "basis": "SYNTHETIC",
    "representatives": [
        {"id": "rep-g1", "phone": "+919800003101", "language": "te"},
        {"id": "rep-g2", "phone": "+919800003102", "language": "ur"},
    ],
    "residents": [
        {"id": f"res-g{i}", "phone": f"+91980000320{i}", "language": "te"} for i in range(1, 6)
    ],
}


@pytest.fixture
def api(client: TestClient, tmp_path: Path) -> TestClient:
    engine = make_engine(f"sqlite:///{(tmp_path / 'api.db').as_posix()}")
    create_all(engine)
    plans = PlanStore(engine)
    debts = DebtStore(engine)
    app.dependency_overrides[get_plan_store] = lambda: plans
    app.dependency_overrides[get_debt_store] = lambda: debts
    app.dependency_overrides[get_now] = lambda: NOW
    client.engine = engine  # type: ignore[attr-defined]
    return client


def _bookings(day: str, count: int = 12) -> list[dict[str, Any]]:
    setup = plan_builder._setup()
    sections = [s for s in sorted(setup.ctx.network.home) if s in setup.ctx.mapping][:3]
    return [
        {
            "booking_id": f"B-{day}-{i:03d}",
            "section": sections[i % 3],
            "arrived_at": f"{day}T03:{i:02d}:00+05:30",
        }
        for i in range(count)
    ]


def _approved_plan(api: TestClient, day: str) -> dict[str, Any]:
    created = api.post(
        "/plans", json={"day": day, "bookings": _bookings(day)}, headers=auth("officer")
    )
    assert created.status_code in (200, 201), created.text  # 200: already stored as a draft
    view = created.json()
    for group in view["flags"]:
        checked = api.post(
            f"/plans/{view['plan_id']}/groups/{group}/check",
            json={"officer_id": "off-1", "reason": "checked on the ground"},
            headers=auth("officer"),
        )
        assert checked.status_code == 200, checked.text
    approved = api.post(
        f"/plans/{view['plan_id']}/approve",
        json={"officer_id": "off-1", "reason": "approved for the day"},
        headers=auth("officer"),
    )
    assert approved.status_code == 200, approved.text
    return approved.json()


def _deliver(api: TestClient, delivery_id: str, outcome: str | None, day: str = DAY) -> None:
    store = DeliveryStore(api.engine)  # type: ignore[attr-defined]
    stop = store.get_stop("stop-g1")
    assert stop is not None
    at = datetime.fromisoformat(f"{day}T09:00:00+05:30")
    chain = InMemoryLedger(key="test-ledger-key", clock=lambda: at)
    state = dl.start_delivery(
        delivery_id, stop.stop_id, stop.lat, stop.lon, "drv-1", stop.representatives, chain, at
    )
    if outcome is not None:
        state = replace(
            state, outcome=dl.OutcomeDecision(outcome, "majority", True, 3, 0, 0, "SYNTHETIC")
        )  # type: ignore[arg-type]
    store.put_delivery(state)


def _close(api: TestClient, day: str, plan_id: str, role: str = "officer") -> Any:
    return api.post(
        f"/debt/days/{day}/close",
        json={"plan_id": plan_id, "officer_id": "off-1", "reason": "all deliveries closed"},
        headers=auth(role),
    )


def _register_stop(api: TestClient) -> None:
    registered = api.post("/stops", json=copy.deepcopy(STOP), headers=auth("officer"))
    assert registered.status_code == 200, registered.text
    assert registered.json()["ward_id"] == WARD


def test_the_whole_loop_from_stop_to_report_card(api: TestClient) -> None:
    _register_stop(api)
    plan = _approved_plan(api, DAY)
    (allotted,) = plan["stops"]
    assert allotted["stop_id"] == "stop-g1" and allotted["ward_id"] == WARD
    assert allotted["ward_name"] == "Ward 105 Gachibowli" and allotted["litres"] > LOAD
    assert plan["debts_used"] == 0
    _deliver(api, "d1", "Confirmed")
    _deliver(api, "d2", "Disputed")

    closed = _close(api, DAY, plan["plan_id"])
    assert closed.status_code == 200, closed.text
    body = closed.json()
    assert body["day"] == DAY and body["plan_id"] == plan["plan_id"]
    (ward,) = body["wards"]
    assert ward["ward_id"] == WARD and ward["ward_name"] == "Ward 105 Gachibowli"
    assert ward["planned_litres"] == allotted["litres"] and ward["credited_litres"] == LOAD
    assert ward["debt_after"] == allotted["litres"] - LOAD
    assert ward["deliveries"] == {"Confirmed": 1, "Disputed": 1}

    accounts = api.get("/debt/accounts", headers=auth("officer")).json()
    assert accounts["total"] == 1
    assert accounts["items"][0]["ward_id"] == WARD
    assert accounts["items"][0]["debt_litres"] == allotted["litres"] - LOAD
    days = api.get("/debt/days", headers=auth("officer")).json()
    assert [d["day"] for d in days["items"]] == [DAY]

    card = api.get(f"/wards/{WARD}/report-card", headers=auth("resident")).json()
    assert card["deliveries"]["basis"] == "SYNTHETIC"
    assert card["deliveries"]["value"]["by_outcome"]["Confirmed"] == 1
    assert card["debt"]["value"]["debt_litres"] == allotted["litres"] - LOAD
    assert card["debt"]["value"]["last_day"]["day"] == DAY
    schedule = card["schedule"]["value"]
    assert schedule["plan_id"] == plan["plan_id"] and schedule["status"] == "APPROVED"
    assert schedule["stops"][0]["stop_id"] == "stop-g1"

    sms = api.get(f"/wards/{WARD}/sms-summary", headers=auth("resident")).json()
    assert "1 confirmed" in sms["text"] and "tanker loads owed" in sms["text"]
    for public in (json.dumps(card), json.dumps(sms)):  # what a resident reads
        assert "+91" not in public and "98000031" not in public and "98000032" not in public
        assert "all deliveries closed" not in public and "off-1" not in public

    # the next day's plan carries the debt: the ward's turns go up
    nxt = api.post(
        "/plans", json={"day": NEXT, "bookings": _bookings(NEXT)}, headers=auth("officer")
    )
    assert nxt.status_code == 201, nxt.text
    assert nxt.json()["debts_used"] == 1 and "debts" in nxt.json()["basis"]
    plain = plan_builder.build_supplied_plan(date(2026, 10, 4), _bookings(NEXT)).plan
    group = f"ward:{WARD}"
    assert nxt.json()["effective_entitlement"][group] > plain.effective_entitlement[group]


def test_a_day_closes_only_in_order_once_and_after_it_ends(api: TestClient) -> None:
    _register_stop(api)
    plan = _approved_plan(api, DAY)
    today = NOW.astimezone(REPORT_CARD_CONFIG.service_timezone).date().isoformat()
    not_over = _close(api, today, plan["plan_id"])
    assert not_over.status_code == 409 and "not over" in not_over.text
    assert _close(api, DAY, plan["plan_id"]).status_code == 200
    again = _close(api, DAY, plan["plan_id"])
    assert again.status_code == 409 and "already closed" in again.text
    earlier = _close(api, "2026-10-02", plan["plan_id"])
    assert earlier.status_code == 409 and "order" in earlier.text
    gap = _close(api, "2026-10-05", plan["plan_id"])  # 10-04 not closed yet (and 10-05 is today)
    assert gap.status_code == 409
    skipped = api.post(
        "/debt/days/2026-10-02/close",
        json={"officer_id": "off-1", "reason": "x"},
        headers=auth("officer"),
    )
    assert skipped.status_code == 409


def test_days_close_without_gaps_and_a_day_without_a_plan_can_be_closed(api: TestClient) -> None:
    _register_stop(api)
    plan = _approved_plan(api, "2026-10-02")
    assert _close(api, "2026-10-02", plan["plan_id"]).status_code == 200
    owed = api.get("/debt/accounts", headers=auth("officer")).json()["items"][0]["debt_litres"]
    jump = api.post(
        "/debt/days/2026-10-04/close",
        json={"officer_id": "off-1", "reason": "no plan"},
        headers=auth("officer"),
    )
    assert jump.status_code == 409 and "2026-10-03" in jump.text
    _deliver(api, "d-free", "Confirmed", day=DAY)  # a delivery on a day without a plan
    no_plan = api.post(
        f"/debt/days/{DAY}/close",
        json={"officer_id": "off-1", "reason": "no plan was made that day"},
        headers=auth("officer"),
    )
    assert no_plan.status_code == 200, no_plan.text
    body = no_plan.json()
    assert body["plan_id"] is None
    (ward,) = body["wards"]
    assert ward["planned_litres"] == 0 and ward["credited_litres"] == LOAD
    assert ward["debt_after"] == owed - LOAD


def test_only_an_approved_supplied_plan_with_closed_deliveries_can_close_a_day(
    api: TestClient,
) -> None:
    _register_stop(api)
    replay = api.post("/plans", json={"day": "2025-05-01"}, headers=auth("officer"))
    assert replay.status_code == 201, replay.text
    simulated = _close(api, "2025-05-01", replay.json()["plan_id"])
    assert simulated.status_code == 409 and "simulation" in simulated.text.lower()

    draft = api.post(
        "/plans", json={"day": DAY, "bookings": _bookings(DAY)}, headers=auth("officer")
    )
    not_approved = _close(api, DAY, draft.json()["plan_id"])
    assert not_approved.status_code == 409 and "approved" in not_approved.text

    plan = _approved_plan(api, DAY)
    _deliver(api, "d-open", None)
    still_open = _close(api, DAY, plan["plan_id"])
    assert still_open.status_code == 409 and "d-open" in still_open.text

    assert _close(api, DAY, "plan-missing").status_code == 404
    assert _close(api, DAY, plan["plan_id"], role="driver").status_code == 403
    assert api.get("/debt/accounts", headers=auth("resident")).status_code == 403
    assert api.get("/debt/accounts", headers=auth("officer")).json()["total"] == 0


def test_a_ward_with_nothing_yet_says_so_on_its_card(api: TestClient) -> None:
    card = api.get("/wards/relation/7848859/report-card", headers=auth("resident")).json()
    assert (
        card["deliveries"]["value"] is None and "no delivery stop" in card["deliveries"]["reason"]
    )
    assert card["debt"]["value"] is None and "no closed day" in card["debt"]["reason"]
    assert card["schedule"]["value"] is None and "no plan" in card["schedule"]["reason"]
    sms = api.get("/wards/relation/7848859/sms-summary", headers=auth("resident")).json()
    assert "not available" in sms["text"]
