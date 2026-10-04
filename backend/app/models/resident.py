from __future__ import annotations

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, IdTimestampMixin


class Resident(IdTimestampMixin, Base):
    """A resident of a stop who may be sampled for "Did you get water? 1 yes / 2 no" (F12).

    `resident_id` is unique within its stop. The phone number is personal data: it is used to
    send the SMS and to match a reply, and never written to the ledger or sent in a response.
    """

    __tablename__ = "resident"
    __table_args__ = (UniqueConstraint("stop_id", "resident_id"),)

    stop_id: Mapped[str] = mapped_column(ForeignKey("delivery_stop.stop_id"), index=True)
    resident_id: Mapped[str] = mapped_column(String(64))
    phone: Mapped[str] = mapped_column(String(32))
    language: Mapped[str] = mapped_column(String(8))
    # REAL (registered) or SYNTHETIC (demo, labelled on screen).
    basis: Mapped[str] = mapped_column(String(16))
