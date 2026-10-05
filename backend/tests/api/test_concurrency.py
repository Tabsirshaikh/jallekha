"""Two people acting at the same moment: no lost updates, no 500 for a duplicate start.

Store level: a write made from a stale read is refused (optimistic version) and the first write
stands. HTTP level: real concurrent requests on one plan and one delivery. All data is SYNTHETIC
except the committed replay plan (SIMULATION).
"""

from __future__ import annotations

from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.engine import Engine

from app.auth import get_api_config
from app.config.api import ApiConfig
from app.db import create_all, make_engine
from app.main import app
from app.routers import deliveries, plans
from app.routers.stores import (
    PlanConflict,
    PlanRecord,
    PlanStore,
    get_delivery_store,
    get_plan_store,
)
from app.services import delivery as dl
from app.services import plan_builder, planner
from app.services.delivery_store import DeliveryConflict, DeliveryStore, Stop
from app.services.ledger_port import InMemoryLedger
from app.services.ledger_store import StoredLedger
from app.services.sms import FakeSmsSender

NOW = datetime(2026, 10, 4, 5, 0, tzinfo=UTC)
STOP = (17.4400, 78.4983)
OFFICER = {"Authorization": "Bearer t-officer"}
DRIVER = {"Authorization": "Bearer t-driver"}


def _people() -> tuple[tuple[dl.Representative, ...], tuple[dl.Resident, ...]]:
    reps = (
        dl.Representative("rep-01", "stop-0001", "+919800000101", "te"),
        dl.Representative("rep-02", "stop-0001", "+919800000102", "ur"),
    )
    residents = tuple(dl.Resident(f"res-{i:02d}", f"+9198000002{i:02d}", "te") for i in range(1, 6))
    return reps, residents


def _delivery(delivery_id: str = "D-1") -> dl.DeliveryState:
    reps, _ = _people()
    return dl.start_delivery(
        delivery_id, "stop-0001", *STOP, "drv-1", reps, InMemoryLedger(key="k"), NOW
    )


@pytest.fixture
def db(tmp_path: Path) -> Iterator[Engine]:
    engine = make_engine(f"sqlite:///{(tmp_path / 'race.db').as_posix()}")
    create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def delivery_store(db: Engine) -> DeliveryStore:
    store = DeliveryStore(db)
    reps, residents = _people()
    store.put_stop(Stop("stop-0001", *STOP, reps, residents, "SYNTHETIC"))
    return store


# --- store level ---------------------------------------------------------------------------


def test_a_stale_plan_save_is_refused_and_the_first_save_stands(db: Engine) -> None:
    built = plan_builder.build_replay_plan(date(2025, 3, 1))
    PlanStore(db).put(PlanRecord(built.inputs, built.plan, built.basis, built.recipe))
    plan_id = built.plan.plan_id
    first, second = PlanStore(db).get(plan_id), PlanStore(db).get(plan_id)  # two officers
    assert first is not None and second is not None
    groups = sorted(first.plan.flags)
    ledger = InMemoryLedger(key="k")
    first.plan = planner.mark_checked(first.plan, groups[0], "off-1", "seen", ledger, NOW)
    PlanStore(db).save(first)
    second.plan = planner.mark_checked(second.plan, groups[1], "off-2", "seen", ledger, NOW)
    with pytest.raises(PlanConflict):
        PlanStore(db).save(second)
    stored = PlanStore(db).get(plan_id)
    assert stored is not None and set(stored.plan.checked) == {groups[0]}
    # after reloading, the second officer's change goes through
    again = PlanStore(db).get(plan_id)
    assert again is not None
    again.plan = planner.mark_checked(again.plan, groups[1], "off-2", "seen", ledger, NOW)
    PlanStore(db).save(again)
    final = PlanStore(db).get(plan_id)
    assert final is not None and set(final.plan.checked) == {groups[0], groups[1]}


def test_a_stale_delivery_write_is_refused_and_the_first_write_stands(
    delivery_store: DeliveryStore,
) -> None:
    delivery_store.put_delivery(_delivery())
    first, second = delivery_store.get_delivery("D-1"), delivery_store.get_delivery("D-1")
    assert first is not None and second is not None
    delivery_store.put_delivery(replace(first, wrong_attempts=1))
    with pytest.raises(DeliveryConflict):
        delivery_store.put_delivery(replace(second, wrong_attempts=1))
    stored = delivery_store.get_delivery("D-1")
    assert stored is not None and stored.wrong_attempts == 1
    # a reloaded state can be written again
    delivery_store.put_delivery(replace(stored, wrong_attempts=2))
    again = delivery_store.get_delivery("D-1")
    assert again is not None and again.wrong_attempts == 2


def test_a_second_start_of_the_same_delivery_conflicts_instead_of_crashing(
    delivery_store: DeliveryStore,
) -> None:
    delivery_store.put_delivery(_delivery())
    with pytest.raises(DeliveryConflict):
        delivery_store.put_delivery(_delivery())  # a new state: version 0, but the row exists


def test_the_version_does_not_make_states_unequal(delivery_store: DeliveryStore) -> None:
    state = _delivery()
    delivery_store.put_delivery(state)
    loaded = delivery_store.get_delivery("D-1")
    assert loaded == state  # the version is bookkeeping, not part of the delivery


# --- HTTP level ----------------------------------------------------------------------------


@pytest.fixture
def live(
    db: Engine, delivery_store: DeliveryStore, monkeypatch: pytest.MonkeyPatch
) -> Iterator[tuple[PlanRecord, StoredLedger]]:
    monkeypatch.setenv("API_TOKENS", "officer:t-officer,driver:t-driver")
    monkeypatch.setenv("OTP_HMAC_KEY", "test-otp-key")
    monkeypatch.delenv("API_DEV_TOKEN", raising=False)
    chain = StoredLedger(db, keyring={"k1": "test-ledger-key"}, key_id="k1")
    plan_store = PlanStore(db)
    built = plan_builder.build_replay_plan(date(2025, 3, 1))
    record = PlanRecord(built.inputs, built.plan, built.basis, built.recipe)
    plan_store.put(record)
    app.dependency_overrides.update(
        {
            get_api_config: ApiConfig.from_env,
            plans.get_plan_ledger: lambda: chain,
            deliveries.get_delivery_ledger: lambda: chain,
            deliveries.get_delivery_sms: FakeSmsSender,
            get_plan_store: lambda: plan_store,
            get_delivery_store: lambda: delivery_store,
        }
    )
    try:
        yield record, chain
    finally:
        app.dependency_overrides.clear()


def test_officers_checking_different_groups_at_once_lose_none(
    live: tuple[PlanRecord, StoredLedger],
) -> None:
    record, chain = live
    plan_id = record.plan.plan_id
    groups = sorted(record.plan.flags)[:8]
    assert len(groups) == 8

    def check(group: str) -> int:
        body = {"officer_id": "off-1", "reason": f"seen {group}"}
        url = f"/plans/{plan_id}/groups/{group}/check"
        return TestClient(app).post(url, json=body, headers=OFFICER).status_code

    with ThreadPoolExecutor(max_workers=8) as pool:
        statuses = list(pool.map(check, groups))
    assert statuses == [200] * 8
    view = TestClient(app).get(f"/plans/{plan_id}", headers=OFFICER).json()
    assert set(view["checked"]) == set(groups)
    assert len(chain.entries) == 8  # one entry per check, none written for a lost one


def test_two_starts_of_one_delivery_give_one_success_and_conflicts_never_a_500(
    live: tuple[PlanRecord, StoredLedger],
) -> None:
    body = {"delivery_id": "D-race", "stop_id": "stop-0001", "driver_id": "drv-1"}

    def start(_: int) -> int:
        return TestClient(app).post("/deliveries", json=body, headers=DRIVER).status_code

    with ThreadPoolExecutor(max_workers=8) as pool:
        statuses = sorted(pool.map(start, range(8)))
    assert statuses == [200] + [409] * 7


def test_simultaneous_wrong_codes_are_all_counted(live: tuple[PlanRecord, StoredLedger]) -> None:
    client = TestClient(app)
    body = {"delivery_id": "D-otp", "stop_id": "stop-0001", "driver_id": "drv-1"}
    assert client.post("/deliveries", json=body, headers=DRIVER).status_code == 200
    sent = client.post(
        "/deliveries/D-otp/otp", json={"representative_id": "rep-01"}, headers=DRIVER
    )
    assert sent.status_code == 200
    attempt = {"code": "000000", "lat": STOP[0], "lon": STOP[1]}

    def verify(_: int) -> str:
        r = TestClient(app).post("/deliveries/D-otp/otp/verify", json=attempt, headers=DRIVER)
        return r.json()["result"] if r.status_code == 200 else str(r.status_code)

    with ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(verify, range(3)))
    shown = TestClient(app).get("/deliveries/D-otp", headers=DRIVER).json()
    assert results.count("wrong_code") == shown["wrong_attempts"], results
    assert shown["wrong_attempts"] == 3, results
