from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, IdTimestampMixin, utcnow


class StoredPlan(IdTimestampMixin, Base):
    """A daily plan built through the API (A7 planner, T9 gate; Wave 1).

    The plan itself is not stored (no pickling): `recipe_json` says how to rebuild it (the
    planner is deterministic) and `digest` is the digest of the plan built, checked on every
    rebuild. The officer's state is stored as data: `checked_json` is
    [{"group", "reason"}] in check order; approval fields as on the plan. Reasons stay here,
    the ledger has only their SHA-256. `created_at` (UTC) is when the plan was stored.
    """

    __tablename__ = "plan_record"

    plan_id: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    day: Mapped[str] = mapped_column(String(10), index=True)  # YYYY-MM-DD
    recipe_json: Mapped[str] = mapped_column(Text)  # {source, replay, scenario, seed, day, ...}
    digest: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16), default="DRAFT")  # DRAFT | APPROVED
    flags_total: Mapped[int] = mapped_column(Integer)  # for lists without a rebuild
    checked_json: Mapped[str] = mapped_column(Text, default="[]")
    approved_by: Mapped[str | None] = mapped_column(String(64))
    approval_reason: Mapped[str | None] = mapped_column(Text)
    basis_json: Mapped[str] = mapped_column(Text)  # labels shown with the plan
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )
