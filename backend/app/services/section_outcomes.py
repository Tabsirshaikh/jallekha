"""Persist field checks; notes stay off the ledger and repeat visits do not inflate precision."""

from __future__ import annotations

import hashlib
import json
from datetime import date
from threading import RLock
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config.section_outcomes import SECTION_OUTCOME_CONFIG as CONFIG
from app.models import SectionCheckOutcome
from app.models.base import utcnow

_write_lock = RLock()


def view(row):
    return {
        "id": row.id,
        "section_id": row.section_id,
        "period_year": row.period_year,
        "checked_on": row.checked_on.isoformat(),
        "could_not_book": row.could_not_book,
        "note": row.note,
        "note_sha256": row.note_sha256,
        "screening_sha256": row.screening_sha256,
        "recorded_by": row.recorded_by,
        "ledger_missing": row.ledger_missing,
        "basis": "REAL",
    }


class SectionOutcomeStore:
    def __init__(self, engine, ledger, candidates, clock=utcnow):
        self.engine, self.ledger, self.candidates, self.clock = engine, ledger, candidates, clock
        SectionCheckOutcome.__table__.create(engine, checkfirst=True)

    def record(self, section_id, outcome, checked_on, note, actor, check_id):
        if outcome not in ("yes", "no", "unclear"):
            raise ValueError("Outcome must be yes, no or unclear")
        if (
            not isinstance(checked_on, date)
            or checked_on > self.clock().astimezone(ZoneInfo(CONFIG.timezone)).date()
        ):
            raise ValueError("Check date must not be in the future")
        if not isinstance(note, str) or len(note) > CONFIG.maximum_note_chars:
            raise ValueError("Note is too long")
        if not actor or not check_id or len(check_id) > 36:
            raise ValueError("A check id and authenticated actor are required")
        candidate = self.candidates().get(section_id)
        if not candidate or not candidate["field_check_candidate"]:
            raise ValueError("Section is not on the flagged visit list")
        digest = hashlib.sha256(note.encode()).hexdigest()
        screening = hashlib.sha256(
            json.dumps(candidate, sort_keys=True, default=str).encode()
        ).hexdigest()
        with _write_lock:
            with Session(self.engine, expire_on_commit=False) as session:
                row = session.get(SectionCheckOutcome, check_id)
                if row:
                    if (
                        row.section_id,
                        row.could_not_book,
                        row.checked_on,
                        row.note_sha256,
                        row.recorded_by,
                    ) != (section_id, outcome, checked_on, digest, actor):
                        raise ValueError("Check id already belongs to a different observation")
                else:
                    row = SectionCheckOutcome(
                        id=check_id,
                        created_at=self.clock(),
                        section_id=section_id,
                        period_year=candidate["period_year"],
                        screening_sha256=screening,
                        checked_on=checked_on,
                        could_not_book=outcome,
                        note=note,
                        note_sha256=digest,
                        recorded_by=actor,
                        ledger_missing=True,
                    )
                    session.add(row)
                    session.commit()
                if row.ledger_missing:
                    # A failed ledger append leaves a durable pending observation. Retrying the
                    # same check id appends once, then marks it linked; pending rows do not score.
                    try:
                        already_linked = any(
                            e.event_type == "section_check_recorded" and e.entity_id == row.id
                            for e in self.ledger.entries
                        )
                        if not already_linked:
                            self.ledger.record(
                                "section_check_recorded",
                                {
                                    "entity_type": "section_check",
                                    "entity_id": row.id,
                                    "section_id": section_id,
                                    "period_year": row.period_year,
                                    "checked_on": checked_on.isoformat(),
                                    "could_not_book": outcome,
                                    "note_sha256": digest,
                                    "screening_sha256": row.screening_sha256,
                                },
                                actor,
                            )
                    except Exception:
                        return view(row)
                    row.ledger_missing = False
                    session.commit()
                return view(row)

    def list(self):
        with Session(self.engine) as session:
            return [
                view(r)
                for r in session.scalars(
                    select(SectionCheckOutcome).order_by(
                        SectionCheckOutcome.checked_on.desc(),
                        SectionCheckOutcome.created_at.desc(),
                        SectionCheckOutcome.id.desc(),
                    )
                )
            ]

    def summary(self):
        latest = {}
        pending = 0
        for row in self.list():
            if row["ledger_missing"]:
                pending += 1
                continue
            latest.setdefault((row["section_id"], row["period_year"]), row)
        yes = sum(r["could_not_book"] == "yes" for r in latest.values())
        no = sum(r["could_not_book"] == "no" for r in latest.values())
        n = yes + no
        return {
            "distinct_sections": len(latest),
            "decisive_sections": n,
            "yes": yes,
            "no": no,
            "unclear_sections": len(latest) - n,
            "pending_ledger": pending,
            "precision": yes / n if n >= CONFIG.minimum_decisive_sections else None,
            "minimum_decisive_sections": CONFIG.minimum_decisive_sections,
            "basis": "DERIVED",
            "threshold_basis": CONFIG.basis,
            "status": "MEASURED_ON_VISITED_FLAGS"
            if n >= CONFIG.minimum_decisive_sections
            else "NOT_YET_CHECKED_ON_GROUND",
            "limitation": (
                "Precision among visited flags only; "
                "no recall estimate or representative city sample."
            ),
        }
