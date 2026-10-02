"""Thin ledger interface for features that log events (T3 now; T5, T7 later).

Features depend on `LedgerPort`, not on storage, so T6 can swap the in-memory chain for the
database-backed, concurrency-safe one without touching them. The hash, signature and event
types come from the S3 ledger (`services/ledger.py`).

Payload convention: every payload carries `entity_type` and `entity_id`; they fill the entry's
fields and also stay in the payload. `actor` is added to the payload. Ids and numbers only,
no personal data (no phone numbers, no OTP codes).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime
from typing import Any, Protocol

from app.config.trust import TRUST_CONFIG
from app.models.base import utcnow
from app.services import ledger


class LedgerPort(Protocol):
    def append(
        self, entry_type: str, payload: Mapping[str, Any], actor: str
    ) -> ledger.LedgerEntry: ...


class InMemoryLedger:
    """LedgerPort backed by the S3 hash chain; entries live in memory (T6 adds storage)."""

    def __init__(self, key: str | None = None, clock: Callable[[], datetime] = utcnow) -> None:
        self._key = key if key is not None else TRUST_CONFIG.ledger_hmac_key
        self._clock = clock
        self._entries: list[ledger.LedgerEntry] = []

    @property
    def entries(self) -> tuple[ledger.LedgerEntry, ...]:
        return tuple(self._entries)

    def append(self, entry_type: str, payload: Mapping[str, Any], actor: str) -> ledger.LedgerEntry:
        entity_type, entity_id = payload.get("entity_type"), payload.get("entity_id")
        if not entity_type or not entity_id:
            raise ValueError("Ledger payload needs entity_type and entity_id")
        entry = ledger.next_entry(
            self._entries[-1] if self._entries else None,
            entry_type,
            str(entity_type),
            entity_id,
            {**payload, "actor": actor},
            self._clock().isoformat(),
            self._key,
        )
        self._entries.append(entry)
        return entry
