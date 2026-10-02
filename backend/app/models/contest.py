from __future__ import annotations

from sqlalchemy import Boolean, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, IdTimestampMixin


class Contest(IdTimestampMixin, Base):
    """A resident's or councillor's contest of a ward or booking ranking (F16, T7).

    The reason text stays here; the ledger (contest_filed) gets ids, codes and the SHA-256 of
    the text, so a later edit can be detected. Long digit runs (phone numbers) are removed from
    the text before it is stored. `created_at` (UTC) is the filing time.
    """

    __tablename__ = "contest"

    filed_by: Mapped[str] = mapped_column(String(64), index=True)  # an id, never a phone number
    role: Mapped[str] = mapped_column(String(16))  # resident | councillor
    target_type: Mapped[str] = mapped_column(String(16))  # ward | booking
    target_id: Mapped[str] = mapped_column(String(80), index=True)
    reason_code: Mapped[str] = mapped_column(String(32))
    reason_text: Mapped[str] = mapped_column(Text)
    reason_sha256: Mapped[str] = mapped_column(String(64))
    text_chars: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(16), default="open")  # open | replied
    # True while the ledger entry is expected but not written (logged again later).
    ledger_missing: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
