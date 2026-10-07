"""SQLAlchemy models: one table per file. Import each model module here so create_all sees it."""

from app.models.base import Base, IdTimestampMixin, new_id, utcnow
from app.models.booking import Booking
from app.models.complaint import Complaint
from app.models.contest import Contest
from app.models.contest_reply import ContestReply
from app.models.debt_day import DebtDay
from app.models.delivery import Delivery
from app.models.delivery_outcome import DeliveryOutcome
from app.models.delivery_roster import DeliveryRoster
from app.models.delivery_stop import DeliveryStop
from app.models.delivery_version import DeliveryVersion
from app.models.duplicate_link import DuplicateLink
from app.models.intake_item import IntakeItemRecord
from app.models.ledger_entry import LedgerEntryRecord
from app.models.ledger_head import LedgerHead
from app.models.plan_record import StoredPlan
from app.models.representative import Representative
from app.models.resident import Resident
from app.models.resident_response import ResidentResponse
from app.models.section_check_outcome import SectionCheckOutcome
from app.models.supply_notice import SupplyNotice
from app.models.voice_note import VoiceNote
from app.models.water_debt_account import WaterDebtAccount

__all__ = [
    "Base",
    "Booking",
    "Complaint",
    "Contest",
    "ContestReply",
    "DebtDay",
    "Delivery",
    "DeliveryOutcome",
    "DeliveryRoster",
    "DeliveryStop",
    "DeliveryVersion",
    "DuplicateLink",
    "IdTimestampMixin",
    "IntakeItemRecord",
    "LedgerEntryRecord",
    "LedgerHead",
    "Representative",
    "Resident",
    "ResidentResponse",
    "StoredPlan",
    "SupplyNotice",
    "SectionCheckOutcome",
    "VoiceNote",
    "WaterDebtAccount",
    "new_id",
    "utcnow",
]
