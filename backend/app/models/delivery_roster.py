from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, IdTimestampMixin


class DeliveryRoster(IdTimestampMixin, Base):
    """The people of one delivery, in order (T3 `DeliveryState`).

    kind `representative`: the stop's representatives copied when the delivery started.
    kind `sample`: the residents sampled for the check, in sample order; `reply_order` is the
    order in which their replies were counted (empty while silent). Answers and times stay in
    `resident_response`. Keeping the order lets a reloaded state equal the one saved.
    """

    __tablename__ = "delivery_roster"
    __table_args__ = (UniqueConstraint("delivery_id", "kind", "position"),)

    delivery_id: Mapped[str] = mapped_column(ForeignKey("delivery.id"), index=True)
    kind: Mapped[str] = mapped_column(String(16))  # representative | sample
    position: Mapped[int] = mapped_column(Integer)
    member_id: Mapped[str] = mapped_column(String(64))  # representative.id or a resident_id
    reply_order: Mapped[int | None] = mapped_column(Integer)
