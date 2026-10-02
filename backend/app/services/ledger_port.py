"""Thin ledger interface for features that log events (T3 now; T5, T7 later).

Features depend on `LedgerPort`, not on storage. The implementation is T6's stored ledger
(`services/ledger_store.py`): `StoredLedger` for the application database, and
`InMemoryLedger`, the same stored ledger on a private in-memory SQLite database, for tests and
the demo. The hash, signature and event types come from the S3 ledger (`services/ledger.py`).

Payload convention: every payload carries `entity_type` and `entity_id`; they fill the entry's
fields and also stay in the payload. `actor` and `key_id` are added to the payload (callers may
not set them). Ids and numbers only, no personal data (no phone numbers, no OTP codes).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime
from typing import Any, Protocol

from app.config.trust import TRUST_CONFIG
from app.models.base import utcnow
from app.services import ledger
from app.services.ledger_store import StoredLedger, memory_engine


class LedgerPort(Protocol):
    def append(
        self, entry_type: str, payload: Mapping[str, Any], actor: str
    ) -> ledger.LedgerEntry: ...


class InMemoryLedger(StoredLedger):
    """The stored ledger on a private in-memory SQLite database (tests, demo)."""

    def __init__(self, key: str | None = None, clock: Callable[[], datetime] = utcnow) -> None:
        key = key if key is not None else TRUST_CONFIG.ledger_hmac_key
        key_id = TRUST_CONFIG.ledger_key_id
        super().__init__(memory_engine(), {key_id: key} if key else {}, key_id, clock)
