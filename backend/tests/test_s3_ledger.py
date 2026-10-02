"""S3: hash-chained ledger ported from v1 (pure core; database wiring is T6)."""

from __future__ import annotations

from dataclasses import replace

import pytest

from app.services import ledger

KEY = "test-ledger-key"


def chain(n: int, key: str = KEY) -> list[ledger.LedgerEntry]:
    entries: list[ledger.LedgerEntry] = []
    for i in range(n):
        entries.append(
            ledger.next_entry(
                entries[-1] if entries else None,
                "override",
                "plan",
                f"p{i}",
                {"i": i, "reason": "test entry", "score": i / 3},
                f"2026-10-02T06:{i // 60:02d}:{i % 60:02d}+00:00",
                key,
            )
        )
    return entries


def test_chain_of_100_entries_verifies() -> None:
    entries = chain(100)
    result = ledger.verify_entries(entries, KEY)
    assert result == {"valid": True, "broken_at": None, "checked": 100, "head": entries[-1].hash}
    assert entries[0].prev_hash == ledger.GENESIS
    assert [e.seq for e in entries] == list(range(1, 101))


def test_edited_payload_is_detected_at_that_entry() -> None:
    entries = chain(100)
    entries[59] = replace(entries[59], payload={"i": -1})
    result = ledger.verify_entries(entries, KEY)
    assert not result["valid"]
    assert result["broken_at"] == 60
    assert result["reason"] == "hash_mismatch"


def test_removed_entry_is_detected() -> None:
    entries = chain(10)
    del entries[4]
    result = ledger.verify_entries(entries, KEY)
    assert not result["valid"] and result["broken_at"] == 6


def test_wrong_key_fails_signature_check() -> None:
    result = ledger.verify_entries(chain(3), "another-key")
    assert result == {"valid": False, "broken_at": 1, "reason": "signature_mismatch", "checked": 1}


def test_ledger_refuses_to_write_without_a_key() -> None:
    with pytest.raises(ValueError, match="key"):
        ledger.next_entry(None, "override", "plan", "p1", {}, "2026-10-02T06:00:00+00:00", None)


def test_unknown_event_type_is_rejected() -> None:
    with pytest.raises(ValueError, match="event type"):
        ledger.next_entry(None, "made_up", "plan", "p1", {}, "2026-10-02T06:00:00+00:00", KEY)


def test_payload_is_canonical_so_it_rehashes_identically() -> None:
    entry = chain(1)[0]
    assert ledger.payload_json({"b": 1, "a": 2}) == '{"a":2,"b":1}'
    assert entry.hash == ledger.compute_hash(
        ledger.GENESIS, entry.event_type, entry.entity_id, entry.payload, entry.created_at_iso
    )
