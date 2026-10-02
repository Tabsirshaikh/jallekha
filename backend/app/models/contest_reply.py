from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, IdTimestampMixin


class ContestReply(IdTimestampMixin, Base):
    """The officer's reply to a contest (F16, T7). One reply per contest; the reason is required.

    The text stays here; the ledger (contest_replied) gets ids, the outcome code and the
    SHA-256 of the text. `created_at` (UTC) is the reply time.
    """

    __tablename__ = "contest_reply"

    contest_id: Mapped[str] = mapped_column(ForeignKey("contest.id"), unique=True)
    officer_id: Mapped[str] = mapped_column(String(64))
    outcome_code: Mapped[str] = mapped_column(String(32))
    reason_text: Mapped[str] = mapped_column(Text)
    reason_sha256: Mapped[str] = mapped_column(String(64))
    text_chars: Mapped[int] = mapped_column(Integer)
    ledger_missing: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
