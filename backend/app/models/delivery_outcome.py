from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, IdTimestampMixin


class DeliveryOutcome(IdTimestampMixin, Base):
    """The F12 outcome of a delivery, decided once (T3). `created_at` is the decision time.

    Only Confirmed counts toward water debt (F11, P2's A6).
    """

    __tablename__ = "delivery_outcome"

    delivery_id: Mapped[str] = mapped_column(ForeignKey("delivery.id"), unique=True)
    outcome: Mapped[str] = mapped_column(String(16), index=True)  # Confirmed | Disputed | ...
    rule: Mapped[str] = mapped_column(String(24))  # majority | no_majority_fallback
    otp_verified: Mapped[bool] = mapped_column(Boolean)
    yes_count: Mapped[int] = mapped_column(Integer)
    no_count: Mapped[int] = mapped_column(Integer)
    silent_count: Mapped[int] = mapped_column(Integer)
    counts_toward_debt: Mapped[bool] = mapped_column(Boolean)
    outcome_basis: Mapped[str] = mapped_column(Text)
