from __future__ import annotations

from sqlalchemy import Boolean, Float, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, IdTimestampMixin


class Complaint(IdTimestampMixin, Base):
    """One resident complaint (F13/F14). `created_at` is the report time in UTC.

    Location is optional: a missed call has none until the caller answers the ask-back SMS.
    """

    __tablename__ = "complaint"

    category: Mapped[str] = mapped_column(String(32), index=True)
    # How the category was set: REPORTED (button), DERIVED (keyword), ASSUMED (missed call) or
    # PENDING (voice note waiting for a human transcript).
    category_basis: Mapped[str | None] = mapped_column(Text)
    lat: Mapped[float | None] = mapped_column(Float)
    lon: Mapped[float | None] = mapped_column(Float)
    household_id: Mapped[str | None] = mapped_column(String(64), index=True)
    text: Mapped[str | None] = mapped_column(Text)
    language: Mapped[str | None] = mapped_column(String(8))
    language_basis: Mapped[str | None] = mapped_column(Text)
    # Voice notes (T4): speech-recognition confidence when the model reports one.
    transcript_confidence: Mapped[float | None] = mapped_column(Float)
    needs_human_transcription: Mapped[bool] = mapped_column(Boolean, default=False)
    # Field worker who reported for a household or location (F14 "reporting for others").
    reporter_id: Mapped[str | None] = mapped_column(String(64))
    # open | awaiting_location | needs_transcription
    status: Mapped[str] = mapped_column(String(24), default="open")
    channel: Mapped[str] = mapped_column(String(32))
    area_id: Mapped[str | None] = mapped_column(String(64), index=True)
    # REAL (resident report) or SYNTHETIC (demo stream, labelled on screen).
    basis: Mapped[str] = mapped_column(String(16))
