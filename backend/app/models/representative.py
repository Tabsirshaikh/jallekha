from __future__ import annotations

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, IdTimestampMixin


class Representative(IdTimestampMixin, Base):
    """A registered representative who receives the delivery OTP for a stop (F12: 2-3 per stop).

    The phone number is personal data: it is used to send the SMS and never written to the
    ledger.
    """

    __tablename__ = "representative"

    stop_id: Mapped[str] = mapped_column(String(64), index=True)
    phone: Mapped[str] = mapped_column(String(32))
    language: Mapped[str] = mapped_column(String(8))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    # REAL (registered) or SYNTHETIC (demo, labelled on screen).
    basis: Mapped[str] = mapped_column(String(16))
