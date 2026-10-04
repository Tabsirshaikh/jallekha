"""Officer-chosen need weights and ward names on plans (API); replay plans (SIMULATION)."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from conftest import auth
from fastapi.testclient import TestClient
from sqlalchemy.engine import Engine

from app.config.allocation import ALLOCATION_CONFIG
from app.db import create_all, make_engine
from app.main import app
from app.routers import plans
from app.routers.stores import PlanStore, get_plan_store

DAY = "2025-05-01"
DEFAULT_ID = f"replay-{DAY}"
WEIGHTED_ID = f"replay-{DAY}-w5-0-0"
WEIGHTS = {"wad": 5.0, "cad": 0.0, "hardship": 0.0}
BARKAS = "ward:relation/7867584"


@pytest.fixture
def db(tmp_path: Path) -> Iterator[Engine]:
    engine = make_engine(f"sqlite:///{(tmp_path / 'weights.db').as_posix()}")
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


def _post(api: TestClient, body: dict[str, Any]) -> Any:
    return api.post("/plans", json=body, headers=auth("officer"))


def test_a_default_plan_shows_the_configured_weights_and_ward_names(api: TestClient) -> None:
    view = _post(api, {"day": DAY}).json()
    cfg = ALLOCATION_CONFIG
    assert view["weights"] == {
        "wad": cfg.need_weight_wad,
        "cad": cfg.need_weight_cad,
        "hardship": cfg.need_weight_hardship,
        "is_default": True,
    }
    assert view["group_names"][BARKAS] == "Ward 42 Barkas"
    assert set(view["group_names"]) == set(view["effective_entitlement"])
    assert "ASSUMED" in view["basis"]["weights"]


def test_a_weighted_plan_is_its_own_plan_beside_the_default(api: TestClient) -> None:
    default = _post(api, {"day": DAY})
    weighted = _post(api, {"day": DAY, "weights": WEIGHTS})
    assert (default.status_code, weighted.status_code) == (201, 201)
    view = weighted.json()
    assert view["plan_id"] == WEIGHTED_ID != DEFAULT_ID
    assert view["weights"] == {**WEIGHTS, "is_default": False}
    assert "chosen by an officer" in view["basis"]["weights"]
    listed = {p["plan_id"] for p in api.get("/plans", headers=auth("officer")).json()["items"]}
    assert {DEFAULT_ID, WEIGHTED_ID} <= listed
    assert view["effective_entitlement"] != default.json()["effective_entitlement"]


def test_the_same_weights_again_return_the_stored_plan(api: TestClient) -> None:
    first = _post(api, {"day": DAY, "weights": WEIGHTS})
    ledger_before = len(_ledger().entries)
    again = _post(api, {"day": DAY, "weights": WEIGHTS})
    assert (first.status_code, again.status_code) == (201, 200)
    assert again.json() == first.json()
    assert len(_ledger().entries) == ledger_before


def test_weights_equal_to_the_defaults_are_the_default_plan(api: TestClient) -> None:
    cfg = ALLOCATION_CONFIG
    same = {
        "wad": cfg.need_weight_wad,
        "cad": cfg.need_weight_cad,
        "hardship": cfg.need_weight_hardship,
    }
    view = _post(api, {"day": DAY, "weights": same}).json()
    assert view["plan_id"] == DEFAULT_ID and view["weights"]["is_default"] is True


@pytest.mark.parametrize(
    "weights",
    [
        {"wad": 9, "cad": 1, "hardship": 1},
        {"wad": -1, "cad": 1, "hardship": 1},
        {"wad": 2, "cad": 1},  # all three are required
        {"wad": "high", "cad": 1, "hardship": 1},
        {"wad": 2, "cad": 1, "hardship": 1, "debt": 3},  # no such slider
    ],
)
def test_unusable_weights_are_refused_and_nothing_is_stored(
    api: TestClient, weights: dict[str, Any]
) -> None:
    before = len(_ledger().entries)
    response = _post(api, {"day": DAY, "weights": weights})
    assert response.status_code == 422
    assert api.get("/plans", headers=auth("officer")).json()["total"] == 0
    assert len(_ledger().entries) == before


def test_the_ledger_entry_for_a_weighted_plan_carries_the_weights(api: TestClient) -> None:
    before = len(_ledger().entries)
    _post(api, {"day": DAY, "weights": WEIGHTS})
    created = _ledger().entries[before:]
    assert len(created) == 1 and created[0].event_type == "plan_created"
    assert created[0].payload["weights"] == WEIGHTS


def test_a_weighted_plan_survives_a_restart_with_the_same_view(api: TestClient, db: Engine) -> None:
    view = _post(api, {"day": DAY, "weights": WEIGHTS}).json()
    _restart(db)
    again = api.get(f"/plans/{WEIGHTED_ID}", headers=auth("officer"))
    assert again.status_code == 200 and again.json() == view


def test_compare_lists_who_gains_and_loses(api: TestClient) -> None:
    _post(api, {"day": DAY, "weights": WEIGHTS})
    response = api.get(f"/plans/{WEIGHTED_ID}/compare", headers=auth("officer"))
    assert response.status_code == 200
    body = response.json()
    assert body["against"] == DEFAULT_ID and body["weights"] == WEIGHTS
    assert body["gainers"] and body["losers"]
    assert sum(r["change"] for r in body["all_changes"]) == 0
    assert all(r["name"] for r in body["gainers"] + body["losers"])
    assert "SIMULATION" in body["basis"]


def test_compare_needs_a_weighted_plan_and_an_officer(api: TestClient) -> None:
    _post(api, {"day": DAY})
    assert api.get(f"/plans/{DEFAULT_ID}/compare", headers=auth("officer")).status_code == 404
    assert (
        api.get("/plans/replay-2025-05-02-w1-1-1/compare", headers=auth("officer")).status_code
        == 404
    )
    assert api.get(f"/plans/{DEFAULT_ID}/compare").status_code == 401
    assert api.get(f"/plans/{DEFAULT_ID}/compare", headers=auth("resident")).status_code == 403


def _ledger():  # type: ignore[no-untyped-def]
    return app.dependency_overrides[plans.get_plan_ledger]()


def test_the_plan_list_says_which_plans_are_weighted(api: TestClient) -> None:
    _post(api, {"day": DAY})
    _post(api, {"day": DAY, "weights": WEIGHTS})
    items = {p["plan_id"]: p for p in api.get("/plans", headers=auth("officer")).json()["items"]}
    assert items[DEFAULT_ID]["weights"] is None
    assert items[WEIGHTED_ID]["weights"] == WEIGHTS


def test_the_plan_list_reports_the_default_weights_and_the_largest_allowed(api: TestClient) -> None:
    body = api.get("/plans", headers=auth("officer")).json()
    cfg = ALLOCATION_CONFIG
    assert body["default_weights"] == {
        "wad": cfg.need_weight_wad,
        "cad": cfg.need_weight_cad,
        "hardship": cfg.need_weight_hardship,
    }
    assert body["max_weight"] == cfg.need_weight_max
