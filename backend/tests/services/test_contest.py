"""T7 contest (F16): file, officer reply with a required reason, both in the stored ledger."""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import inspect, select, update
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.config.explain import EXPLAIN_CONFIG
from app.db import create_all, make_engine
from app.models import Contest, ContestReply
from app.services import contest as ct
from app.services.ledger_store import StoredLedger

LEDGER_KEY = "test-ledger-key"
T0 = datetime(2026, 10, 2, 9, 0, tzinfo=UTC)


@pytest.fixture
def engine(tmp_path: Path) -> Iterator[Engine]:
    eng = make_engine(f"sqlite:///{(tmp_path / 'contest.db').as_posix()}")
    create_all(eng)
    yield eng
    eng.dispose()


@pytest.fixture
def store(engine: Engine) -> StoredLedger:
    return StoredLedger(engine, keyring={"k1": LEDGER_KEY}, key_id="k1")


@pytest.fixture
def service(engine: Engine, store: StoredLedger) -> ct.ContestService:
    return ct.ContestService(engine, ledger=store, clock=lambda: T0)


def _contest(**overrides: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "filed_by": "resident-42",
        "role": "resident",
        "target_type": "ward",
        "target_id": "relation/7848799",
        "reason_code": "ranking_wrong",
        "reason_text": "Our ward got no tanker for a week while the next ward got three.",
    }
    data.update(overrides)
    return data


def _reply(**overrides: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "officer_id": "officer-7",
        "outcome_code": "ranking_stands",
        "reason_text": "Need weight checked against Census 2011; the order follows the fair queue.",
    }
    data.update(overrides)
    return data


def _rows(engine: Engine, model: type) -> list[Any]:
    with Session(engine) as session:
        return list(session.scalars(select(model)))


# --- done-when ---------------------------------------------------------------------------


@pytest.mark.parametrize("bad", ["", "   ", "\n\t ", None])
def test_a_reply_without_a_reason_is_rejected_and_nothing_is_stored_or_logged(
    service: ct.ContestService, engine: Engine, store: StoredLedger, bad: str | None
) -> None:
    filed = service.file(_contest())
    before = len(store.entries)
    result = service.reply(filed.contest_id, _reply(reason_text=bad))
    assert result.status == "invalid" and "reason" in (result.error or "")
    assert _rows(engine, ContestReply) == []
    assert _rows(engine, Contest)[0].status == "open"
    assert len(store.entries) == before


def test_a_contest_and_its_reply_are_both_in_the_stored_ledger_and_the_chain_verifies(
    service: ct.ContestService, store: StoredLedger
) -> None:
    filed = service.file(_contest())
    replied = service.reply(filed.contest_id, _reply())
    assert (filed.status, replied.status) == ("filed", "replied")
    entries = store.entries
    assert [e.event_type for e in entries] == ["contest_filed", "contest_replied"]
    assert all(e.entity_type == "contest" and e.entity_id == filed.contest_id for e in entries)
    assert entries[1].payload["reply_id"] == replied.reply_id
    assert [filed.ledger_seq, replied.ledger_seq] == [1, 2]
    assert store.verify().valid


# --- contest rules -----------------------------------------------------------------------


def test_contest_rows_hold_who_role_target_reason_status_and_times(
    service: ct.ContestService, engine: Engine
) -> None:
    filed = service.file(
        _contest(
            role="councillor",
            filed_by="councillor-3",
            target_type="booking",
            target_id="2025-05-15:ADIKMET:00012",
        )
    )
    row = _rows(engine, Contest)[0]
    assert (row.id, row.filed_by, row.role, row.target_type, row.target_id) == (
        filed.contest_id,
        "councillor-3",
        "councillor",
        "booking",
        "2025-05-15:ADIKMET:00012",
    )
    assert (row.reason_code, row.status) == ("ranking_wrong", "open")
    assert row.created_at is not None
    service.reply(filed.contest_id, _reply())
    row = _rows(engine, Contest)[0]
    reply = _rows(engine, ContestReply)[0]
    assert row.status == "replied" and reply.contest_id == filed.contest_id
    assert (reply.officer_id, reply.outcome_code) == ("officer-7", "ranking_stands")


def test_one_reply_per_contest(
    service: ct.ContestService, engine: Engine, store: StoredLedger
) -> None:
    filed = service.file(_contest())
    service.reply(filed.contest_id, _reply())
    again = service.reply(filed.contest_id, _reply(reason_text="second answer"))
    assert again.status == "already_replied"
    assert len(_rows(engine, ContestReply)) == 1 and len(store.entries) == 2


@pytest.mark.parametrize(
    "bad",
    [
        {"role": "officer"},
        {"target_type": "station"},
        {"reason_code": "made_up"},
        {"filed_by": ""},
        {"filed_by": "+919800000001"},
        {"target_id": ""},
        {"reason_text": "x" * (EXPLAIN_CONFIG.max_reason_chars + 1)},
    ],
)
def test_bad_contests_are_rejected(
    service: ct.ContestService, engine: Engine, bad: dict[str, Any]
) -> None:
    assert service.file(_contest(**bad)).status == "invalid"
    assert _rows(engine, Contest) == []


@pytest.mark.parametrize(
    "bad",
    [
        {"officer_id": ""},
        {"officer_id": "   "},
        {"officer_id": "+919800000001"},
        {"outcome_code": "maybe"},
        {"reason_text": "y" * (EXPLAIN_CONFIG.max_reason_chars + 1)},
    ],
)
def test_bad_replies_are_rejected(
    service: ct.ContestService, engine: Engine, bad: dict[str, Any]
) -> None:
    filed = service.file(_contest())
    assert service.reply(filed.contest_id, _reply(**bad)).status == "invalid"
    assert _rows(engine, ContestReply) == []


def test_reply_to_an_unknown_contest(service: ct.ContestService) -> None:
    assert service.reply("no-such-contest", _reply()).status == "not_found"


def test_tables_one_per_model(engine: Engine) -> None:
    assert {"contest", "contest_reply"} <= set(inspect(engine).get_table_names())


# --- privacy and the text hash -----------------------------------------------------------


def test_no_free_text_or_phone_in_any_ledger_payload(
    service: ct.ContestService, store: StoredLedger, engine: Engine
) -> None:
    filed = service.file(_contest(reason_text="Call me on 9800000001, Ramesh, about the tanker."))
    service.reply(filed.contest_id, _reply(reason_text="Spoke to Ramesh; the order stands."))
    text = json.dumps([e.payload for e in store.entries], ensure_ascii=False)
    for secret in ("9800000001", "Ramesh", "tanker", "order stands"):
        assert secret not in text
    for entry in store.entries:
        assert set(entry.payload) <= ct.LEDGER_PAYLOAD_KEYS | {"actor", "key_id"}
        assert len(entry.payload["reason_sha256"]) == 64
    stored = _rows(engine, Contest)[0].reason_text
    assert "9800000001" not in stored and "[number removed]" in stored


def test_the_hash_check_detects_edited_text(service: ct.ContestService, engine: Engine) -> None:
    filed = service.file(_contest())
    service.reply(filed.contest_id, _reply())
    assert service.verify_text(filed.contest_id) == {"contest": "match", "reply": "match"}
    with Session(engine) as session, session.begin():
        session.execute(
            update(Contest).where(Contest.id == filed.contest_id).values(reason_text="edited later")
        )
    assert service.verify_text(filed.contest_id) == {"contest": "edited", "reply": "match"}
    with Session(engine) as session, session.begin():
        session.execute(update(ContestReply).values(reason_text="also edited"))
    assert service.verify_text(filed.contest_id)["reply"] == "edited"


def test_a_ledger_failure_keeps_the_rows_and_marks_them(engine: Engine) -> None:
    failing = ct.ContestService(
        engine, ledger=StoredLedger(engine, keyring={}, key_id="k1"), clock=lambda: T0
    )
    filed = failing.file(_contest())
    replied = failing.reply(filed.contest_id, _reply())
    assert (filed.status, replied.status) == ("filed", "replied")
    assert (filed.ledger_seq, replied.ledger_seq) == (None, None)
    assert failing.ids_missing_ledger() == {
        "contest": [filed.contest_id],
        "reply": [replied.reply_id],
    }
    assert failing.verify_text(filed.contest_id) == {
        "contest": "no_ledger_entry",
        "reply": "no_ledger_entry",
    }
