"""Contests of a ward or booking ranking and the officer's reply (F16, T7).

A resident or councillor files a contest (reason code + text); the officer must reply with a
non-empty reason (checked here, not only in a UI) and an outcome code. One reply per contest.

The text stays in the `contest` / `contest_reply` tables. Filing writes `contest_filed` and
replying writes `contest_replied` through T6's stored ledger (`ledger_store`); payloads hold
ids, codes, numbers and the SHA-256 of the text, so a later edit of the stored text is
detected (`verify_text`). Phone numbers are never stored or logged: people are referred to by
id, and long digit runs are removed from the text before it is stored and hashed. A ledger
failure keeps the row and marks it `ledger_missing`, as in T4 and T5.
"""

from __future__ import annotations

import hashlib
import logging
import re
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.engine import Engine

from app.config.explain import (
    CONTEST_REASON_CODES,
    CONTEST_ROLES,
    CONTEST_TARGETS,
    EXPLAIN_CONFIG,
    REPLY_OUTCOME_CODES,
)
from app.db import make_session_factory
from app.models import Contest, ContestReply
from app.models.base import utcnow
from app.services import ledger_store

logger = logging.getLogger("jallekha.contest")

LEDGER_PAYLOAD_KEYS = frozenset(
    {
        "entity_type",
        "entity_id",
        "role",
        "target_type",
        "target_id",
        "reason_code",
        "reason_sha256",
        "text_chars",
        "reply_id",
        "officer_id",
        "outcome_code",
    }
)
_PERSON_ID = re.compile(r"^[A-Za-z][A-Za-z0-9_.:-]{0,63}$")  # starts with a letter: no phone
# A ward id (`relation/7848799`) or a booking id as the planner writes it
# (`2025-04-29:MANIKONDA (DIV 18):00387`: HMWSSB section names have spaces and brackets).
_TARGET_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 _.:/()-]{0,79}$")
_PHONE_LIKE = re.compile(r"^\+?\d{10,15}$")
# Indian mobile numbers (with +91 / 91 / 0 prefix) and any run of 10+ digits.
_PHONE_IN_TEXT = re.compile(r"(?:\+?91[\s-]?|0)?[6-9]\d{9}(?!\d)|\d{10,}")
REDACTED = "[number removed]"


def clean_text(text: Any) -> str | None:
    """Strip, remove phone-like digit runs; None if nothing is left."""
    if not isinstance(text, str):
        return None
    cleaned = _PHONE_IN_TEXT.sub(REDACTED, text).strip()
    return cleaned or None


def text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ContestResult:
    """filed | replied | invalid | not_found | already_replied"""

    status: str
    contest_id: str | None = None
    reply_id: str | None = None
    ledger_seq: int | None = None
    error: str | None = None


def _person(value: Any, name: str) -> str:
    if not isinstance(value, str) or not _PERSON_ID.match(value.strip()):
        raise ValueError(f"{name} must be an id starting with a letter (never a phone number)")
    return value.strip()


def _text(value: Any, name: str) -> tuple[str, str]:
    cleaned = clean_text(value)
    if cleaned is None:
        raise ValueError(f"A {name} is required (empty or whitespace-only text is rejected)")
    if len(cleaned) > EXPLAIN_CONFIG.max_reason_chars:
        raise ValueError(f"The {name} is longer than {EXPLAIN_CONFIG.max_reason_chars} characters")
    return cleaned, text_hash(cleaned)


def _utc_iso(moment: datetime) -> str:
    """ISO time in UTC; SQLite returns the stored UTC time without its zone."""
    return (moment if moment.tzinfo else moment.replace(tzinfo=UTC)).isoformat()


def _contest_view(row: Contest) -> dict[str, Any]:
    return {
        "contest_id": row.id,
        "created_at": _utc_iso(row.created_at),
        "filed_by": row.filed_by,
        "role": row.role,
        "target_type": row.target_type,
        "target_id": row.target_id,
        "reason_code": row.reason_code,
        "reason_text": row.reason_text,
        "status": row.status,
    }


def _reply_view(row: ContestReply) -> dict[str, Any]:
    return {
        "reply_id": row.id,
        "created_at": _utc_iso(row.created_at),
        "officer_id": row.officer_id,
        "outcome_code": row.outcome_code,
        "reason_text": row.reason_text,
    }


class ContestService:
    def __init__(
        self,
        engine: Engine,
        ledger: Any | None = None,
        clock: Callable[[], datetime] = utcnow,
    ) -> None:
        self.engine = engine
        self._sessions = make_session_factory(engine)
        self._ledger = ledger if ledger is not None else ledger_store.get_ledger()
        self._clock = clock

    # --- filing ----------------------------------------------------------------------------

    def file(self, data: Mapping[str, Any]) -> ContestResult:
        try:
            filed_by = _person(data.get("filed_by"), "filed_by")
            role = data.get("role")
            if role not in CONTEST_ROLES:
                raise ValueError(f"role must be one of {list(CONTEST_ROLES)}")
            target_type = data.get("target_type")
            if target_type not in CONTEST_TARGETS:
                raise ValueError(f"target_type must be one of {list(CONTEST_TARGETS)}")
            target_id = data.get("target_id")
            if (
                not isinstance(target_id, str)
                or not _TARGET_ID.match(target_id)
                or _PHONE_LIKE.match(target_id)
                # spaces and dots no longer break a number apart: "98765 43210" is a phone
                or _PHONE_IN_TEXT.search(re.sub(r"[\s.-]", "", target_id))
            ):
                raise ValueError("target_id must be a ward or booking id")
            reason_code = data.get("reason_code")
            if reason_code not in CONTEST_REASON_CODES:
                raise ValueError(f"reason_code must be one of {list(CONTEST_REASON_CODES)}")
            text, digest = _text(data.get("reason_text"), "contest reason")
        except ValueError as exc:
            return ContestResult("invalid", error=str(exc))

        contest_id = str(uuid.uuid4())
        with self._sessions() as session, session.begin():
            session.add(
                Contest(
                    id=contest_id,
                    created_at=self._clock(),
                    filed_by=filed_by,
                    role=role,
                    target_type=target_type,
                    target_id=target_id,
                    reason_code=reason_code,
                    reason_text=text,
                    reason_sha256=digest,
                    text_chars=len(text),
                    status="open",
                    ledger_missing=True,
                )
            )
        seq = self._log(
            "contest_filed",
            {
                "entity_type": "contest",
                "entity_id": contest_id,
                "role": role,
                "target_type": target_type,
                "target_id": target_id,
                "reason_code": reason_code,
                "reason_sha256": digest,
                "text_chars": len(text),
            },
            filed_by,
            Contest,
            contest_id,
        )
        return ContestResult("filed", contest_id, ledger_seq=seq)

    # --- replying --------------------------------------------------------------------------

    def reply(self, contest_id: str, data: Mapping[str, Any]) -> ContestResult:
        try:
            officer_id = _person(data.get("officer_id"), "officer_id")
            outcome_code = data.get("outcome_code")
            if outcome_code not in REPLY_OUTCOME_CODES:
                raise ValueError(f"outcome_code must be one of {list(REPLY_OUTCOME_CODES)}")
            text, digest = _text(data.get("reason_text"), "reply reason")
        except ValueError as exc:
            return ContestResult("invalid", contest_id, error=str(exc))

        reply_id = str(uuid.uuid4())
        with self._sessions() as session, session.begin():
            contest = session.get(Contest, contest_id)
            if contest is None:
                return ContestResult("not_found", contest_id, error="No such contest")
            existing = session.scalars(
                select(ContestReply).where(ContestReply.contest_id == contest_id)
            ).first()
            if existing is not None or contest.status != "open":
                return ContestResult(
                    "already_replied", contest_id, existing.id if existing else None,
                    error="This contest already has a reply",
                )  # fmt: skip
            session.add(
                ContestReply(
                    id=reply_id,
                    created_at=self._clock(),
                    contest_id=contest_id,
                    officer_id=officer_id,
                    outcome_code=outcome_code,
                    reason_text=text,
                    reason_sha256=digest,
                    text_chars=len(text),
                    ledger_missing=True,
                )
            )
            contest.status = "replied"
        seq = self._log(
            "contest_replied",
            {
                "entity_type": "contest",
                "entity_id": contest_id,
                "reply_id": reply_id,
                "officer_id": officer_id,
                "outcome_code": outcome_code,
                "reason_sha256": digest,
                "text_chars": len(text),
            },
            officer_id,
            ContestReply,
            reply_id,
        )
        return ContestResult("replied", contest_id, reply_id, seq)

    # --- reading ---------------------------------------------------------------------------

    def list_contests(
        self,
        *,
        status: str | None = None,
        target_type: str | None = None,
        target_id: str | None = None,
        filed_by: str | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[dict[str, Any]], int]:
        """Contests, newest first, narrowed by the given filters: (page of items, total).
        The stored text is returned as stored (phone-like runs were removed when it was filed)."""
        filters = [
            (Contest.status, status),
            (Contest.target_type, target_type),
            (Contest.target_id, target_id),
            (Contest.filed_by, filed_by),
        ]
        where = [column == value for column, value in filters if value is not None]
        with self._sessions() as session:
            total = session.scalar(select(func.count()).select_from(Contest).where(*where)) or 0
            rows = session.scalars(
                select(Contest)
                .where(*where)
                .order_by(Contest.created_at.desc(), Contest.id)
                .offset(offset)
                .limit(limit)
            ).all()
            return [_contest_view(row) for row in rows], total

    def get_contest(self, contest_id: str) -> dict[str, Any] | None:
        """One contest with its reply (`reply` is None while open); None if there is no such
        contest."""
        with self._sessions() as session:
            contest = session.get(Contest, contest_id)
            if contest is None:
                return None
            reply = session.scalars(
                select(ContestReply).where(ContestReply.contest_id == contest_id)
            ).first()
            view = _contest_view(contest)
            view["reply"] = _reply_view(reply) if reply else None
            return view

    # --- ledger ----------------------------------------------------------------------------

    def _log(
        self, event: str, payload: dict[str, Any], actor: str, model: type, row_id: str
    ) -> int | None:
        extra = set(payload) - LEDGER_PAYLOAD_KEYS
        if extra:  # ids, codes, numbers and hashes only
            raise ValueError(f"Ledger payload keys not allowed: {sorted(extra)}")
        try:
            entry = self._ledger.record(event, payload, actor)
        except Exception:
            logger.exception("Ledger write failed for %s %s", event, row_id)
            return None
        with self._sessions() as session, session.begin():
            session.execute(update(model).where(model.id == row_id).values(ledger_missing=False))
        return entry.seq

    def ids_missing_ledger(self) -> dict[str, list[str]]:
        with self._sessions() as session:
            return {
                "contest": list(
                    session.scalars(select(Contest.id).where(Contest.ledger_missing.is_(True)))
                ),
                "reply": list(
                    session.scalars(
                        select(ContestReply.id).where(ContestReply.ledger_missing.is_(True))
                    )
                ),
            }

    def verify_text(self, contest_id: str) -> dict[str, str]:
        """Compare the stored text with the hash in the ledger: match | edited |
        no_ledger_entry (| no_reply)."""
        hashes: dict[str, str] = {}
        for entry in self._ledger.entries:
            if entry.entity_type == "contest" and entry.entity_id == contest_id:
                kind = {"contest_filed": "contest", "contest_replied": "reply"}.get(
                    entry.event_type
                )
                if kind:
                    hashes[kind] = entry.payload.get("reason_sha256", "")
        with self._sessions() as session:
            contest = session.get(Contest, contest_id)
            if contest is None:
                raise ValueError(f"No contest {contest_id}")
            reply = session.scalars(
                select(ContestReply).where(ContestReply.contest_id == contest_id)
            ).first()
            texts = {"contest": contest.reason_text, "reply": reply.reason_text if reply else None}
        result: dict[str, str] = {}
        for kind, text in texts.items():
            if text is None:
                result[kind] = "no_reply"
            elif kind not in hashes:
                result[kind] = "no_ledger_entry"
            else:
                result[kind] = "match" if text_hash(text) == hashes[kind] else "edited"
        return result
