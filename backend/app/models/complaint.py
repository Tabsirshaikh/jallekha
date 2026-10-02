from __future__ import annotations

from sqlalchemy import Float, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, IdTimestampMixin


class Complaint(IdTimestampMixin, Base):
    """One resident complaint (F13/F14). `created_at` is the report time in UTC."""

    __tablename__ = "complaint"

    category: Mapped[str] = mapped_column(String(32), index=True)
    lat: Mapped[float] = mapped_column(Float)
    lon: Mapped[float] = mapped_column(Float)
    household_id: Mapped[str | None] = mapped_column(String(64), index=True)
    text: Mapped[str | None] = mapped_column(Text)
    language: Mapped[str | None] = mapped_column(String(8))
    channel: Mapped[str] = mapped_column(String(32))
    area_id: Mapped[str | None] = mapped_column(String(64), index=True)
    # REAL (resident report) or SYNTHETIC (demo stream, labelled on screen).
    basis: Mapped[str] = mapped_column(String(16))
