from __future__ import annotations

from sqlalchemy import ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class DeliveryVersion(Base):
    """How many times a delivery has been saved (optimistic lock).

    A write made from a stale read is refused (`DeliveryConflict`), so two people acting on one
    delivery at the same moment cannot silently overwrite each other. A separate table, so the
    `delivery` table itself did not change.
    """

    __tablename__ = "delivery_version"

    delivery_id: Mapped[str] = mapped_column(ForeignKey("delivery.id"), primary_key=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
