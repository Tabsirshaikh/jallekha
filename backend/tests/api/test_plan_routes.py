"""POST /plans and GET /plans (Wave 1) on a DB-backed store, and the existing plan routes
after a restart. Plans are real replay plans (SIMULATION) gated by T9."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from conftest import auth, conforms, example
from fastapi.testclient import TestClient
from sqlalchemy import update
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.config.confidence import CONFIDENCE_CONFIG
from app.db import create_all, make_engine
from app.main import app
from app.models import StoredPlan
from app.routers import plans
from app.routers.stores import PlanStore, get_plan_store

DAY = "2025-03-01"
PLAN_ID = "replay-2025-03-01"


@pytest.fixture
def db(tmp_path: Path) -> Iterator[Engine]:
    engine = make_engine(f"sqlite:///{(tmp_path / 'plans.db').as_posix()}")
    create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def api(client: TestClient, db: Engine) -> TestClient:
    restart(db)
    return client


def restart(db: Engine) -> None:
    """Serve plans from a new store on the same database, as after an app restart."""
    store = PlanStore(make_engine(str(db.url)))
    app.dependency_overrides[get_plan_store] = lambda: store


def _ledger():  # type: ignore[no-untyped-def]
    return app.dependency_overrides[plans.get_plan_ledger]()


def _create(api: TestClient, day: str = DAY):  # type: ignore[no-untyped-def]
    return api.post("/plans", json={"day": day}, headers=auth("officer"))


def test_plan_routes_need_an_officer(api: TestClient) -> None:
    assert api.post("/plans", json={"day": DAY}).status_code == 401
    assert api.get("/plans").status_code == 401
    for role in ("resident", "driver", "field_worker"):
        assert api.post("/plans", json={"day": DAY}, headers=auth(role)).status_code == 403
        assert api.get("/plans", headers=auth(role)).status_code == 403


def test_create_answers_201_with_the_plan_view(api: TestClient) -> None:
    created = _create(api)
    assert created.status_code == 201, created.text
    body = created.json()
    conforms(body, example("plan.get")["response"])
    assert body["plan_id"] == PLAN_ID and body["day"] == DAY and body["status"] == "DRAFT"
    assert body["basis"]["plan"].startswith("SIMULATION")
    assert body["flags"] and body["flags_total"] == len(body["flags"])
    for flag in body["flags"].values():
        assert flag["basis"].startswith("DERIVED; min of available signals")
    assert api.get(f"/plans/{PLAN_ID}", headers=auth("officer")).json() == body
    events = [e for e in _ledger().entries if e.event_type == "plan_created"]
    assert [e.payload["entity_id"] for e in events][-1] == PLAN_ID
    assert events[-1].payload["digest"] == body["digest"]


def test_create_again_returns_the_stored_plan_without_a_second_ledger_entry(
    api: TestClient, db: Engine
) -> None:
    first = _create(api).json()
    restart(db)
    again = _create(api)
    assert again.status_code == 200
    assert again.json() == first
    created = [
        e for e in _ledger().entries
        if e.event_type == "plan_created" and e.payload["entity_id"] == PLAN_ID
    ]  # fmt: skip
    assert len(created) == 1


def test_create_refuses_bad_and_unknown_days(api: TestClient) -> None:
    for body in ({"day": "2025-13-01"}, {"day": "soon"}, {}):
        bad = api.post("/plans", json=body, headers=auth("officer"))
        assert bad.status_code == 422 and bad.json()["error"]["code"] == "validation_error"
    for day in ("2025-02-28", "2026-10-04"):
        unknown = _create(api, day)
        assert unknown.status_code == 404 and unknown.json()["error"]["code"] == "not_found"
        assert "2025-03-01 to 2025-07-31" in unknown.json()["error"]["message"]


def test_list_pages_the_stored_plans(api: TestClient, db: Engine) -> None:
    _create(api, "2025-03-02")
    _create(api)
    restart(db)
    listed = api.get("/plans", headers=auth("officer"))
    assert listed.status_code == 200, listed.text
    body = listed.json()
    assert body["total"] == 2 and body["offset"] == 0
    assert [i["plan_id"] for i in body["items"]] == [PLAN_ID, "replay-2025-03-02"]
    item = body["items"][0]
    assert set(item) == {
        "plan_id", "day", "status", "basis", "flags_total", "checked_total", "created_at",
        "weights",
        "source",
    }  # fmt: skip
    assert item["status"] == "DRAFT" and item["checked_total"] == 0 and item["flags_total"] > 0
    page = api.get("/plans", params={"offset": 1, "limit": 1}, headers=auth("officer")).json()
    assert page["total"] == 2 and [i["plan_id"] for i in page["items"]] == ["replay-2025-03-02"]
    too_big = api.get("/plans", params={"limit": 10_000}, headers=auth("officer"))
    assert too_big.status_code == 422


def test_confidence_comes_from_the_t9_gate(api: TestClient) -> None:
    plan = _create(api).json()
    conf = api.get(f"/plans/{PLAN_ID}/confidence", headers=auth("officer")).json()
    assert conf["threshold_basis"] == CONFIDENCE_CONFIG.threshold_basis
    assert {g["group"] for g in conf["groups"] if g["needs_check"]} == set(plan["flags"])


def test_approval_stays_blocked_after_a_restart_until_every_flag_is_checked(
    api: TestClient, db: Engine
) -> None:
    officer = auth("officer")
    flags = sorted(_create(api).json()["flags"])
    first, rest = flags[0], flags[1:]
    checked = api.post(
        f"/plans/{PLAN_ID}/groups/{first}/check",
        json={"officer_id": "officer-7", "reason": "Checked the section list"},
        headers=officer,
    )
    assert checked.status_code == 200, checked.text
    conforms(checked.json(), example("plan_check.post")["response"])

    restart(db)
    view = api.get(f"/plans/{PLAN_ID}", headers=officer).json()
    assert view["checked"] == {first: "Checked the section list"}
    decision = {"officer_id": "officer-7", "reason": "Plan reviewed"}
    blocked = api.post(f"/plans/{PLAN_ID}/approve", json=decision, headers=officer)
    assert blocked.status_code == 409
    conforms(blocked.json(), example("plan_approve.post")["response"]["body"])

    for group in rest:
        api.post(
            f"/plans/{PLAN_ID}/groups/{group}/check",
            json={"officer_id": "officer-7", "reason": "ok"},
            headers=officer,
        )
    restart(db)
    approved = api.post(f"/plans/{PLAN_ID}/approve", json=decision, headers=officer)
    assert approved.status_code == 200, approved.text

    restart(db)
    final = api.get(f"/plans/{PLAN_ID}", headers=officer).json()
    assert final["status"] == "APPROVED" and final["approved_by"] == "officer-7"
    assert final["approval_reason"] == "Plan reviewed" and set(final["checked"]) == set(flags)
    again = api.post(f"/plans/{PLAN_ID}/approve", json=decision, headers=officer)
    assert again.status_code == 409
    listed = api.get("/plans", headers=officer).json()["items"][0]
    assert listed["status"] == "APPROVED" and listed["checked_total"] == len(flags)


def test_a_plan_that_no_longer_rebuilds_is_a_conflict(api: TestClient, db: Engine) -> None:
    _create(api)
    with Session(db) as session, session.begin():
        session.execute(update(StoredPlan).values(digest="0" * 64))
    restart(db)
    response = api.get(f"/plans/{PLAN_ID}", headers=auth("officer"))
    assert response.status_code == 409
    assert "digest" in response.json()["error"]["message"]
