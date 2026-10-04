"""POST /plans with the bookings of a day supplied by an officer (API)."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from conftest import auth
from fastapi.testclient import TestClient
from sqlalchemy.engine import Engine

from app.config.plans import PLAN_STORE_CONFIG
from app.db import create_all, make_engine
from app.main import app
from app.routers import plans
from app.routers.stores import PlanStore, get_plan_store
from app.services import plan_builder

DAY = "2026-10-03"  # outside the replay window: that is the point
WEIGHTS = {"wad": 5, "cad": 0, "hardship": 0}


@pytest.fixture
def db(tmp_path: Path) -> Iterator[Engine]:
    engine = make_engine(f"sqlite:///{(tmp_path / 'supplied.db').as_posix()}")
    create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def api(client: TestClient, db: Engine) -> TestClient:
    _restart(db)
    return client


def _restart(db: Engine) -> None:
    store = PlanStore(make_engine(str(db.url)))
    app.dependency_overrides[get_plan_store] = lambda: store


def _ledger():  # type: ignore[no-untyped-def]
    return app.dependency_overrides[plans.get_plan_ledger]()


def _bookings(count: int = 30) -> list[dict[str, Any]]:
    setup = plan_builder._setup()
    sections = [s for s in sorted(setup.ctx.network.home) if s in setup.ctx.mapping][:3]
    return [
        {
            "booking_id": f"B-{i:04d}",
            "section": sections[i % 3],
            "arrived_at": f"2026-10-03T03:{i % 60:02d}:00+05:30",
        }
        for i in range(count)
    ]


def _post(api: TestClient, body: dict[str, Any]) -> Any:
    return api.post("/plans", json=body, headers=auth("officer"))


def test_a_plan_is_built_from_supplied_bookings_outside_the_replay_window(api: TestClient) -> None:
    response = _post(api, {"day": DAY, "bookings": _bookings(30)})
    assert response.status_code == 201, response.text
    view = response.json()
    assert view["plan_id"].startswith("plan-2026-10-03-")
    assert view["day"] == DAY and view["source"] == "supplied_bookings"
    assert view["bookings_supplied"] == 30
    assert "supplied" in view["basis"]["plan"].lower()
    served = sum(s["served_total"] for s in view["stations"].values())
    waiting = sum(s["waiting_total"] for s in view["stations"].values())
    assert served + waiting == 30


def test_the_same_bookings_again_return_the_stored_plan(api: TestClient) -> None:
    rows = _bookings(20)
    first = _post(api, {"day": DAY, "bookings": rows})
    entries = len(_ledger().entries)
    again = _post(api, {"day": DAY, "bookings": list(reversed(rows))})  # order does not matter
    assert (first.status_code, again.status_code) == (201, 200)
    assert again.json() == first.json() and len(_ledger().entries) == entries


def test_the_ledger_entry_says_the_plan_came_from_supplied_bookings(api: TestClient) -> None:
    before = len(_ledger().entries)
    _post(api, {"day": DAY, "bookings": _bookings(12), "weights": WEIGHTS})
    created = _ledger().entries[before:]
    assert len(created) == 1 and created[0].event_type == "plan_created"
    assert created[0].payload["source"] == "supplied_bookings"
    assert created[0].payload["bookings"] == 12 and created[0].payload["weights"] == WEIGHTS


def test_unusable_bookings_are_refused_with_the_reasons_and_nothing_is_stored(
    api: TestClient,
) -> None:
    rows = _bookings(6)
    rows[0]["category"] = "industrial"
    rows[1]["section"] = "NO SUCH SECTION"
    before = len(_ledger().entries)
    response = _post(api, {"day": DAY, "bookings": rows})
    assert response.status_code == 422
    message = response.json()["error"]["message"]
    assert "booking 1" in message and "category" in message and "booking 2" in message
    assert api.get("/plans", headers=auth("officer")).json()["total"] == 0
    assert len(_ledger().entries) == before


def test_too_many_bookings_are_refused(api: TestClient) -> None:
    rows = _bookings(3)
    many = [
        {**rows[i % 3], "booking_id": f"B-{i}"}
        for i in range(PLAN_STORE_CONFIG.max_supplied_bookings + 1)
    ]
    response = _post(api, {"day": DAY, "bookings": many})
    assert response.status_code == 422 and "at most" in response.json()["error"]["message"]


def test_an_empty_list_is_not_a_plan(api: TestClient) -> None:
    assert _post(api, {"day": DAY, "bookings": []}).status_code == 422


def test_without_bookings_a_day_must_still_be_in_the_replay_window(api: TestClient) -> None:
    assert _post(api, {"day": DAY}).status_code == 404


def test_supplied_bookings_can_be_planned_with_other_weights_and_compared(api: TestClient) -> None:
    rows = _bookings(60)
    default = _post(api, {"day": DAY, "bookings": rows}).json()
    weighted = _post(api, {"day": DAY, "bookings": rows, "weights": WEIGHTS})
    assert weighted.status_code == 201
    view = weighted.json()
    assert view["plan_id"] == f"{default['plan_id']}-w5-0-0"
    assert view["weights"]["is_default"] is False and view["bookings_supplied"] == 60
    compare = api.get(f"/plans/{view['plan_id']}/compare", headers=auth("officer"))
    assert compare.status_code == 200
    assert compare.json()["against"] == default["plan_id"]


def test_a_supplied_plan_survives_a_restart_with_the_same_view(api: TestClient, db: Engine) -> None:
    view = _post(api, {"day": DAY, "bookings": _bookings(24)}).json()
    _restart(db)
    again = api.get(f"/plans/{view['plan_id']}", headers=auth("officer"))
    assert again.status_code == 200 and again.json() == view


def test_replay_plans_say_so_and_the_list_names_the_source(api: TestClient) -> None:
    replay = _post(api, {"day": "2025-05-01"}).json()
    assert replay["source"] == "planner_replay" and replay["bookings_supplied"] is None
    _post(api, {"day": DAY, "bookings": _bookings(10)})
    items = {
        p["plan_id"]: p["source"]
        for p in api.get("/plans", headers=auth("officer")).json()["items"]
    }
    assert sorted(items.values()) == ["planner_replay", "supplied_bookings"]


def test_only_an_officer_may_supply_bookings(api: TestClient) -> None:
    body = {"day": DAY, "bookings": _bookings(3)}
    assert api.post("/plans", json=body).status_code == 401
    for role in ("resident", "driver", "field_worker"):
        assert api.post("/plans", json=body, headers=auth(role)).status_code == 403
