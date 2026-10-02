"""SQLAlchemy models: one table per file. Import each model module here so create_all sees it."""

from app.models.base import Base, IdTimestampMixin, new_id, utcnow
from app.models.complaint import Complaint
from app.models.duplicate_link import DuplicateLink

__all__ = ["Base", "Complaint", "DuplicateLink", "IdTimestampMixin", "new_id", "utcnow"]
