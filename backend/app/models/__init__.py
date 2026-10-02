"""SQLAlchemy models: one table per file. Import each model module here so create_all sees it."""

from app.models.base import Base, IdTimestampMixin, new_id, utcnow
from app.models.complaint import Complaint
from app.models.delivery import Delivery
from app.models.delivery_outcome import DeliveryOutcome
from app.models.duplicate_link import DuplicateLink
from app.models.representative import Representative
from app.models.resident_response import ResidentResponse

__all__ = [
    "Base",
    "Complaint",
    "Delivery",
    "DeliveryOutcome",
    "DuplicateLink",
    "IdTimestampMixin",
    "Representative",
    "ResidentResponse",
    "new_id",
    "utcnow",
]
