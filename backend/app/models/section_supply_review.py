"""Append-only officer assessments; no existing-table migration is needed."""

from sqlalchemy import Boolean, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, IdTimestampMixin


class SectionSupplyReview(IdTimestampMixin, Base):
    __tablename__ = "section_supply_review"
    section_id: Mapped[str] = mapped_column(String(160), index=True)
    data_json: Mapped[str] = mapped_column(Text)
    ledger_missing: Mapped[bool] = mapped_column(Boolean, default=True)
