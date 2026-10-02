from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, IdTimestampMixin


class ResidentResponse(IdTimestampMixin, Base):
    """A sampled resident asked "Did you get water? 1 yes / 2 no" (F12).

    One row per sampled resident; `created_at` is when they were asked. `answer` stays empty
    for silence, which counts for nothing.
    """

    __tablename__ = "resident_response"
    __table_args__ = (UniqueConstraint("delivery_id", "resident_id"),)

    delivery_id: Mapped[str] = mapped_column(ForeignKey("delivery.id"), index=True)
    resident_id: Mapped[str] = mapped_column(String(64))
    answer: Mapped[str | None] = mapped_column(String(8))  # yes | no | None (silent)
    replied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
