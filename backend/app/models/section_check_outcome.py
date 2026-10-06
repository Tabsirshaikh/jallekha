"""Append-only section visits; latest dated visit per section/year informs precision."""

from datetime import date

from sqlalchemy import Boolean, Date, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, IdTimestampMixin


class SectionCheckOutcome(IdTimestampMixin, Base):
    __tablename__ = "section_check_outcome"

    section_id: Mapped[str] = mapped_column(String(160), index=True)
    period_year: Mapped[int] = mapped_column(Integer)
    screening_sha256: Mapped[str] = mapped_column(String(64))
    checked_on: Mapped[date] = mapped_column(Date)
    could_not_book: Mapped[str] = mapped_column(String(8))
    note: Mapped[str] = mapped_column(Text)
    note_sha256: Mapped[str] = mapped_column(String(64))
    recorded_by: Mapped[str] = mapped_column(String(64))
    ledger_missing: Mapped[bool] = mapped_column(Boolean, default=True)
