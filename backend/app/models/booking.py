from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, IdTimestampMixin


class Booking(IdTimestampMixin, Base):
    """A tanker booking made through JalLekha (resident app or field worker).

    The section comes from the booking's location (the approximate section areas), never from
    what the resident typed. The phone number is personal data: it receives the delivery code and
    the "did you get water?" message and is never written to the ledger or returned in full.
    `status` is WAITING, ASSIGNED (an approved plan gave it a tanker) or CANCELLED; what happened
    at the door is read from its delivery (F12).
    """

    __tablename__ = "booking"

    booking_id: Mapped[str] = mapped_column(String(40), unique=True)
    arrived_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    lat: Mapped[float] = mapped_column(Float)
    lon: Mapped[float] = mapped_column(Float)
    section: Mapped[str] = mapped_column(String(160), index=True)  # the plan group, "section:NAME"
    ward_id: Mapped[str | None] = mapped_column(String(64))
    category: Mapped[str] = mapped_column(String(16))
    water_at_home: Mapped[str] = mapped_column(String(8))  # yes | no | unknown
    facility_name: Mapped[str | None] = mapped_column(String(120))
    # NONE (a home), CLAIMED (hospital/care home/school, not yet checked), VERIFIED or REJECTED.
    claim_status: Mapped[str] = mapped_column(String(12))
    claim_checked_by: Mapped[str | None] = mapped_column(String(64))
    phone: Mapped[str] = mapped_column(String(32))
    consumer_key: Mapped[str] = mapped_column(String(32), index=True)  # hash of the phone number
    language: Mapped[str] = mapped_column(String(8))
    channel: Mapped[str] = mapped_column(String(16))  # app | field_worker
    basis: Mapped[str] = mapped_column(String(16))  # REAL or SYNTHETIC (demo, labelled)
    status: Mapped[str] = mapped_column(String(12), index=True)
    # Set when an approved plan by section gives the booking a tanker (plan to driver link).
    plan_id: Mapped[str | None] = mapped_column(String(120))
    tanker_id: Mapped[str | None] = mapped_column(String(16), index=True)
    station_id: Mapped[str | None] = mapped_column(String(16))
    trip_n: Mapped[int | None] = mapped_column(Integer)
    depart: Mapped[str | None] = mapped_column(String(5))
    arrive: Mapped[str | None] = mapped_column(String(5))
    stop_id: Mapped[str | None] = mapped_column(String(64))
