from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, IdTimestampMixin


class IntakeItemRecord(IdTimestampMixin, Base):
    """Every report received (F14, T4), including spam and duplicates of a client id.

    `created_at` is the server's receive time (UTC); `client_created_at` is the phone's time for
    offline items. `client_id` is the offline idempotency key. The phone is stored only as an
    HMAC hash (for the spam burst count), never as a number. Spam is kept and marked.
    """

    __tablename__ = "intake_item"

    client_id: Mapped[str | None] = mapped_column(String(64), unique=True)
    client_created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    channel: Mapped[str] = mapped_column(String(16))
    # created | merged | spam (invalid items are reported to the client, not stored)
    status: Mapped[str] = mapped_column(String(16))
    complaint_id: Mapped[str | None] = mapped_column(ForeignKey("complaint.id"), index=True)
    phone_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    reporter_id: Mapped[str | None] = mapped_column(String(64))
    language: Mapped[str | None] = mapped_column(String(8))
    spam_score: Mapped[float | None] = mapped_column(Float)
    spam_reasons: Mapped[str | None] = mapped_column(Text)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=False)
