from __future__ import annotations

from sqlalchemy import Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, IdTimestampMixin


class DuplicateLink(IdTimestampMixin, Base):
    """A complaint marked as a duplicate by the F13 rule (T1). One link per child."""

    __tablename__ = "duplicate_link"

    child_id: Mapped[str] = mapped_column(ForeignKey("complaint.id"), unique=True)
    # Cluster root (first report) and the complaint the rule actually matched.
    parent_id: Mapped[str] = mapped_column(ForeignKey("complaint.id"), index=True)
    matched_id: Mapped[str] = mapped_column(ForeignKey("complaint.id"))
    rule: Mapped[str] = mapped_column(String(16))  # household | location_time
    distance_m: Mapped[float] = mapped_column(Float)
    hours_apart: Mapped[float] = mapped_column(Float)
    text_score: Mapped[float | None] = mapped_column(Float)
    basis: Mapped[str] = mapped_column(String(16), default="DERIVED")
