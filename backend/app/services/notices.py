"""Supply-notice feed (F15, T5): an officer enters an HMWSSB notice; it becomes an outage (A5).

Officer entry only. docs/research/P3.md F15 decided "Keep officer entry": HMWSSB notices are
press releases with area lists and hours, there is no structured or machine-readable feed, and
D14 has not been fetched, so there is nothing to parse.

Steps: check the input (a proper time range with a zone) -> refuse a duplicate (same source,
areas and times) -> match each area name to a 2016 ward using P1's tables, with a confidence;
names that are unknown, ambiguous, unplaced or only similar are flagged for an officer and never
guessed -> store the notice -> call P2's `create_outage` for the matched wards (source
"notice", reason code `hmwssb_supply_notice`) -> write `outage_created` (A5) and
`notice_published` (T6) to the stored ledger. The notice text stays in `supply_notice`; ledger
payloads hold ids, codes and numbers only.
"""

from __future__ import annotations

import csv
import difflib
import hashlib
import json
import logging
import re
import unicodedata
import uuid
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.engine import Engine

from app.config.notices import ALERT_TEMPLATES, NOTICE_CONFIG, NOTICE_SOURCES
from app.db import create_all, make_engine, make_session_factory
from app.models import SupplyNotice
from app.models.base import utcnow
from app.services import ledger_store, outage
from app.services.sms import SmsMessage, SmsSender, message_language

logger = logging.getLogger("jallekha.notices")

_WARD_PREFIX = re.compile(r"^ward\s+\d+\s+", re.IGNORECASE)


def normalise(name: str) -> str:
    """Case, accents and punctuation removed: 'RAMANTHAPUR(DIV 14)' -> 'ramanthapur div 14'."""
    text = unicodedata.normalize("NFKD", name).casefold()
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"[^0-9a-z]+", " ", text).strip()


# --- area matching -----------------------------------------------------------------------


@dataclass(frozen=True)
class AreaMatch:
    name: str  # as written in the notice
    status: str  # matched | flagged
    ward_id: str | None
    ward_name: str | None
    confidence: float  # 1.0 exact; otherwise difflib similarity of the closest name
    method: str | None  # ward_name | section_name | fuzzy
    reason: str | None = None  # no_confident_match | ambiguous | section_unplaced
    suggestion: str | None = None  # shown to the officer, never used automatically


class AreaIndex:
    """Ward and section names from P1's tables (2016 GHMC wards)."""

    def __init__(self, sections: Iterable[Mapping[str, str]], wards: Mapping[str, str]) -> None:
        self.wards = dict(wards)
        self._names: dict[str, set[tuple[str, str]]] = {}  # name -> {(ward_id, method)}
        self._unplaced: set[str] = set()
        self.section_count = 0
        self.placed_section_count = 0
        for ward_id, ward_name in self.wards.items():
            self._add(_WARD_PREFIX.sub("", ward_name), ward_id, "ward_name")
        for row in sections:
            self.section_count += 1
            names = {normalise(row.get("section", "")), normalise(row.get("lookup_name", ""))}
            names.discard("")
            ward_id = row.get("ward_id") or ""
            if row.get("status") == "MAPPED" and ward_id:
                self.placed_section_count += 1
                for name in names:
                    self._add(name, ward_id, "section_name")
            else:
                self._unplaced |= names

    @property
    def ward_count(self) -> int:
        return len(self.wards)

    def _add(self, name: str, ward_id: str, method: str) -> None:
        key = normalise(name)
        if key:
            self._names.setdefault(key, set()).add((ward_id, method))

    @classmethod
    def from_files(
        cls, sections_path: str | None = None, wards_path: str | None = None
    ) -> AreaIndex:
        sections_file = Path(sections_path or NOTICE_CONFIG.sections_path)
        with sections_file.open(encoding="utf-8", newline="") as handle:
            sections = list(csv.DictReader(handle))
        geojson = json.loads(
            Path(wards_path or NOTICE_CONFIG.wards_path).read_text(encoding="utf-8")
        )
        wards = {f["properties"]["@id"]: f["properties"]["name"] for f in geojson["features"]}
        return cls(sections, wards)

    def match(self, name: str) -> AreaMatch:
        key = normalise(name)
        exact = self._names.get(key, set())
        ward_ids = sorted({ward_id for ward_id, _ in exact})
        if len(ward_ids) == 1:
            ward_id = ward_ids[0]
            methods = {method for _, method in exact}
            method = "ward_name" if "ward_name" in methods else "section_name"
            return AreaMatch(name, "matched", ward_id, self.wards.get(ward_id), 1.0, method)
        if len(ward_ids) > 1:
            names = ", ".join(self.wards.get(w, w) for w in ward_ids)
            return AreaMatch(name, "flagged", None, None, 1.0, None, "ambiguous", names)
        if key in self._unplaced:
            return AreaMatch(name, "flagged", None, None, 1.0, None, "section_unplaced")
        return self._closest(name, key)

    def _closest(self, name: str, key: str) -> AreaMatch:
        best_score, best_names = 0.0, []
        for candidate in self._names:
            score = difflib.SequenceMatcher(None, key, candidate).ratio()
            if score > best_score:
                best_score, best_names = score, [candidate]
            elif score == best_score:
                best_names.append(candidate)
        best_wards = sorted({w for n in best_names for w, _ in self._names[n]})
        suggestion = None
        if best_score >= NOTICE_CONFIG.area_suggestion_min_similarity and len(best_wards) == 1:
            suggestion = self.wards.get(best_wards[0])
        score = round(best_score, 3)
        if score >= NOTICE_CONFIG.area_match_min_confidence and len(best_wards) == 1:
            ward_id = best_wards[0]
            return AreaMatch(name, "matched", ward_id, self.wards.get(ward_id), score, "fuzzy")
        return AreaMatch(name, "flagged", None, None, score, None, "no_confident_match", suggestion)


# --- input -------------------------------------------------------------------------------


@dataclass(frozen=True)
class NoticeInput:
    source: str
    raw_text: str
    area_names: tuple[str, ...]
    start: datetime
    end: datetime
    entered_by: str
    source_ref: str | None = None
    people_affected: float | None = None
    is_synthetic: bool = False


def _time(value: Any, name: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} is required (ISO 8601 with a time zone)")
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{name} is not a valid ISO 8601 time") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{name} needs a time zone (for example +05:30)")
    return parsed.astimezone(UTC)


def notice_from_json(data: Any) -> NoticeInput:
    """Check one officer entry. Raises ValueError with a readable reason."""
    if not isinstance(data, Mapping):
        raise ValueError("A notice must be a JSON object")
    source = data.get("source")
    if source not in NOTICE_SOURCES:
        raise ValueError(f"source must be one of {list(NOTICE_SOURCES)}")
    raw_text = data.get("raw_text")
    if not isinstance(raw_text, str) or not raw_text.strip():
        raise ValueError("raw_text (the notice as published) is required")
    if len(raw_text) > NOTICE_CONFIG.max_raw_text_chars:
        raise ValueError("raw_text is too long")
    names = data.get("area_names")
    if not isinstance(names, list) or not names:
        raise ValueError("area_names must be a non-empty list")
    if len(names) > NOTICE_CONFIG.max_area_names:
        raise ValueError("Too many area names")
    if not all(isinstance(n, str) and n.strip() for n in names):
        raise ValueError("Every area name must be non-empty text")
    start, end = _time(data.get("start"), "start"), _time(data.get("end"), "end")
    if end <= start:
        raise ValueError("end must be after start")
    entered_by = data.get("entered_by")
    if not isinstance(entered_by, str) or not entered_by.strip() or len(entered_by) > 64:
        raise ValueError("entered_by (the officer's id) is required")
    people = data.get("people_affected")
    if people is not None:
        if isinstance(people, bool) or not isinstance(people, int | float) or people < 0:
            raise ValueError("people_affected must be a number of 0 or more")
        people = float(people)
    source_ref = data.get("source_ref")
    if source_ref is not None and (not isinstance(source_ref, str) or len(source_ref) > 512):
        raise ValueError("source_ref must be text of at most 512 characters")
    return NoticeInput(
        source=source,
        raw_text=raw_text.strip(),
        area_names=tuple(n.strip() for n in names),
        start=start,
        end=end,
        entered_by=entered_by.strip(),
        source_ref=source_ref,
        people_affected=people,
        is_synthetic=bool(data.get("is_synthetic", False)),
    )


def fingerprint(notice: NoticeInput) -> str:
    """Same source, same areas (any order or case) and same times = the same notice."""
    areas = sorted({normalise(name) for name in notice.area_names})
    key = json.dumps(
        [notice.source, areas, notice.start.isoformat(), notice.end.isoformat()],
        ensure_ascii=True,
    )
    return hashlib.sha256(key.encode()).hexdigest()


# --- alerts ------------------------------------------------------------------------------


def render_alert(key: str, language: str, params: Mapping[str, str]) -> str:
    templates = ALERT_TEMPLATES[key]
    return templates[message_language(language)].format(**params)


def _local(moment: datetime) -> str:
    return (moment + timedelta(minutes=NOTICE_CONFIG.display_utc_offset_minutes)).strftime(
        "%d %b %H:%M"
    )


def _hours_text(hours: float) -> str:
    return str(int(hours)) if float(hours).is_integer() else f"{hours:.1f}"


# --- the service -------------------------------------------------------------------------


@dataclass(frozen=True)
class NoticeResult:
    """created (outage made) | needs_review (saved, no ward matched) | duplicate | invalid."""

    status: str
    notice_id: str | None = None
    outage_id: str | None = None
    ward_ids: list[str] = field(default_factory=list)
    matched: list[AreaMatch] = field(default_factory=list)
    flagged: list[AreaMatch] = field(default_factory=list)
    hours: float | None = None
    people_affected: float | None = None
    people_affected_basis: str | None = None
    needs_officer_review: bool = False
    outage: outage.OutageEvent | None = None
    ledger_seqs: list[int] = field(default_factory=list)
    error: str | None = None


def _load_evidence(path: str) -> list[dict[str, str]]:
    with Path(path).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


class NoticeService:
    def __init__(
        self,
        engine: Engine,
        ledger: Any | None = None,
        areas: AreaIndex | None = None,
        evidence: Sequence[Mapping[str, str]] | None = None,
        clock: Callable[[], datetime] = utcnow,
    ) -> None:
        self.engine = engine
        self._sessions = make_session_factory(engine)
        self._ledger = ledger if ledger is not None else ledger_store.get_ledger()
        self._areas = areas or AreaIndex.from_files()
        self._evidence = (
            [dict(r) for r in evidence]
            if evidence is not None
            else _load_evidence(NOTICE_CONFIG.evidence_path)
        )
        self._clock = clock

    def enter(self, data: Any) -> NoticeResult:
        """Officer entry of one notice (JSON object)."""
        try:
            notice = notice_from_json(data)
        except ValueError as exc:
            return NoticeResult("invalid", error=str(exc))
        notice_print = fingerprint(notice)
        with self._sessions() as session:
            existing = session.scalars(
                select(SupplyNotice).where(SupplyNotice.fingerprint == notice_print)
            ).first()
            if existing is not None:
                return NoticeResult(
                    "duplicate",
                    existing.id,
                    existing.outage_id,
                    json.loads(existing.ward_ids_json),
                    hours=existing.hours,
                    needs_officer_review=existing.needs_officer_review,
                )

        matches = [self._areas.match(name) for name in notice.area_names]
        matched = [m for m in matches if m.status == "matched"]
        flagged = [m for m in matches if m.status == "flagged"]
        ward_ids = sorted({m.ward_id for m in matched if m.ward_id})
        hours = (notice.end - notice.start).total_seconds() / 3600
        people, people_basis = self._people(notice, ward_ids)
        review = bool(flagged) or not ward_ids or notice.people_affected is None
        notice_id = str(uuid.uuid4())

        event = args = None
        if ward_ids:
            event, args = outage.create_outage(
                outage_id=str(uuid.uuid4()),
                ward_ids=ward_ids,
                start=notice.start,
                end=notice.end,
                source="notice",
                reason=NOTICE_CONFIG.outage_reason_code,
                created_by=notice.entered_by,
                known_wards=set(self._areas.wards),
                people_affected=people or 0.0,
            )
        status = "created" if event is not None else "needs_review"
        with self._sessions() as session, session.begin():
            session.add(
                SupplyNotice(
                    id=notice_id,
                    created_at=self._clock(),
                    source=notice.source,
                    source_ref=notice.source_ref,
                    raw_text=notice.raw_text,
                    area_names_json=json.dumps(list(notice.area_names), ensure_ascii=False),
                    matched_json=json.dumps([asdict(m) for m in matched], ensure_ascii=False),
                    flagged_json=json.dumps([asdict(m) for m in flagged], ensure_ascii=False),
                    ward_ids_json=json.dumps(ward_ids),
                    area_match_basis=(
                        "DERIVED: exact name match to GHMC 2016 ward names and P1's placed "
                        "sections (section_to_ward_2016.csv); others flagged for an officer"
                    ),
                    start_at=notice.start,
                    end_at=notice.end,
                    hours=hours,
                    hours_basis="DERIVED: end - start",
                    people_affected=people,
                    people_affected_basis=people_basis,
                    needs_officer_review=review,
                    entered_by=notice.entered_by,
                    status=status,
                    outage_id=event.outage_id if event else None,
                    fingerprint=notice_print,
                    basis="SYNTHETIC" if notice.is_synthetic else "REAL",
                    ledger_missing=True,
                )
            )

        seqs = self._log(notice_id, notice, event, args, ward_ids, flagged, hours, people, review)
        return NoticeResult(
            status,
            notice_id,
            event.outage_id if event else None,
            ward_ids,
            matched,
            flagged,
            hours,
            people,
            people_basis,
            review,
            event,
            seqs,
        )

    def _people(self, notice: NoticeInput, ward_ids: list[str]) -> tuple[float | None, str | None]:
        if notice.people_affected is not None:
            return notice.people_affected, "REPORTED: officer figure"
        if not ward_ids:
            return None, None
        return outage.people_in_wards(ward_ids, self._evidence), (
            "DERIVED, HISTORICAL: Census 2011 population of the matched wards (whole wards; a "
            "notice may cover only part of a ward). Rule OPEN, owner to confirm; officer to check"
        )

    def _log(
        self,
        notice_id: str,
        notice: NoticeInput,
        event: outage.OutageEvent | None,
        args: dict[str, Any] | None,
        ward_ids: list[str],
        flagged: list[AreaMatch],
        hours: float,
        people: float | None,
        review: bool,
    ) -> list[int]:
        """outage_created (A5's payload, entity fields copied in), then notice_published."""
        writes: list[tuple[str, dict[str, Any]]] = []
        if event is not None and args is not None:
            payload = {
                "entity_type": args["entity_type"],
                "entity_id": args["entity_id"],
                **args["payload"],
            }
            writes.append((args["event_type"], payload))
        writes.append(
            (
                "notice_published",
                {
                    "entity_type": "supply_notice",
                    "entity_id": notice_id,
                    "outage_id": event.outage_id if event else None,
                    "source": notice.source,
                    "ward_ids": ward_ids,
                    "flagged_count": len(flagged),
                    "hours": round(hours, 3),
                    "people_affected": people,
                    "needs_officer_review": review,
                    "is_synthetic": notice.is_synthetic,
                },
            )
        )
        seqs: list[int] = []
        try:
            for event_type, payload in writes:
                seqs.append(self._ledger.record(event_type, payload, notice.entered_by).seq)
        except Exception:
            logger.exception("Ledger write failed for supply notice %s", notice_id)
            return seqs
        with self._sessions() as session, session.begin():
            session.execute(
                update(SupplyNotice)
                .where(SupplyNotice.id == notice_id)
                .values(ledger_missing=False)
            )
        return seqs

    def send_alerts(
        self, notice_id: str, recipients: Iterable[tuple[str, str]], sms: SmsSender
    ) -> int:
        """Send the alert (template key + parameters) to (phone, language) pairs. Recipients
        come from the caller (there is no resident registry yet); phones are not stored."""
        with self._sessions() as session:
            notice = session.get(SupplyNotice, notice_id)
            if notice is None:
                raise ValueError(f"No supply notice {notice_id}")
            start = (
                notice.start_at.replace(tzinfo=UTC)
                if notice.start_at.tzinfo is None
                else notice.start_at
            )
            end = (
                notice.end_at.replace(tzinfo=UTC) if notice.end_at.tzinfo is None else notice.end_at
            )
            params = {
                "areas": ", ".join(json.loads(notice.area_names_json)),
                "start": _local(start),
                "end": _local(end),
                "hours": _hours_text(notice.hours),
            }
        count = 0
        for phone, language in recipients:
            sms.send(
                SmsMessage(
                    to=phone,
                    template_key=NOTICE_CONFIG.alert_template_key,
                    language=message_language(language),
                    params=params,
                )
            )
            count += 1
        return count

    def notice_ids_missing_ledger(self) -> list[str]:
        with self._sessions() as session:
            return list(
                session.scalars(
                    select(SupplyNotice.id).where(SupplyNotice.ledger_missing.is_(True))
                )
            )


_default: NoticeService | None = None


def default_service() -> NoticeService:
    """The application's notice feed (DATABASE_URL, stored ledger, P1's area tables)."""
    global _default
    if _default is None:
        engine = make_engine()
        create_all(engine)
        _default = NoticeService(engine)
    return _default
