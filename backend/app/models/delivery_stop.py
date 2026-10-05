from __future__ import annotations

from sqlalchemy import Float, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, IdTimestampMixin


class DeliveryStop(IdTimestampMixin, Base):
    """A tanker stop registered by an officer (F12): where the geofence is drawn.

    Its 2-3 representatives are rows of `representative` and its residents rows of `resident`,
    both keyed by `stop_id`. A registered stop is never changed (no update route yet).
    `created_at` (UTC) is the registration time.
    """

    __tablename__ = "delivery_stop"

    stop_id: Mapped[str] = mapped_column(String(64), unique=True)
    lat: Mapped[float] = mapped_column(Float)
    lon: Mapped[float] = mapped_column(Float)
    # REAL (registered on the ground) or SYNTHETIC (demo, labelled on screen).
    basis: Mapped[str] = mapped_column(String(16))
    # The ward the stop serves (F20) and where that came from: OFFICER (named at registration),
    # DERIVED (placed on the 2016 ward polygons) or UNPLACED (outside every ward; ward empty).
    ward_id: Mapped[str | None] = mapped_column(String(64), index=True)
    ward_basis: Mapped[str] = mapped_column(String(16), default="UNPLACED")
