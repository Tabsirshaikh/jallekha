"""Stored ledger (F18, T6): tamper-evident, not blockchain.

Every allocation-affecting change is written with `record(entry_type, payload, actor)`. The
hash, signature and event types are the S3 ledger's (`services/ledger.py`); this module stores
the entries in the database, keeps the sequence unique under concurrent writers, verifies the
stored chain and publishes a daily head hash.

What it catches, and what it does not:
- An edited, deleted or reordered stored entry breaks the hash chain or the sequence.
- Entries are signed with an HMAC key; `key_id` (inside the hashed payload) names the key, so
  entries signed before a key rotation still verify when the retired key is configured.
- Whoever holds the key could rebuild a whole valid chain, or drop the newest entries. The
  head hash published each day (and sent outside the system) catches both from that day on
  (Crosby & Wallach 2009, docs/research/P3.md F18). Entries after the last publication are
  only as safe as the database until the next head is published.
"""

from __future__ import annotations

import hmac
import json
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import create_engine, select
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.pool import StaticPool

from app.config.trust import TRUST_CONFIG
from app.db import make_engine, make_session_factory
from app.models import Base, LedgerEntryRecord, LedgerHead
from app.models.base import utcnow
from app.services import ledger

RESERVED_PAYLOAD_KEYS = ("actor", "key_id")


@dataclass(frozen=True)
class ChainCheck:
    """Result of verifying the stored chain. `reason` names the first problem found."""

    valid: bool
    checked: int
    broken_at: int | None = None  # sequence number where the chain first fails
    # gap | reorder | hash_mismatch | hmac_mismatch | unknown_key | key_id_mismatch |
    # truncated | head_mismatch
    reason: str | None = None
    head_seq: int | None = None
    head_hash: str | None = None
    detail: str | None = None


@dataclass(frozen=True)
class PublishedHead:
    day: str  # local day (config offset), YYYY-MM-DD
    seq: int
    head_hash: str
    key_id: str
    published_at: datetime


def memory_engine() -> Engine:
    """An in-memory SQLite database shared by every session (tests and demo)."""
    return create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )


def _utc(value: datetime) -> datetime:
    # SQLite returns naive datetimes; every stored time is UTC.
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _aware(now: datetime) -> datetime:
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("Use a timezone-aware UTC datetime")
    return now.astimezone(UTC)


def _to_entry(row: LedgerEntryRecord) -> ledger.LedgerEntry:
    try:
        payload = json.loads(row.payload_json)
    except ValueError:
        payload = {"unreadable_payload": row.payload_json}  # never matches the stored hash
    return ledger.LedgerEntry(
        seq=row.seq,
        event_type=row.event_type,
        entity_type=row.entity_type,
        entity_id=row.entity_id,
        payload=payload,
        prev_hash=row.prev_hash,
        hash=row.hash,
        signature=row.signature,
        created_at_iso=row.created_at_iso,
    )


def _to_head(row: LedgerHead) -> PublishedHead:
    return PublishedHead(row.day, row.seq, row.head_hash, row.key_id, _utc(row.created_at))


def _broken(position: int, seq: int, reason: str, detail: str | None = None) -> ChainCheck:
    return ChainCheck(False, position, broken_at=seq, reason=reason, detail=detail)


def verify_chain(
    entries: Sequence[ledger.LedgerEntry],
    keyring: Mapping[str, str] | None = None,
    heads: Iterable[PublishedHead] = (),
) -> ChainCheck:
    """Check order, links, hashes, signatures (by key_id) and published heads; report the
    first broken entry. Entries are taken in the order given (stored ledger: by seq)."""
    keys = TRUST_CONFIG.ledger_keyring() if keyring is None else keyring
    seqs = {entry.seq for entry in entries}
    hashes = {entry.hash for entry in entries}
    prev_hash = ledger.GENESIS
    for position, entry in enumerate(entries, start=1):
        if entry.seq != position:
            reason = "reorder" if position in seqs else "gap"
            return _broken(position, position, reason, f"expected seq {position}, got {entry.seq}")
        if entry.prev_hash != prev_hash:
            reason = "reorder" if entry.prev_hash in hashes else "hash_mismatch"
            return _broken(position, entry.seq, reason, "prev_hash does not match the entry before")
        try:
            expected = ledger.entry_hash(entry)
        except (TypeError, ValueError):  # a payload that is not valid JSON
            expected = None
        if entry.hash != expected:
            return _broken(position, entry.seq, "hash_mismatch", "stored hash does not match")
        key_id = entry.payload.get("key_id")
        key = keys.get(key_id) if isinstance(key_id, str) else None
        if not key:
            return _broken(position, entry.seq, "unknown_key", f"no key for key_id {key_id!r}")
        if not hmac.compare_digest(entry.signature, ledger.sign(entry.hash, key)):
            return _broken(position, entry.seq, "hmac_mismatch", "signature does not match")
        prev_hash = entry.hash
    by_seq = {entry.seq: entry for entry in entries}
    last_seq = len(entries)
    for head in sorted(heads, key=lambda h: h.seq):
        if head.seq > last_seq:
            return _broken(
                last_seq,
                last_seq + 1,
                "truncated",
                f"head published on {head.day} has seq {head.seq}; chain ends at {last_seq}",
            )
        if by_seq[head.seq].hash != head.head_hash:
            return _broken(
                last_seq, head.seq, "head_mismatch", f"differs from the head published {head.day}"
            )
    last = entries[-1] if entries else None
    return ChainCheck(
        True,
        last_seq,
        head_seq=last.seq if last else None,
        head_hash=last.hash if last else None,
    )


class StoredLedger:
    """The ledger in the database. Implements T3's `LedgerPort` (`append`)."""

    def __init__(
        self,
        engine: Engine,
        keyring: Mapping[str, str] | None = None,
        key_id: str | None = None,
        clock: Callable[[], datetime] = utcnow,
    ) -> None:
        self.engine = engine
        self._keyring = dict(TRUST_CONFIG.ledger_keyring() if keyring is None else keyring)
        self._key_id = key_id or TRUST_CONFIG.ledger_key_id
        self._clock = clock
        self._sessions = make_session_factory(engine)
        Base.metadata.create_all(engine, tables=[LedgerEntryRecord.__table__, LedgerHead.__table__])

    # --- writing ---------------------------------------------------------------------------

    def record(self, entry_type: str, payload: Mapping[str, Any], actor: str) -> ledger.LedgerEntry:
        """Append one entry in its own transaction; retry if another writer took the seq."""
        key = self._keyring.get(self._key_id)
        if not key:
            raise ValueError("Ledger HMAC key is not set (LEDGER_HMAC_KEY); refusing to write")
        if entry_type not in ledger.EVENT_TYPES:
            raise ValueError(f"Unknown ledger event type: {entry_type}")
        reserved = [name for name in RESERVED_PAYLOAD_KEYS if name in payload]
        if reserved:
            raise ValueError(f"Payload keys {reserved} are reserved for the ledger")
        entity_type, entity_id = payload.get("entity_type"), payload.get("entity_id")
        if not entity_type or not entity_id:
            raise ValueError("Ledger payload needs entity_type and entity_id")
        body = {**payload, "actor": actor, "key_id": self._key_id}
        last_error: Exception | None = None
        for _ in range(TRUST_CONFIG.ledger_append_retries):
            try:
                with self._sessions() as session, session.begin():
                    last_row = session.scalars(
                        select(LedgerEntryRecord).order_by(LedgerEntryRecord.seq.desc()).limit(1)
                    ).first()
                    now = _aware(self._clock())
                    entry = ledger.next_entry(
                        _to_entry(last_row) if last_row else None,
                        entry_type,
                        str(entity_type),
                        entity_id,
                        body,
                        now.isoformat(),
                        key,
                    )
                    session.add(
                        LedgerEntryRecord(
                            created_at=now,
                            seq=entry.seq,
                            event_type=entry.event_type,
                            entity_type=entry.entity_type,
                            entity_id=entry.entity_id,
                            payload_json=ledger.payload_json(entry.payload),
                            prev_hash=entry.prev_hash,
                            hash=entry.hash,
                            signature=entry.signature,
                            created_at_iso=entry.created_at_iso,
                            key_id=self._key_id,
                        )
                    )
                return entry
            except IntegrityError as exc:  # another writer used this seq first
                last_error = exc
            except OperationalError as exc:  # SQLite: database briefly locked by a writer
                if "locked" not in str(exc).lower():
                    raise
                last_error = exc
        raise RuntimeError("Could not append to the ledger after retries") from last_error

    def append(self, entry_type: str, payload: Mapping[str, Any], actor: str) -> ledger.LedgerEntry:
        return self.record(entry_type, payload, actor)

    def publish_head(self, now: datetime | None = None) -> PublishedHead:
        """Publish today's head (once per local day; never changed afterwards)."""
        now = _aware(now or self._clock())
        offset = timedelta(minutes=TRUST_CONFIG.ledger_head_utc_offset_minutes)
        day = (now + offset).date().isoformat()
        for _ in range(TRUST_CONFIG.ledger_append_retries):
            try:
                with self._sessions() as session, session.begin():
                    existing = session.scalars(select(LedgerHead).filter_by(day=day)).first()
                    if existing is not None:
                        return _to_head(existing)
                    last = session.scalars(
                        select(LedgerEntryRecord).order_by(LedgerEntryRecord.seq.desc()).limit(1)
                    ).first()
                    if last is None:
                        raise ValueError("The ledger is empty; nothing to publish")
                    row = LedgerHead(
                        created_at=now,
                        day=day,
                        seq=last.seq,
                        head_hash=last.hash,
                        key_id=last.key_id,
                    )
                    session.add(row)
                    session.flush()
                    return _to_head(row)
            except IntegrityError:  # another process published this day first
                continue
        raise RuntimeError("Could not publish the ledger head after retries")

    # --- reading ---------------------------------------------------------------------------

    def _rows(self, after_seq: int = 0, limit: int | None = None) -> list[LedgerEntryRecord]:
        with self._sessions() as session:
            query = (
                select(LedgerEntryRecord)
                .where(LedgerEntryRecord.seq > after_seq)
                .order_by(LedgerEntryRecord.seq)
            )
            if limit is not None:
                query = query.limit(limit)
            return list(session.scalars(query))

    @property
    def entries(self) -> tuple[ledger.LedgerEntry, ...]:
        return tuple(_to_entry(row) for row in self._rows())

    def page(self, after_seq: int = 0, limit: int = 100) -> list[tuple[ledger.LedgerEntry, str]]:
        """Entries after `after_seq`, in order, with the stored key id (read-only list)."""
        return [(_to_entry(row), row.key_id) for row in self._rows(after_seq, limit)]

    def heads(self) -> list[PublishedHead]:
        with self._sessions() as session:
            return [
                _to_head(row)
                for row in session.scalars(select(LedgerHead).order_by(LedgerHead.day))
            ]

    def verify(self, heads: Iterable[PublishedHead] | None = None) -> ChainCheck:
        """Verify the stored chain against the keyring and the published heads."""
        rows = self._rows()
        entries = [_to_entry(row) for row in rows]
        check = verify_chain(entries, self._keyring, self.heads() if heads is None else heads)
        for position, (row, entry) in enumerate(zip(rows, entries, strict=True), start=1):
            if row.key_id != entry.payload.get("key_id"):
                if check.valid or (check.broken_at is not None and row.seq < check.broken_at):
                    return _broken(
                        position, row.seq, "key_id_mismatch", "key_id column differs from payload"
                    )
                break
        return check


_default: StoredLedger | None = None


def get_ledger() -> StoredLedger:
    """The application's ledger (DATABASE_URL, keys from the environment)."""
    global _default
    if _default is None:
        _default = StoredLedger(make_engine())
    return _default


def record(entry_type: str, payload: Mapping[str, Any], actor: str) -> ledger.LedgerEntry:
    """The single call every module uses to write to the ledger (F18)."""
    return get_ledger().record(entry_type, payload, actor)
