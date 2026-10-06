"""Persist field observations and count independent, decisive section outcomes only."""

import hashlib
from datetime import UTC, date, datetime

import pytest

from app.db import create_all, make_engine
from app.services.ledger_store import StoredLedger
from app.services.section_outcomes import SectionOutcomeStore


def store(tmp_path, count=32):
    engine = make_engine(f"sqlite:///{(tmp_path / 'checks.db').as_posix()}")
    create_all(engine)
    ledger = StoredLedger(engine, keyring={"k1": "test-key"}, key_id="k1")
    candidates = {
        f"1:S{i}": {"field_check_candidate": True, "period_year": 2025} for i in range(count)
    }
    return SectionOutcomeStore(
        engine, ledger, lambda: candidates, clock=lambda: datetime(2026, 10, 6, tzinfo=UTC)
    ), ledger


def test_saved_note_is_only_a_digest_on_ledger_and_idempotent(tmp_path):
    service, ledger = store(tmp_path)
    result = service.record(
        "1:S0", "yes", date(2026, 10, 5), "People could not book", "worker-1", "same-check"
    )
    assert result["ledger_missing"] is False
    assert result["note"] == "People could not book"
    entries = ledger.entries
    assert len(entries) == 1
    assert entries[0].event_type == "section_check_recorded"
    assert "People could not book" not in str(entries[0].payload)
    assert entries[0].payload["note_sha256"] == hashlib.sha256(b"People could not book").hexdigest()
    assert (
        service.record(
            "1:S0", "yes", date(2026, 10, 5), "People could not book", "worker-1", "same-check"
        )
        == result
    )
    assert len(ledger.entries) == 1
    with pytest.raises(ValueError):
        service.record("1:S0", "no", date(2026, 10, 5), "changed", "worker-1", "same-check")


def test_precision_requires_30_distinct_decisive_flags_and_uses_latest_visit(tmp_path):
    service, _ = store(tmp_path)
    for i in range(29):
        service.record(
            f"1:S{i}", "yes" if i < 20 else "no", date(2026, 10, 4), "", "worker", f"first-{i}"
        )
    assert service.summary()["precision"] is None
    service.record("1:S29", "unclear", date(2026, 10, 4), "", "worker", "unclear")
    assert service.summary()["precision"] is None
    service.record("1:S0", "no", date(2026, 10, 5), "", "worker", "repeat")
    assert service.summary()["decisive_sections"] == 29
    service.record("1:S29", "yes", date(2026, 10, 5), "", "worker", "decisive")
    summary = service.summary()
    assert summary["decisive_sections"] == 30
    assert summary["precision"] == pytest.approx(20 / 30)
    assert summary["unclear_sections"] == 0


def test_only_known_flags_and_no_future_dates(tmp_path):
    service, _ = store(tmp_path)
    with pytest.raises(ValueError):
        service.record("not-flagged", "yes", date(2026, 10, 5), "", "worker", "x")
    with pytest.raises(ValueError):
        service.record("1:S0", "yes", date(2026, 10, 7), "", "worker", "future")


def test_pending_ledger_observation_is_durable_excluded_and_retried(tmp_path):
    service, chain = store(tmp_path)

    class FailingLedger:
        entries = ()

        def record(self, *args):
            raise RuntimeError("ledger unavailable")

    service.ledger = FailingLedger()
    pending = service.record("1:S0", "yes", date(2026, 10, 5), "note", "worker", "pending")
    assert pending["ledger_missing"] is True
    assert len(service.list()) == 1
    assert service.summary()["decisive_sections"] == 0
    assert service.summary()["pending_ledger"] == 1
    service.ledger = chain
    linked = service.record("1:S0", "yes", date(2026, 10, 5), "note", "worker", "pending")
    assert linked["ledger_missing"] is False
    assert service.summary()["decisive_sections"] == 1
    assert len(chain.entries) == 1
