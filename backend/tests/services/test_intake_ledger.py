"""T4 ledger wiring: intake writes to the stored ledger (T6); payloads hold ids and numbers only."""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.db import create_all, make_engine
from app.models import IntakeItemRecord
from app.services import intake_pipeline as ip
from app.services import ledger, ledger_store
from app.services.ledger_store import StoredLedger
from app.services.sms import FakeSmsSender

PHONE_KEY = "test-phone-key"
LEDGER_KEY = "test-ledger-key"
T0 = datetime(2026, 10, 2, 9, 0, tzinfo=UTC)
HERE = (17.385, 78.4867)
NEARBY = (17.3853, 78.4867)
PHONE = "+919800000001"


class Clock:
    def __init__(self) -> None:
        self.now = T0

    def __call__(self) -> datetime:
        return self.now


@pytest.fixture
def engine(tmp_path: Path) -> Iterator[Engine]:
    eng = make_engine(f"sqlite:///{(tmp_path / 'intake.db').as_posix()}")
    create_all(eng)
    yield eng
    eng.dispose()


@pytest.fixture
def store(engine: Engine) -> StoredLedger:
    return StoredLedger(engine, keyring={"k1": LEDGER_KEY}, key_id="k1")


@pytest.fixture
def clock() -> Clock:
    return Clock()


def _service(engine: Engine, store: Any, clock: Clock, tmp_path: Path) -> ip.IntakeService:
    return ip.IntakeService(
        engine,
        sms=FakeSmsSender(),
        transcriber=ip.FallbackTranscriber(),
        audio_store=ip.LocalAudioStore(tmp_path / "audio"),
        phone_hash_key=PHONE_KEY,
        ledger=store,
        clock=clock,
    )


def _app(text: str, where: tuple[float, float] = HERE, **extra: Any) -> dict[str, Any]:
    return {"channel": "app", "text": text, "lat": where[0], "lon": where[1], **extra}


def test_intake_event_types_exist() -> None:
    assert set(ip.PROPOSED_EVENTS.values()) == {
        "complaint_received",
        "complaint_merged",
        "complaint_marked_spam",
    }
    assert set(ip.PROPOSED_EVENTS.values()) <= ledger.EVENT_TYPES


def test_created_merged_and_spam_items_write_entries_and_the_chain_verifies(
    engine: Engine, store: StoredLedger, clock: Clock, tmp_path: Path
) -> None:
    service = _service(engine, store, clock, tmp_path)
    first = service.receive_json(_app("no water"))
    clock.now += timedelta(hours=2)
    second = service.receive_json(_app("no water here too", NEARBY))
    spam = service.receive_sms({"From": PHONE, "Body": "@!"})
    assert (first.status, second.status, spam.status) == ("created", "merged", "spam")
    entries = store.entries
    assert [e.event_type for e in entries] == [
        "complaint_received",
        "complaint_merged",
        "complaint_marked_spam",
    ]
    assert (entries[0].entity_type, entries[0].entity_id) == ("complaint", first.complaint_id)
    assert entries[1].payload["parent_id"] == first.complaint_id
    assert (entries[2].entity_type, entries[2].entity_id) == ("intake_item", spam.intake_id)
    assert [first.ledger_seq, second.ledger_seq, spam.ledger_seq] == [1, 2, 3]
    assert store.verify().valid


def test_duplicate_and_invalid_items_write_nothing(
    engine: Engine, store: StoredLedger, clock: Clock, tmp_path: Path
) -> None:
    service = _service(engine, store, clock, tmp_path)
    service.receive_json(_app("no water", client_id="c-1"))
    service.receive_json(_app("no water", client_id="c-1"))
    service.receive_json({"channel": "fax", "text": "no water"})
    assert [e.event_type for e in store.entries] == ["complaint_received"]


def test_no_payload_holds_a_phone_number_name_text_or_audio(
    engine: Engine, store: StoredLedger, clock: Clock, tmp_path: Path
) -> None:
    service = _service(engine, store, clock, tmp_path)
    service.receive_sms({"From": PHONE, "Body": "no water at H.No 4-5 Ramesh house"})
    service.receive_missed_call({"caller": "+919800000002"})
    service.receive_json(
        {
            "channel": "field_worker",
            "text": "నీళ్లు రాలేదు",
            "reporter_id": "fw-1",
            "household_id": "hh-7",
        }
    )
    service.receive_voice(b"RIFF-secret-audio", "audio/wav", lat=HERE[0], lon=HERE[1], phone=PHONE)
    service.receive_sms({"From": "+919800000003", "Body": "@!"})
    assert len(store.entries) == 5
    allowed = ip.LEDGER_PAYLOAD_KEYS | set(ledger_store.RESERVED_PAYLOAD_KEYS)
    for entry in store.entries:
        assert set(entry.payload) <= allowed
        text = json.dumps(entry.payload, ensure_ascii=False)
        for secret in (
            "9800000001",
            "9800000002",
            "9800000003",
            "Ramesh",
            "no water",
            "నీళ్లు",
            "RIFF",
            "hh-7",
        ):
            assert secret not in text
        for value in entry.payload.values():
            assert value is None or isinstance(value, bool | int | float) or len(str(value)) <= 64
    assert store.verify().valid


def test_a_ledger_failure_keeps_the_report_and_is_logged(
    engine: Engine, clock: Clock, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    keyless = StoredLedger(engine, keyring={}, key_id="k1")
    service = _service(engine, keyless, clock, tmp_path)
    with caplog.at_level(logging.ERROR, logger="jallekha.intake"):
        result = service.receive_json(_app("no water"))
    assert result.status == "created" and result.complaint_id and result.ledger_seq is None
    assert "ledger" in caplog.text.lower()


def test_default_service_writes_to_the_stored_ledger(
    engine: Engine, store: StoredLedger, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(ledger_store, "_default", store)
    monkeypatch.setattr(ip, "_default", None)
    monkeypatch.setattr(ip, "make_engine", lambda: engine)
    service = ip.default_service()
    service.receive_json(_app("no water"))  # no phone, so no PHONE_HASH_KEY needed
    assert [e.event_type for e in store.entries] == ["complaint_received"]


def test_missing_ledger_entries_are_marked_and_can_be_found(
    engine: Engine, store: StoredLedger, clock: Clock, tmp_path: Path
) -> None:
    keyless = _service(engine, StoredLedger(engine, keyring={}, key_id="k1"), clock, tmp_path)
    lost = keyless.receive_json(_app("no water"))
    lost_spam = keyless.receive_sms({"From": PHONE, "Body": "@!"})
    written = _service(engine, store, clock, tmp_path).receive_json(_app("leak", (17.4, 78.5)))
    with Session(engine) as session:
        flags = {r.id: r.ledger_missing for r in session.scalars(select(IntakeItemRecord))}
    assert flags == {lost.intake_id: True, lost_spam.intake_id: True, written.intake_id: False}
    assert set(keyless.intake_ids_missing_ledger()) == {lost.intake_id, lost_spam.intake_id}


def test_no_marker_when_no_ledger_is_configured(
    engine: Engine, clock: Clock, tmp_path: Path
) -> None:
    service = _service(engine, None, clock, tmp_path)
    service.receive_json(_app("no water"))
    assert service.intake_ids_missing_ledger() == []
