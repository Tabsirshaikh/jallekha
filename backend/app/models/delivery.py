from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, IdTimestampMixin


class Delivery(IdTimestampMixin, Base):
    """One tanker visit to one stop (F12, T3). `created_at` is when the delivery started.

    The plain OTP is never stored: only the nonce and its hash (S3 `services/otp.py`).
    Wrong OTP attempts are counted per visit and survive a reissued OTP.
    """

    __tablename__ = "delivery"

    stop_id: Mapped[str] = mapped_column(String(64), index=True)
    driver_id: Mapped[str] = mapped_column(String(64), index=True)
    stop_lat: Mapped[float] = mapped_column(Float)
    stop_lon: Mapped[float] = mapped_column(Float)
    otp_representative_id: Mapped[str | None] = mapped_column(ForeignKey("representative.id"))
    otp_nonce: Mapped[str | None] = mapped_column(String(32))
    otp_code_hash: Mapped[str | None] = mapped_column(String(64))
    otp_digits: Mapped[int | None] = mapped_column(Integer)
    otp_issued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    otp_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    otp_wrong_attempts: Mapped[int] = mapped_column(Integer, default=0)
    # OTP tries from outside the geofence (never attempts; logged up to outside_tries_max).
    outside_tries: Mapped[int] = mapped_column(Integer, default=0)
    otp_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    residents_sampled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sample_seed: Mapped[str | None] = mapped_column(String(64))
    # REAL (live delivery) or SYNTHETIC (demo, labelled on screen).
    basis: Mapped[str] = mapped_column(String(16))
