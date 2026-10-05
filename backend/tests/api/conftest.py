"""Fixtures for the T10 API tests: tokens from the environment, temporary databases, a small
A7 plan in the in-memory plan store and a T3 stop in the database. All data here is SYNTHETIC."""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.auth import get_api_config
from app.config.api import ApiConfig
from app.db import create_all, make_engine
from app.main import app
from app.routers import contests, deliveries, evidence, intake, ledger, notices, plans
from app.routers.stores import (
    DeliveryStore,
    PlanRecord,
    PlanStore,
    Stop,
    get_debt_store,
    get_delivery_store,
    get_plan_store,
)
from app.services import delivery as dl
from app.services import fair_queue, planner
from app.services import intake_pipeline as ip
from app.services import notices as nt
from app.services.contest import ContestService
from app.services.debt_store import DebtStore
from app.services.ledger_store import StoredLedger
from app.services.sms import FakeSmsSender

ROOT = Path(__file__).resolve().parents[3]
EXAMPLES = ROOT / "docs/api_examples"
TOKENS = {
    "officer": "t-officer",
    "driver": "t-driver",
    "resident": "t-resident",
    "field_worker": "t-field",
}
GATEWAY = "t-gateway"
OTP_KEY = "test-otp-key"
NOW = datetime(2026, 10, 3, 5, 0, tzinfo=UTC)
STOP = (17.4400, 78.4983)


def auth(role: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {TOKENS[role]}"}


GATEWAY_HEADERS = {"X-Gateway-Token": GATEWAY}


def example(name: str) -> dict[str, Any]:
    return json.loads((EXAMPLES / f"{name}.json").read_text(encoding="utf-8"))


def _pending(group: str, n: int, start: int) -> list[planner.PlannerBooking]:
    first = NOW - timedelta(hours=10)
    return [
        planner.PlannerBooking(
            fair_queue.QueueBooking(
                booking_id=f"B-{group}-{start + i:03d}",
                group=group,
                arrived_at=first + timedelta(minutes=start + i),
                tier=2,
                consumer_id=f"c-{start + i}",
                category="domestic",
            ),
            "S1",
        )
        for i in range(n)
    ]


def make_plan(chain: StoredLedger) -> PlanRecord:
    # One placed ward with Census need and one unplaced section (A3 fallback): the gate flags it.
    inputs = planner.PlanInputs(
        plan_id="plan-test-1",
        day=date(2026, 10, 3),
        capacity={"S1": 6},
        pending=_pending("ward:relation/7848824", 6, 0) + _pending("section:LOST", 6, 100),
        entitlement={"ward:relation/7848824": 1.0, "section:LOST": 1.0},
    )
    gate = planner.ProvisionalGate(frozenset({"section:LOST"}))
    plan = planner.build_plan(inputs, gate, chain, NOW)
    basis = {
        "plan": "SYNTHETIC test plan",
        "effective_entitlement": "SYNTHETIC",
        "flags": "PROVISIONAL",
    }
    return PlanRecord(inputs, plan, basis)


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("API_TOKENS", ",".join(f"{r}:{t}" for r, t in TOKENS.items()))
    monkeypatch.setenv("GATEWAY_TOKEN", GATEWAY)
    monkeypatch.setenv("OTP_HMAC_KEY", OTP_KEY)
    monkeypatch.delenv("API_DEV_TOKEN", raising=False)
    engine = make_engine(f"sqlite:///{(tmp_path / 'api.db').as_posix()}")
    create_all(engine)
    chain = StoredLedger(engine, keyring={"k1": "test-ledger-key"}, key_id="k1")
    intake_service = ip.IntakeService(
        engine,
        sms=FakeSmsSender(),
        transcriber=ip.FallbackTranscriber(),
        audio_store=ip.LocalAudioStore(tmp_path / "audio"),
        phone_hash_key="test-phone-key",
        ledger=chain,
    )
    plan_store = PlanStore()
    plan_store.put(make_plan(chain))
    reps = (
        dl.Representative("rep-01", "stop-0001", "+919800000101", "te"),
        dl.Representative("rep-02", "stop-0001", "+919800000102", "ur"),
    )
    residents = tuple(dl.Resident(f"res-{i:02d}", f"+9198000002{i:02d}", "te") for i in range(1, 6))
    delivery_store = DeliveryStore(engine)
    delivery_store.put_stop(Stop("stop-0001", *STOP, reps, residents, "SYNTHETIC"))
    debt_store = DebtStore(engine)
    overrides = {
        get_api_config: ApiConfig.from_env,
        intake.get_intake_service: lambda: intake_service,
        notices.get_notice_service: lambda: nt.NoticeService(engine, ledger=chain),
        ledger.get_ledger_dependency: lambda: chain,
        plans.get_plan_ledger: lambda: chain,
        deliveries.get_delivery_ledger: lambda: chain,
        deliveries.get_delivery_sms: FakeSmsSender,
        evidence.get_summary_ledger: lambda: chain,
        contests.get_contest_service: lambda: ContestService(engine, ledger=chain),
        get_plan_store: lambda: plan_store,
        get_delivery_store: lambda: delivery_store,
        get_debt_store: lambda: debt_store,  # never the default database
    }
    app.dependency_overrides.update(overrides)
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


# --- shape check against docs/api_examples ------------------------------------------------------


def _kind(value: Any) -> str:
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int | float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return "null"


def _map_like(d: dict[str, Any]) -> bool:
    """A dict keyed by data (ward ids, stations, policies) rather than by field names."""
    if not d:
        return True
    kinds = {_kind(v) for v in d.values()}
    if len(kinds) != 1:
        return False
    values = list(d.values())
    return not isinstance(values[0], dict) or all(set(v) == set(values[0]) for v in values)


# A ledger payload's fields depend on its event type; GeoJSON coordinates nest differently for
# Polygon and MultiPolygon. Only their presence is checked.
OPAQUE = {"payload", "coordinates"}


def conforms(actual: Any, expected: Any, path: str = "$") -> None:
    """`actual` has the shape of the documented example: the same field names (maps keyed by
    data may differ in keys), and the same JSON kinds; null is allowed either side. A list item
    must match one of the example's items (items may differ, e.g. a counterfactual's changes)."""
    if actual is None or expected is None:
        return
    assert _kind(actual) == _kind(expected), f"{path}: {_kind(actual)} != {_kind(expected)}"
    if isinstance(expected, dict):
        if set(actual) == set(expected):
            for key in expected:
                if key not in OPAQUE:
                    conforms(actual[key], expected[key], f"{path}.{key}")
        else:
            assert _map_like(expected) and _map_like(actual), (
                f"{path}: fields differ: {sorted(set(actual) ^ set(expected))}"
            )
            if expected:
                proto = next(iter(expected.values()))
                for key, value in actual.items():
                    conforms(value, proto, f"{path}.{key}")
    elif isinstance(expected, list) and expected:
        for i, item in enumerate(actual):
            errors = []
            for candidate in expected:
                try:
                    conforms(item, candidate, f"{path}[{i}]")
                    break
                except AssertionError as exc:
                    errors.append(str(exc))
            else:
                raise AssertionError(errors[0])
