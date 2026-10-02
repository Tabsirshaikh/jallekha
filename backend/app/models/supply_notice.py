from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, IdTimestampMixin


class SupplyNotice(IdTimestampMixin, Base):
    """An HMWSSB supply-interruption notice entered by an officer (F15, T5).

    The notice text stays here; the ledger gets only ids and numbers. Area names are matched to
    2016 wards with a confidence; unmatched or uncertain names are flagged for an officer, never
    guessed. `fingerprint` (source + areas + times) keeps the same notice from being entered
    twice. `created_at` (UTC) is the entry time.
    """

    __tablename__ = "supply_notice"

    source: Mapped[str] = mapped_column(String(32))
    source_ref: Mapped[str | None] = mapped_column(String(512))  # URL or reference, optional
    raw_text: Mapped[str] = mapped_column(Text)
    area_names_json: Mapped[str] = mapped_column(Text)  # names as written in the notice
    matched_json: Mapped[str] = mapped_column(Text)  # [{name, ward_id, ward_name, ...}]
    flagged_json: Mapped[str] = mapped_column(Text)  # names for an officer, with the reason
    ward_ids_json: Mapped[str] = mapped_column(Text)
    area_match_basis: Mapped[str] = mapped_column(Text)
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    hours: Mapped[float] = mapped_column(Float)
    hours_basis: Mapped[str] = mapped_column(String(64))
    people_affected: Mapped[float | None] = mapped_column(Float)
    people_affected_basis: Mapped[str | None] = mapped_column(Text)
    needs_officer_review: Mapped[bool] = mapped_column(Boolean, default=False)
    entered_by: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16))  # created | needs_review
    outage_id: Mapped[str | None] = mapped_column(String(36), index=True)
    fingerprint: Mapped[str] = mapped_column(String(64), unique=True)
    # REAL (an HMWSSB notice) or SYNTHETIC (demo, labelled on screen).
    basis: Mapped[str] = mapped_column(String(16))
    # True while a ledger entry is expected but not written (logged again later).
    ledger_missing: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
