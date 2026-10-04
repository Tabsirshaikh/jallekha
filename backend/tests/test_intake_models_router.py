"""T4 intake tables and the thin intake endpoints (batch, SMS webhook, missed call)."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import get_api_config
from app.config.api import ApiConfig
from app.db import create_all, make_engine
from app.main import app
from app.models import Complaint, IntakeItemRecord
from app.routers.intake import get_intake_service
from app.services import intake_pipeline as ip
from app.services.sms import FakeSmsSender

HEADERS = {"Authorization": "Bearer test-token", "X-Gateway-Token": "test-gateway"}


@pytest.fixture
def service(tmp_path: Path) -> Iterator[ip.IntakeService]:
    engine = make_engine(f"sqlite:///{(tmp_path / 'intake.db').as_posix()}")
    create_all(engine)
    svc = ip.IntakeService(
        engine,
        sms=FakeSmsSender(),
        transcriber=ip.FallbackTranscriber(),
        audio_store=ip.LocalAudioStore(tmp_path / "audio"),
        phone_hash_key="test-phone-key",
    )
    app.dependency_overrides[get_intake_service] = lambda: svc
    app.dependency_overrides[get_api_config] = lambda: ApiConfig(
        tokens={"test-token": "resident"}, gateway_token="test-gateway"
    )
    yield svc
    app.dependency_overrides.clear()
    engine.dispose()


def test_intake_tables_and_unique_client_id(service: ip.IntakeService) -> None:
    tables = set(inspect(service.engine).get_table_names())
    assert {"complaint", "intake_item", "voice_note"} <= tables
    with Session(service.engine) as session:
        session.add(IntakeItemRecord(client_id="c-1", channel="app", status="created"))
        session.commit()
        session.add(IntakeItemRecord(client_id="c-1", channel="app", status="created"))
        with pytest.raises(IntegrityError):
            session.commit()


def test_complaint_location_is_optional() -> None:
    assert Complaint.__table__.c.lat.nullable and Complaint.__table__.c.lon.nullable


def test_batch_endpoint_returns_a_status_per_item(service: ip.IntakeService) -> None:
    client = TestClient(app, headers=HEADERS)
    body = client.post(
        "/intake/batch",
        json={
            "items": [
                {
                    "channel": "app",
                    "client_id": "a",
                    "text": "no water",
                    "lat": 17.385,
                    "lon": 78.4867,
                },
                {"channel": "fax", "client_id": "b", "text": "no water"},
            ]
        },
    ).json()
    assert [(r["client_id"], r["status"]) for r in body["results"]] == [
        ("a", "created"),
        ("b", "invalid"),
    ]


def test_sms_and_missed_call_webhooks(service: ip.IntakeService) -> None:
    client = TestClient(app, headers=HEADERS)
    sms = client.post("/intake/sms", json={"From": "+919800000001", "Body": "no water"}).json()
    call = client.post("/intake/missed-call", json={"caller": "+919800000002"}).json()
    assert (sms["status"], call["status"], call["complaint_status"]) == (
        "created",
        "created",
        "awaiting_location",
    )
    assert "phone" not in sms and "9800000001" not in str(sms)


def test_batch_size_is_limited(service: ip.IntakeService) -> None:
    client = TestClient(app, headers=HEADERS)
    items = [{"channel": "app", "text": "no water"}] * (ip.INTAKE_CONFIG.max_batch_items + 1)
    assert client.post("/intake/batch", json={"items": items}).status_code == 422
