from __future__ import annotations

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, IdTimestampMixin


class DebtDay(IdTimestampMixin, Base):
    """A closed day (A6 on a stored plan): which approved plan settled it, who closed it, and per
    ward what was planned, credited and owed (`summary_json`). A day is closed once (unique).
    The reason stays here; the ledger has only its SHA-256. `created_at` (UTC) is the close time.
    """

    __tablename__ = "debt_day"

    day: Mapped[str] = mapped_column(String(10), unique=True, index=True)  # YYYY-MM-DD
    # The approved supplied plan that settled it; empty when the day was closed without a plan.
    plan_id: Mapped[str | None] = mapped_column(String(80))
    plan_digest: Mapped[str | None] = mapped_column(String(64))
    closed_by: Mapped[str] = mapped_column(String(64))
    reason: Mapped[str] = mapped_column(Text)
    summary_json: Mapped[str] = mapped_column(Text)  # {ward_id: {planned, credited, ...}}
