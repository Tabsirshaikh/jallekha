"""Supply assessments and seven-day delivery evidence, with replay-safe snapshots."""

import hashlib
import json
from datetime import UTC, date, datetime, timedelta
from threading import RLock

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config.allocation import ALLOCATION_CONFIG
from app.config.env import REPO_ROOT
from app.config.weekly_priority import WEEKLY_PRIORITY_CONFIG as CFG
from app.models import SectionSupplyReview
from app.services import section_plan, weekly_priority
from app.services.service_models import NeedWeights

_lock = RLock()


class SupplyReviewStore:
    def __init__(self, engine, ledger):
        self.engine, self.ledger = engine, ledger
        SectionSupplyReview.__table__.create(engine, checkfirst=True)

    def record(self, data, actor):
        basis = "SYNTHETIC (demo data)" if data.get("synthetic") else "REAL (officer observation)"
        data = {**data, "recorded_by": actor, "basis": basis}
        blob = json.dumps(data, sort_keys=True)
        with _lock, Session(self.engine, expire_on_commit=False) as session:
            row = session.get(SectionSupplyReview, data["id"])
            if row and row.data_json != blob:
                raise ValueError("Review id already belongs to another assessment")
            if row is None:
                row = SectionSupplyReview(
                    id=data["id"],
                    section_id=data["section_id"],
                    data_json=blob,
                    ledger_missing=True,
                )
                session.add(row)
                session.commit()
            if row.ledger_missing:
                if not any(
                    e.event_type == "section_supply_reviewed" and e.entity_id == row.id
                    for e in self.ledger.entries
                ):
                    self.ledger.record(
                        "section_supply_reviewed",
                        {
                            "entity_type": "section_supply_review",
                            "entity_id": row.id,
                            "section_id": row.section_id,
                            "assessment_sha256": hashlib.sha256(blob.encode()).hexdigest(),
                            "note_sha256": hashlib.sha256(data["note"].encode()).hexdigest(),
                        },
                        actor,
                    )
                row.ledger_missing = False
                session.commit()
            return {**data, "ledger_missing": row.ledger_missing}

    def latest(self, as_of):
        with Session(self.engine) as session:
            rows = session.scalars(select(SectionSupplyReview)).all()
            result = {}
            for row in sorted(
                rows,
                key=lambda r: (json.loads(r.data_json)["checked_on"], r.created_at, r.id),
                reverse=True,
            ):
                data = json.loads(row.data_json)
                if (
                    date.fromisoformat(data["checked_on"]) < as_of
                    and row.created_at.replace(tzinfo=UTC).astimezone(section_plan.IST).date()
                    <= as_of
                ):
                    result.setdefault(
                        row.section_id, {**data, "ledger_missing": row.ledger_missing}
                    )
            return result


def current_sections(as_of: date, reviews: SupplyReviewStore, deliveries, root=REPO_ROOT):
    """One count per confirmed load at a REAL registered stop; geography remains approximate.

    Complete records are an explicit officer assertion. Unresolved outcomes invalidate
    the section's completeness. A confirmed load is currently assumed to be 5,000 litres.
    """
    sections = section_plan.load_sections(root)
    assessments = reviews.latest(as_of)
    first = as_of - timedelta(days=CFG.window_days)
    start = datetime.combine(first, datetime.min.time(), section_plan.IST)
    end = datetime.combine(as_of, datetime.min.time(), section_plan.IST)
    places = {
        s.stop_id: section_plan.section_of_point(root, s.lat, s.lon)
        for s in deliveries.list_stops()
        if s.basis == "REAL"
    }
    paid, daily, pending = {}, {}, set()
    for d in deliveries.list_deliveries(
        stop_ids=list(places), started_from=start, started_before=end
    ):
        group = places.get(d.stop_id)
        if not group:
            continue
        if d.outcome is None or d.outcome.outcome in ("Unconfirmed", "Disputed"):
            pending.add(group)
        elif d.outcome.outcome == "Confirmed":
            paid[group] = paid.get(group, 0) + ALLOCATION_CONFIG.tanker_load_litres
            day = d.started_at.astimezone(section_plan.IST).date()
            daily[(group, day)] = daily.get((group, day), 0) + ALLOCATION_CONFIG.tanker_load_litres
    output = {}
    for info in sections.values():
        # Section ids match the F4 evidence file (division:name), not the allocation group.
        ident = f"{info.division}:{info.section}"
        review = assessments.get(ident)
        if info.group in pending and review:
            review = {**review, "records_complete": False}
        requirement = info.people * (review["tanker_share"] if review else 0)
        requirement *= ALLOCATION_CONFIG.minimum_litres_per_person_day
        deprived = sum(
            daily.get((info.group, first + timedelta(days=i)), 0) < requirement
            for i in range(CFG.window_days)
        )
        value = weekly_priority.calculate(
            info.people,
            info.need_weight(NeedWeights.default()),
            review,
            paid.get(info.group, 0),
            as_of,
            deprived,
        )
        output[info.group] = {
            **value,
            "section_id": ident,
            "section": info.section,
            "review": review,
        }
    return output
