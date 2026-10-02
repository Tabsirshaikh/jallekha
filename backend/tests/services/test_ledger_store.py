"""T6 stored ledger (F18): database rows, record(), verify_chain(), key_id and daily head hash."""

from __future__ import annotations

import importlib.util
import sys
import threading
from collections.abc import Iterator
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import delete, inspect, update
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.config.trust import TRUST_CONFIG
from app.db import make_engine
from app.models import LedgerEntryRecord, LedgerHead
from app.services import ledger, ledger_store
from app.services.ledger_port import InMemoryLedger, LedgerPort
from app.services.ledger_store import StoredLedger, verify_chain

KEY = "test-ledger-key-1"
OLD_KEY = "test-ledger-key-0"
T0 = datetime(2026, 10, 2, 6, 0, tzinfo=UTC)


class Clock:
    def __init__(self) -> None:
        self.now = T0

    def __call__(self) -> datetime:
        self.now += timedelta(seconds=1)
        return self.now


@pytest.fixture
def engine(tmp_path: Path) -> Iterator[Engine]:
    eng = make_engine(f"sqlite:///{(tmp_path / 'ledger.db').as_posix()}")
    yield eng
    eng.dispose()


@pytest.fixture
def store(engine: Engine) -> StoredLedger:
    return StoredLedger(engine, keyring={"k1": KEY}, key_id="k1", clock=Clock())


def _fill(store: StoredLedger, n: int) -> None:
    for i in range(n):
        store.record("override", {"entity_type": "plan", "entity_id": f"p{i}", "i": i}, "officer-1")


def _change_row(engine: Engine, at_seq: int, **values: object) -> None:
    with Session(engine) as session, session.begin():
        row = LedgerEntryRecord.seq == at_seq
        session.execute(update(LedgerEntryRecord).where(row).values(**values))


# --- storage and record() ----------------------------------------------------------------


def test_tables_one_per_model_with_unique_sequence(engine: Engine, store: StoredLedger) -> None:
    assert {"ledger_entry", "ledger_head"} <= set(inspect(engine).get_table_names())
    seq_unique = any(
        constraint["column_names"] == ["seq"]
        for constraint in inspect(engine).get_unique_constraints("ledger_entry")
    ) or any(
        index["unique"] and index["column_names"] == ["seq"]
        for index in inspect(engine).get_indexes("ledger_entry")
    )
    assert seq_unique


def test_record_stores_every_field_and_the_chain_verifies(
    engine: Engine, store: StoredLedger
) -> None:
    _fill(store, 5)
    entries = store.entries
    assert [e.seq for e in entries] == [1, 2, 3, 4, 5]
    assert entries[0].prev_hash == ledger.GENESIS
    assert all(e.payload["actor"] == "officer-1" and e.payload["key_id"] == "k1" for e in entries)
    with Session(engine) as session:
        row = session.query(LedgerEntryRecord).filter_by(seq=3).one()
        assert (row.entity_type, row.entity_id, row.key_id) == ("plan", "p2", "k1")
        assert row.created_at.tzinfo is not None or row.created_at_iso.endswith("+00:00")
        assert len(row.id) == 36
    check = store.verify()
    assert (check.valid, check.checked, check.broken_at, check.reason) == (True, 5, None, None)
    assert check.head_seq == 5 and check.head_hash == entries[-1].hash
    # The stored entries are ordinary S3 entries: P2's verifier agrees.
    assert ledger.verify_entries(list(entries), KEY)["valid"]


def test_record_refuses_to_run_without_a_key(engine: Engine) -> None:
    keyless = StoredLedger(engine, keyring={}, key_id="k1", clock=Clock())
    with pytest.raises(ValueError, match="LEDGER_HMAC_KEY"):
        keyless.record("override", {"entity_type": "plan", "entity_id": "p1"}, "officer-1")
    assert keyless.entries == ()


def test_record_rejects_unknown_events_missing_entity_and_reserved_keys(
    store: StoredLedger,
) -> None:
    with pytest.raises(ValueError, match="Unknown ledger event type"):
        store.record("made_up", {"entity_type": "plan", "entity_id": "p1"}, "officer-1")
    with pytest.raises(ValueError, match="entity"):
        store.record("override", {"entity_id": "p1"}, "officer-1")
    for reserved in ("actor", "key_id"):
        with pytest.raises(ValueError, match="reserved"):
            store.record("override", {"entity_type": "plan", "entity_id": "p1", reserved: "x"}, "o")
    assert store.entries == ()


def test_module_level_record_uses_the_default_ledger(
    monkeypatch: pytest.MonkeyPatch, store: StoredLedger
) -> None:
    monkeypatch.setattr(ledger_store, "_default", store)
    entry = ledger_store.record("weights_changed", {"entity_type": "config", "entity_id": "w"}, "o")
    assert entry.seq == 1 and ledger_store.get_ledger() is store


# --- tamper detection ----------------------------------------------------------------------


def test_edited_payload_in_the_database_fails_at_that_entry(
    engine: Engine, store: StoredLedger
) -> None:
    _fill(store, 5)
    _change_row(engine, 3, payload_json='{"entity_id":"p2","entity_type":"plan","i":99}')
    check = store.verify()
    assert (check.valid, check.broken_at, check.reason) == (False, 3, "hash_mismatch")


STORED_FIELDS = {
    "seq": 30,
    "event_type": "weights_changed",
    "entity_type": "ward",
    "entity_id": "p999",
    "payload_json": '{"tampered":true}',
    "prev_hash": "0" * 64,
    "hash": "f" * 64,
    "signature": "e" * 64,
    "created_at_iso": "2026-10-02T07:00:00+00:00",
    "key_id": "k9",
}


@pytest.mark.parametrize(("column", "value"), list(STORED_FIELDS.items()))
def test_changing_any_stored_field_is_detected(
    engine: Engine, store: StoredLedger, column: str, value: object
) -> None:
    _fill(store, 5)
    _change_row(engine, 3, **{column: value})
    check = store.verify()
    assert not check.valid and check.broken_at == 3
    assert check.reason in {"hash_mismatch", "hmac_mismatch", "gap", "key_id_mismatch"}


def test_every_ledger_entry_field_has_a_column() -> None:
    columns = set(LedgerEntryRecord.__table__.columns.keys())
    for name in ("seq", "event_type", "entity_type", "entity_id", "prev_hash", "hash"):
        assert name in columns
    assert {"payload_json", "signature", "created_at_iso", "key_id"} <= columns


def test_deleted_entry_is_a_gap(engine: Engine, store: StoredLedger) -> None:
    _fill(store, 5)
    with Session(engine) as session, session.begin():
        session.execute(delete(LedgerEntryRecord).where(LedgerEntryRecord.seq == 3))
    check = store.verify()
    assert (check.valid, check.broken_at, check.reason) == (False, 3, "gap")


def test_reordered_entries_fail(engine: Engine, store: StoredLedger) -> None:
    _fill(store, 5)
    _change_row(engine, 3, seq=-3)
    _change_row(engine, 4, seq=3)
    _change_row(engine, -3, seq=4)
    check = store.verify()
    assert (check.valid, check.broken_at, check.reason) == (False, 3, "reorder")
    # The same for a list handed to verify_chain out of order.
    entries = list(store.entries)
    swapped = [entries[0], entries[2], entries[1], *entries[3:]]
    assert verify_chain(swapped, {"k1": KEY}).reason == "reorder"


def test_wrong_hmac_key_fails(store: StoredLedger) -> None:
    _fill(store, 3)
    check = verify_chain(list(store.entries), {"k1": "not-the-key"})
    assert (check.valid, check.broken_at, check.reason) == (False, 1, "hmac_mismatch")


def test_verify_without_the_entry_key_reports_unknown_key(store: StoredLedger) -> None:
    _fill(store, 2)
    check = verify_chain(list(store.entries), {})
    assert (check.valid, check.broken_at, check.reason) == (False, 1, "unknown_key")


# --- concurrency ---------------------------------------------------------------------------


def test_concurrent_appends_keep_a_valid_chain(engine: Engine) -> None:
    writers = [StoredLedger(engine, keyring={"k1": KEY}, key_id="k1") for _ in range(2)]
    errors: list[BaseException] = []

    def run(writer: StoredLedger, name: str) -> None:
        try:
            for i in range(20):
                writer.record("override", {"entity_type": "plan", "entity_id": f"{name}{i}"}, name)
        except BaseException as exc:  # noqa: BLE001 - reported below
            errors.append(exc)

    threads = [threading.Thread(target=run, args=(w, f"w{n}")) for n, w in enumerate(writers)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert errors == []
    entries = writers[0].entries
    assert [e.seq for e in entries] == list(range(1, 41))
    assert writers[0].verify().valid


# --- published head hash (S3 review D2) ----------------------------------------------------


def test_removing_the_last_entry_is_caught_by_the_published_head(
    engine: Engine, store: StoredLedger
) -> None:
    _fill(store, 10)
    head = store.publish_head(T0 + timedelta(hours=12))
    assert (head.seq, head.head_hash) == (10, store.entries[-1].hash)
    with Session(engine) as session, session.begin():
        session.execute(delete(LedgerEntryRecord).where(LedgerEntryRecord.seq == 10))
    assert verify_chain(list(store.entries), {"k1": KEY}).valid  # the chain alone cannot tell
    check = store.verify()
    assert (check.valid, check.broken_at, check.reason) == (False, 10, "truncated")


def test_rewritten_history_is_caught_by_the_published_head(tmp_path: Path) -> None:
    first = StoredLedger(
        make_engine(f"sqlite:///{(tmp_path / 'a.db').as_posix()}"), {"k1": KEY}, "k1", Clock()
    )
    _fill(first, 5)
    head = first.publish_head(T0 + timedelta(hours=12))
    # The key holder rebuilds a fully valid chain with different content.
    rewritten = StoredLedger(
        make_engine(f"sqlite:///{(tmp_path / 'b.db').as_posix()}"), {"k1": KEY}, "k1", Clock()
    )
    for i in range(5):
        rewritten.record("override", {"entity_type": "plan", "entity_id": f"x{i}"}, "officer-1")
    assert rewritten.verify().valid
    check = verify_chain(list(rewritten.entries), {"k1": KEY}, heads=[head])
    assert (check.valid, check.broken_at, check.reason) == (False, 5, "head_mismatch")


def test_one_head_per_day_in_the_configured_offset(store: StoredLedger) -> None:
    _fill(store, 2)
    noon = T0 + timedelta(hours=6)
    first = store.publish_head(noon)
    _fill(store, 1)
    again = store.publish_head(noon + timedelta(hours=1))
    assert again == first  # already published that day: not changed afterwards
    offset = timedelta(minutes=TRUST_CONFIG.ledger_head_utc_offset_minutes)
    assert first.day == (noon + offset).date().isoformat()
    next_day = store.publish_head(noon + timedelta(days=1))
    assert next_day.seq == 3 and len(store.heads()) == 2


def test_head_rows_are_stored(engine: Engine, store: StoredLedger) -> None:
    _fill(store, 1)
    store.publish_head(T0 + timedelta(hours=12))
    with Session(engine) as session:
        assert session.query(LedgerHead).count() == 1


# --- key_id and rotation ---------------------------------------------------------------------


def test_entries_signed_with_an_older_key_still_verify_when_it_is_configured(
    engine: Engine,
) -> None:
    clock = Clock()
    old = StoredLedger(engine, keyring={"k0": OLD_KEY}, key_id="k0", clock=clock)
    _fill(old, 3)
    rotated = StoredLedger(engine, keyring={"k1": KEY, "k0": OLD_KEY}, key_id="k1", clock=clock)
    rotated.record("weights_changed", {"entity_type": "config", "entity_id": "w"}, "officer-1")
    assert [e.payload["key_id"] for e in rotated.entries] == ["k0", "k0", "k0", "k1"]
    assert rotated.verify().valid
    without_old = StoredLedger(engine, keyring={"k1": KEY}, key_id="k1", clock=clock)
    check = without_old.verify()
    assert (check.valid, check.broken_at, check.reason) == (False, 1, "unknown_key")


def test_keyring_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LEDGER_HMAC_KEY", "current")
    monkeypatch.setenv("LEDGER_KEY_ID", "k2")
    monkeypatch.setenv("LEDGER_OLD_HMAC_KEYS", "k0:zero, k1:one")
    config = type(TRUST_CONFIG)()
    assert config.ledger_keyring() == {"k2": "current", "k0": "zero", "k1": "one"}
    assert "current" not in repr(config) and "zero" not in repr(config)
    monkeypatch.setenv("LEDGER_OLD_HMAC_KEYS", "broken")
    with pytest.raises(ValueError, match="LEDGER_OLD_HMAC_KEYS"):
        type(TRUST_CONFIG)().ledger_keyring()


# --- T3's port now runs on the stored ledger -------------------------------------------------


def test_t3_ledger_port_is_the_stored_ledger() -> None:
    port: LedgerPort = InMemoryLedger(key=KEY)
    assert isinstance(port, StoredLedger)
    entry = port.append("delivery_started", {"entity_type": "delivery", "entity_id": "d1"}, "drv")
    assert port.entries == (entry,)
    assert port.verify().valid


def test_entries_round_trip_exactly(store: StoredLedger) -> None:
    store.record(
        "override",
        {"entity_type": "plan", "entity_id": "p1", "score": 1 / 3, "names": ["a", "ā"]},
        "officer-1",
    )
    entry = store.entries[0]
    assert ledger.entry_hash(entry) == entry.hash
    assert replace(entry) == entry


# --- daily publish script ------------------------------------------------------------------


def _publish_script():  # type: ignore[no-untyped-def]
    path = Path(__file__).resolve().parents[3] / "scripts/trust/publish_ledger_head.py"
    spec = importlib.util.spec_from_file_location("publish_ledger_head", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_publish_script_exit_codes(
    engine: Engine, store: StoredLedger, capsys: pytest.CaptureFixture[str]
) -> None:
    script = _publish_script()
    assert script.main(store) == 2  # empty
    _fill(store, 3)
    assert script.main(store) == 0
    assert "seq 3 hash" in capsys.readouterr().out
    assert len(store.heads()) == 1
    _change_row(engine, 2, entity_id="x")
    assert script.main(store) == 1  # does not publish over a broken chain
