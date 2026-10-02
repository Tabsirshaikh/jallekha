from __future__ import annotations

from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, IdTimestampMixin


class LedgerEntryRecord(IdTimestampMixin, Base):
    """One stored entry of the tamper-evident ledger (F18, T6). Append-only.

    Every `services.ledger.LedgerEntry` field is stored so the hash can be recomputed:
    `payload_json` is the canonical payload and `created_at_iso` the exact timestamp text that
    was hashed. `key_id` is also inside the payload (so it is hashed); the column is for lookup.
    `created_at` (UTC) is the insert time. Ids and numbers only, no personal data.
    """

    __tablename__ = "ledger_entry"

    seq: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    event_type: Mapped[str] = mapped_column(String(48), index=True)
    entity_type: Mapped[str] = mapped_column(String(48))
    entity_id: Mapped[str] = mapped_column(String(64), index=True)
    payload_json: Mapped[str] = mapped_column(Text)
    prev_hash: Mapped[str] = mapped_column(String(64))
    hash: Mapped[str] = mapped_column(String(64))
    signature: Mapped[str] = mapped_column(String(64))
    created_at_iso: Mapped[str] = mapped_column(String(40))
    key_id: Mapped[str] = mapped_column(String(32))
