"""Unified intake (F14, T4): every channel goes through one pipeline into a Complaint.

IntakeMessage (P2's `services/intake.py`, used as is) -> validate -> spam score (P2's
`services/spam.py`; spam is kept and marked, no complaint) -> language by script -> category
(button, the missed-call rule, or the keyword lists in `config/intake.py`; deterministic, no
LLM) -> Complaint -> T1 duplicate check (`services/dedup.py`) -> one result per item.

Channels: app, SMS webhook (any provider's field names), missed call (no text: "no water" is
ASSUMED, S3 review D14), field worker (reporting for a household or a location), voice notes
(server-side speech recognition, or a stored note for a human), and offline sync (a batch of
app / field-worker items, `client_id` as the idempotency key).

Privacy: raw phone numbers stay in memory only (hashed for the spam burst count, used once for
the ask-back SMS). Ledger payloads hold ids, codes and numbers only, never phone numbers, names
or free text. Created, merged and spam items are logged as complaint_received, complaint_merged
and complaint_marked_spam through T6's stored ledger (`ledger_store`); a ledger failure is logged
as an error and never loses the report.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import math
import re
import unicodedata
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Protocol

from sqlalchemy import func, select, update
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config.access import ACCESS_CONFIG
from app.config.intake import (
    CALLER_FIELDS,
    CATEGORY_ORDER,
    INTAKE_CONFIG,
    KEYWORDS,
    SMS_SENDER_FIELDS,
    SMS_TEXT_FIELDS,
    SMS_TIME_FIELDS,
)
from app.config.spam import SPAM_CONFIG
from app.config.trust import TRUST_CONFIG
from app.db import create_all, make_engine, make_session_factory
from app.models import Complaint, DuplicateLink, IntakeItemRecord, VoiceNote
from app.models.base import utcnow
from app.services import dedup, intake, ledger, ledger_store, spam
from app.services.sms import SmsMessage, SmsSender, get_sms_sender, message_language

logger = logging.getLogger("jallekha.intake")

CATEGORIES = frozenset(category for category, _ in TRUST_CONFIG.dedup_window_hours)
ASK_LOCATION_TEMPLATE = "intake.ask_location"
# Event types intake would log. None exists in ledger.EVENT_TYPES yet; adding them is a team
# decision (not done here).
PROPOSED_EVENTS = {
    "created": "complaint_received",
    "merged": "complaint_merged",
    "spam": "complaint_marked_spam",
}
LEDGER_PAYLOAD_KEYS = frozenset(
    {
        "entity_type",
        "entity_id",
        "intake_id",
        "channel",
        "category",
        "language",
        "parent_id",
        "complaint_status",
        "spam_score",
        "is_synthetic",
    }
)

# --- language and category ---------------------------------------------------------------

_SCRIPT_RANGES = (
    ("te", 0x0C00, 0x0C7F),  # Telugu
    ("hi", 0x0900, 0x097F),  # Devanagari
    ("ur", 0x0600, 0x06FF),  # Arabic script (Urdu)
    ("ur", 0x0750, 0x077F),
    ("ur", 0xFB50, 0xFDFF),
    ("ur", 0xFE70, 0xFEFF),
)
# Arabic letters often typed for their Urdu forms (keyboard differences).
_URDU_FORMS = str.maketrans({"ي": "ی", "ى": "ی", "ك": "ک", "ه": "ہ"})


def detect_language(text: str | None, hint: str | None = None) -> tuple[str | None, str]:
    """Language from the script most letters are written in; the client hint otherwise."""
    counts: dict[str, int] = defaultdict(int)
    for ch in text or "":
        if unicodedata.category(ch)[0] not in ("L", "M"):
            continue
        code = ord(ch)
        lang = next((name for name, low, high in _SCRIPT_RANGES if low <= code <= high), None)
        if lang is None and unicodedata.name(ch, "").startswith("LATIN"):
            lang = INTAKE_CONFIG.latin_language
        if lang is not None:
            counts[lang] += 1
    if counts:
        lang = max(sorted(counts), key=lambda name: counts[name])
        return lang, (
            f"DERIVED: script detection ({counts[lang]} of {sum(counts.values())} letters)"
        )
    if hint in ACCESS_CONFIG.supported_languages:
        return hint, "REPORTED: client language hint"
    return None, "UNKNOWN: no letters and no supported language hint"


def _normalise(text: str) -> str:
    text = unicodedata.normalize("NFC", text).translate(_URDU_FORMS).casefold()
    return re.sub(r"\s+", " ", text).strip()


def _matches(keyword: str, text: str, lang: str) -> bool:
    keyword = _normalise(keyword)
    if lang == "en":  # whole words only in Latin script ("leak" must not match "bleak")
        return re.search(rf"(?<!\w){re.escape(keyword)}(?!\w)", text) is not None
    return keyword in text


def classify(text: str | None, language: str | None = None) -> tuple[str, str]:
    """Category from the keyword lists; more specific categories first. 'other' if none."""
    if not text:
        return "other", "DERIVED: no text to read"
    normalised = _normalise(text)
    languages = [language] if language in KEYWORDS else []
    languages += [lang for lang in KEYWORDS if lang not in languages]
    for category in CATEGORY_ORDER:
        for lang in languages:
            for keyword in KEYWORDS[lang].get(category, ()):
                if _matches(keyword, normalised, lang):
                    return category, (
                        f"DERIVED: keyword '{keyword}' ({lang} list, config/intake.py)"
                    )
    return "other", "DERIVED: no keyword matched (config/intake.py)"


# --- phones, times, payloads -------------------------------------------------------------


def hash_phone(phone: str, key: str) -> str:
    """HMAC-SHA256 of the number in 91XXXXXXXXXX form, so '+91 98...' and '98...' match."""
    digits = re.sub(r"\D", "", phone)
    if len(digits) == 10:
        digits = "91" + digits
    elif len(digits) == 11 and digits.startswith("0"):
        digits = "91" + digits[1:]
    if len(digits) < 8:
        raise ValueError("Phone number is too short")
    return hmac.new(key.encode(), digits.encode(), hashlib.sha256).hexdigest()


def as_utc(value: datetime) -> datetime:
    # SQLite returns naive datetimes; every stored time is UTC.
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _parse_time(value: Any, name: str) -> datetime | None:
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        raise ValueError(f"{name} must be an ISO 8601 time")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{name} must be an ISO 8601 time") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{name} needs a time zone (for example +05:30)")
    return parsed.astimezone(UTC)


def _opt_str(data: Mapping[str, Any], name: str, max_len: int = 64) -> str | None:
    value = data.get(name)
    if value is None or value == "":
        return None
    if not isinstance(value, str) or len(value) > max_len:
        raise ValueError(f"{name} must be text of at most {max_len} characters")
    return value.strip() or None


def _opt_float(data: Mapping[str, Any], *names: str) -> float | None:
    for name in names:
        value = data.get(name)
        if value is None:
            continue
        if isinstance(value, bool) or not isinstance(value, int | float):
            raise ValueError(f"{name} must be a number")
        if not math.isfinite(value):
            raise ValueError(f"{name} must be finite")
        return float(value)
    return None


def _field(payload: Mapping[str, Any], names: Sequence[str]) -> Any:
    lowered = {str(key).lower(): value for key, value in payload.items()}
    return next((lowered[name] for name in names if lowered.get(name) not in (None, "")), None)


@dataclass(frozen=True)
class IntakeItem:
    """One report: P2's IntakeMessage plus what T4 adds. `phone` never leaves memory."""

    message: intake.IntakeMessage
    household_id: str | None = None
    reporter_id: str | None = None
    client_created_at: datetime | None = None
    area_id: str | None = None
    phone: str | None = None


def item_from_json(data: Any, allow_voice: bool = False) -> IntakeItem:
    """Parse and check one app / field-worker / offline item. Raises ValueError if invalid."""
    if not isinstance(data, Mapping):
        raise ValueError("Each item must be a JSON object")
    channel = data.get("channel")
    if not isinstance(channel, str):
        raise ValueError("channel is required")
    lat, lon = _opt_float(data, "lat"), _opt_float(data, "lon", "lng")
    if (lat is None) != (lon is None):
        raise ValueError("lat and lon must be given together")
    if lat is not None and lon is not None and not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise ValueError("lat / lon out of range")
    category = _opt_str(data, "category", 32)
    if category is not None and category not in CATEGORIES:
        raise ValueError(f"Unknown category {category!r}; use one of {sorted(CATEGORIES)}")
    text = data.get("text")
    if text is not None and not isinstance(text, str):
        raise ValueError("text must be text")
    message = intake.IntakeMessage(
        channel=channel,
        text=intake.clean_text(text),
        category=category,
        lat=lat,
        lng=lon,
        language_hint=_opt_str(data, "language_hint", 8),
        client_uuid=_opt_str(data, "client_id"),
        is_synthetic=bool(data.get("is_synthetic", False)),
    )
    intake.validate(message)
    if channel == "voice" and not allow_voice:
        raise ValueError("Voice notes are sent as audio, not JSON")
    item = IntakeItem(
        message=message,
        household_id=_opt_str(data, "household_id"),
        reporter_id=_opt_str(data, "reporter_id"),
        client_created_at=_parse_time(data.get("client_created_at"), "client_created_at"),
        area_id=_opt_str(data, "area_id"),
        phone=_opt_str(data, "phone", 20),
    )
    if channel == "field_worker":
        if item.reporter_id is None:
            raise ValueError("A field-worker report needs reporter_id")
        if item.household_id is None and lat is None:
            raise ValueError("A field-worker report needs household_id or lat / lon")
    return item


# --- voice -------------------------------------------------------------------------------


@dataclass(frozen=True)
class Transcript:
    text: str
    language: str | None
    confidence: float | None  # None when the model does not report one


class TranscriberUnavailable(RuntimeError):
    pass


class Transcriber(Protocol):
    def transcribe(
        self, audio: bytes, content_type: str, language_hint: str | None
    ) -> Transcript | None: ...


class FallbackTranscriber:
    """No speech recognition: the audio is kept and a person writes the transcript."""

    name = "fallback"

    def transcribe(
        self, audio: bytes, content_type: str, language_hint: str | None
    ) -> Transcript | None:
        return None


class IndicConformerTranscriber:
    """AI4Bharat IndicConformer-600M multilingual (docs/research/P3.md F14), `ml` extra.

    Not installed by setup or CI, so this class is not exercised by the tests. The model has no
    published Telugu / Urdu error rate and reports no confidence; it needs the language, so a
    note without a te / hi / ur hint goes to a human.
    """

    name = "indicconformer"
    languages = ("te", "hi", "ur")
    sample_rate = 16_000

    def __init__(self, model_id: str, revision: str | None = None) -> None:
        try:
            import torch
            import torchaudio
            from transformers import AutoModel
        except ImportError as exc:  # the `ml` extra is not installed
            raise TranscriberUnavailable(f"IndicConformer needs the ml extra: {exc}") from exc
        self._torch, self._torchaudio = torch, torchaudio
        self._model = AutoModel.from_pretrained(model_id, revision=revision, trust_remote_code=True)

    def transcribe(
        self, audio: bytes, content_type: str, language_hint: str | None
    ) -> Transcript | None:
        if language_hint not in self.languages:
            return None
        import io

        wav, rate = self._torchaudio.load(io.BytesIO(audio))
        wav = self._torch.mean(wav, dim=0, keepdim=True)
        if rate != self.sample_rate:
            wav = self._torchaudio.functional.resample(wav, rate, self.sample_rate)
        text = str(self._model(wav, language_hint, "ctc")).strip()
        return Transcript(text, language_hint, None) if text else None


def get_transcriber(mode: str | None = None) -> Transcriber:
    """ASR_MODE: fallback, or indicconformer (falls back if the ml extra is missing)."""
    mode = mode or ACCESS_CONFIG.asr_mode
    if mode == "fallback":
        return FallbackTranscriber()
    if mode == "indicconformer":
        try:
            return IndicConformerTranscriber(
                INTAKE_CONFIG.asr_model_id, INTAKE_CONFIG.asr_model_revision
            )
        except TranscriberUnavailable as exc:
            logger.warning("Speech recognition unavailable, using the fallback: %s", exc)
            return FallbackTranscriber()
    raise ValueError(f"ASR_MODE must be 'fallback' or 'indicconformer', got {mode!r}")


class LocalAudioStore:
    """Voice notes on disk, named by their SHA-256 (the same note is stored once)."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    def save(self, audio: bytes, content_type: str) -> str:
        extension = dict(INTAKE_CONFIG.audio_types).get(content_type, ".bin")
        ref = hashlib.sha256(audio).hexdigest() + extension
        self.root.mkdir(parents=True, exist_ok=True)
        path = self.root / ref
        if not path.exists():
            path.write_bytes(audio)
        return ref


@dataclass(frozen=True)
class _Voice:
    audio_ref: str
    content_type: str
    size_bytes: int
    transcriber: str
    transcript: Transcript | None


# --- results and the service -------------------------------------------------------------


class LedgerCall(Protocol):
    """T3's LedgerPort shape; T6's stored ledger fits it."""

    def append(self, entry_type: str, payload: Mapping[str, Any], actor: str) -> Any: ...


@dataclass(frozen=True)
class IntakeResult:
    """Per-item outcome: created | merged | spam | duplicate | invalid."""

    status: str
    client_id: str | None = None
    intake_id: str | None = None
    complaint_id: str | None = None
    complaint_status: str | None = None  # open | awaiting_location | needs_transcription
    parent_id: str | None = None  # duplicate cluster root (T1)
    category: str | None = None
    language: str | None = None
    spam_score: float | None = None
    error: str | None = None
    ledger_seq: int | None = None  # sequence of the ledger entry written for this item


_KEY_FROM_CONFIG = object()


class IntakeService:
    def __init__(
        self,
        engine: Engine,
        sms: SmsSender | None = None,
        transcriber: Transcriber | None = None,
        audio_store: LocalAudioStore | None = None,
        phone_hash_key: str | None | object = _KEY_FROM_CONFIG,
        ledger: LedgerCall | None = None,
        clock: Any = utcnow,
    ) -> None:
        self.engine = engine
        self._sessions = make_session_factory(engine)
        self._sms = sms or get_sms_sender()
        self._transcriber = transcriber or get_transcriber()
        self._audio = audio_store or LocalAudioStore(INTAKE_CONFIG.audio_dir)
        key = INTAKE_CONFIG.phone_hash_key if phone_hash_key is _KEY_FROM_CONFIG else phone_hash_key
        self._phone_key: str | None = key if isinstance(key, str) and key else None
        self._ledger = ledger
        self._clock = clock

    # --- channel adapters ------------------------------------------------------------------

    def receive_json(self, data: Any) -> IntakeResult:
        """App, field-worker or offline item (JSON object)."""
        client_id = data.get("client_id") if isinstance(data, Mapping) else None
        try:
            item = item_from_json(data)
        except ValueError as exc:
            return IntakeResult(
                "invalid", client_id if isinstance(client_id, str) else None, error=str(exc)
            )
        return self.receive(item)

    def receive_batch(self, items: Sequence[Any]) -> list[IntakeResult]:
        """Offline sync: each item on its own, so one bad item does not stop the others."""
        return [self.receive_json(item) for item in items]

    def receive_sms(self, payload: Mapping[str, Any]) -> IntakeResult:
        """SMS webhook, whatever the provider calls its fields."""
        phone, text = _field(payload, SMS_SENDER_FIELDS), _field(payload, SMS_TEXT_FIELDS)
        if not isinstance(phone, str) or not isinstance(text, str) or not text.strip():
            return IntakeResult("invalid", error="SMS payload needs a sender and a text")
        try:  # the gateway's time, kept next to the server time when it carries a zone
            sent_at = _parse_time(_field(payload, SMS_TIME_FIELDS), "timestamp")
        except ValueError:
            sent_at = None
        message = intake.IntakeMessage(channel="sms", text=intake.clean_text(text))
        return self.receive(IntakeItem(message=message, phone=phone, client_created_at=sent_at))

    def receive_missed_call(self, payload: Mapping[str, Any]) -> IntakeResult:
        """Missed call: number and time only; the category is ASSUMED (no water)."""
        phone = _field(payload, CALLER_FIELDS)
        if not isinstance(phone, str):
            return IntakeResult("invalid", error="Missed-call payload needs the caller's number")
        message = intake.IntakeMessage(channel="missed_call")
        return self.receive(IntakeItem(message=message, phone=phone))

    def receive_voice(
        self,
        audio: bytes,
        content_type: str,
        *,
        lat: float | None = None,
        lon: float | None = None,
        language_hint: str | None = None,
        category: str | None = None,
        phone: str | None = None,
        client_id: str | None = None,
        client_created_at: str | None = None,
        household_id: str | None = None,
        reporter_id: str | None = None,
        is_synthetic: bool = False,
    ) -> IntakeResult:
        """Voice note: always stored; transcribed on the server when ASR is available."""
        if not audio:
            return IntakeResult("invalid", client_id, error="Empty audio")
        if len(audio) > INTAKE_CONFIG.max_audio_bytes:
            return IntakeResult("invalid", client_id, error="Audio is too large")
        if content_type not in dict(INTAKE_CONFIG.audio_types):
            return IntakeResult(
                "invalid", client_id, error=f"Unsupported audio type {content_type}"
            )
        data = {
            "channel": "voice",
            "lat": lat,
            "lon": lon,
            "language_hint": language_hint,
            "category": category,
            "phone": phone,
            "client_id": client_id,
            "client_created_at": client_created_at,
            "household_id": household_id,
            "reporter_id": reporter_id,
            "is_synthetic": is_synthetic,
        }
        try:
            item = item_from_json(data, allow_voice=True)
        except ValueError as exc:
            return IntakeResult("invalid", client_id, error=str(exc))
        ref = self._audio.save(audio, content_type)
        try:
            transcript = self._transcriber.transcribe(audio, content_type, language_hint)
        except Exception as exc:  # a failing model must never lose the report
            logger.warning("Transcription failed, keeping the note for a human: %s", exc)
            transcript = None
        if transcript is not None and transcript.text.strip():
            item = replace(item, message=replace(item.message, text=transcript.text.strip()))
        else:
            transcript = None
        name = getattr(self._transcriber, "name", type(self._transcriber).__name__)
        voice = _Voice(ref, content_type, len(audio), name, transcript)
        return self.receive(item, voice)

    # --- the pipeline ----------------------------------------------------------------------

    def receive(self, item: IntakeItem, voice: _Voice | None = None) -> IntakeResult:
        message = item.message
        client_id = message.client_uuid
        phone_hash = None
        if item.phone is not None:
            if self._phone_key is None:
                return IntakeResult(
                    "invalid", client_id, error="PHONE_HASH_KEY is not set; phone reports refused"
                )
            try:
                phone_hash = hash_phone(item.phone, self._phone_key)
            except ValueError as exc:
                return IntakeResult("invalid", client_id, error=str(exc))
        try:
            result = self._store(item, voice, phone_hash)
        except IntegrityError:  # the same client_id arrived twice at the same moment
            existing = self._by_client_id(client_id) if client_id else None
            if existing is None:
                raise
            result = existing
        return self._after(item, result)

    def _by_client_id(self, client_id: str) -> IntakeResult | None:
        with self._sessions() as session:
            row = session.scalars(
                select(IntakeItemRecord).where(IntakeItemRecord.client_id == client_id)
            ).first()
            if row is None:
                return None
            complaint = session.get(Complaint, row.complaint_id) if row.complaint_id else None
            return IntakeResult(
                "duplicate",
                client_id,
                row.id,
                row.complaint_id,
                complaint.status if complaint else None,
                category=complaint.category if complaint else None,
                language=row.language,
                spam_score=row.spam_score,
            )

    def _store(
        self, item: IntakeItem, voice: _Voice | None, phone_hash: str | None
    ) -> IntakeResult:
        message = item.message
        client_id = message.client_uuid
        if client_id:
            existing = self._by_client_id(client_id)
            if existing is not None:
                return existing
        now = as_utc(self._clock())
        with self._sessions() as session, session.begin():
            recent = 0
            if phone_hash:
                since = now - timedelta(minutes=SPAM_CONFIG.burst_window_minutes)
                recent = (
                    session.scalar(
                        select(func.count())
                        .select_from(IntakeItemRecord)
                        .where(
                            IntakeItemRecord.phone_hash == phone_hash,
                            IntakeItemRecord.created_at >= since,
                        )
                    )
                    or 0
                )
            has_location = message.lat is not None
            score, reasons = spam.score(
                spam.SpamSignals(
                    text=message.text,
                    channel=message.channel,
                    has_category_button=message.category is not None,
                    recent_from_same_phone=recent,
                    km_outside_area=None,  # no area boundaries at intake yet
                    phone_registered=message.channel == "field_worker"
                    or INTAKE_CONFIG.phone_registry_available,
                    area_given=has_location
                    or item.area_id is not None
                    or item.household_id is not None,
                )
            )
            language, language_basis = detect_language(message.text, message.language_hint)
            if voice is not None and voice.transcript is not None and voice.transcript.language:
                language, language_basis = voice.transcript.language, "DERIVED: speech recognition"
            record = IntakeItemRecord(
                created_at=now,
                client_id=client_id,
                client_created_at=item.client_created_at,
                channel=message.channel,
                status="spam",
                phone_hash=phone_hash,
                reporter_id=item.reporter_id,
                language=language,
                spam_score=score,
                spam_reasons="; ".join(reasons) or None,
                is_synthetic=message.is_synthetic,
            )
            if spam.is_spam(score):
                record.ledger_missing = self._expects_ledger("spam")
                session.add(record)
                session.flush()
                return IntakeResult(
                    "spam", client_id, record.id, language=language, spam_score=score
                )

            category, category_basis = self._category(message, voice, language)
            if voice is not None and voice.transcript is None:
                status = "needs_transcription"
            elif not has_location and item.household_id is None:
                status = "awaiting_location"
            else:
                status = "open"
            complaint = Complaint(
                created_at=self._report_time(now, item.client_created_at),
                category=category,
                category_basis=category_basis,
                lat=message.lat,
                lon=message.lng,
                household_id=item.household_id,
                text=message.text,
                language=language,
                language_basis=language_basis,
                transcript_confidence=voice.transcript.confidence
                if voice is not None and voice.transcript is not None
                else None,
                needs_human_transcription=status == "needs_transcription",
                reporter_id=item.reporter_id,
                status=status,
                channel=message.channel,
                area_id=item.area_id,
                basis="SYNTHETIC" if message.is_synthetic else "REAL",
            )
            session.add(complaint)
            session.flush()
            parent_id = self._link_duplicate(session, complaint) if status == "open" else None
            record.status = "merged" if parent_id else "created"
            record.ledger_missing = self._expects_ledger(record.status)
            record.complaint_id = complaint.id
            session.add(record)
            if voice is not None:
                session.add(
                    VoiceNote(
                        complaint_id=complaint.id,
                        audio_ref=voice.audio_ref,
                        content_type=voice.content_type,
                        size_bytes=voice.size_bytes,
                        transcriber=voice.transcriber,
                        transcript=voice.transcript.text if voice.transcript else None,
                        confidence=voice.transcript.confidence if voice.transcript else None,
                        needs_human=voice.transcript is None,
                    )
                )
            session.flush()
            return IntakeResult(
                record.status,
                client_id,
                record.id,
                complaint.id,
                status,
                parent_id,
                category,
                language,
                score,
            )

    def _category(
        self, message: intake.IntakeMessage, voice: _Voice | None, language: str | None
    ) -> tuple[str, str]:
        if message.category:
            return message.category, "REPORTED: category button"
        preset = intake.preset_category(message)
        if preset is not None:  # missed call
            return preset, INTAKE_CONFIG.missed_call_category_basis
        if voice is not None and voice.transcript is None:
            return "other", "PENDING: voice note waiting for a human transcript"
        return classify(message.text, language)

    def _report_time(self, now: datetime, client_time: datetime | None) -> datetime:
        if INTAKE_CONFIG.offline_report_time == "client" and client_time is not None:
            oldest = now - timedelta(hours=INTAKE_CONFIG.max_offline_age_hours)
            if oldest <= client_time <= now:
                return client_time
        return now

    def _link_duplicate(self, session: Session, complaint: Complaint) -> str | None:
        """T1 rule against earlier located complaints of the same category; link to the root."""
        rule = dedup.DedupRule.from_config()
        report_time = as_utc(complaint.created_at)
        since = report_time - rule.window_for(complaint.category)
        rows = session.scalars(
            select(Complaint).where(
                Complaint.category == complaint.category,
                Complaint.id != complaint.id,
                Complaint.lat.is_not(None),
                Complaint.status == "open",
                Complaint.created_at >= since,
                Complaint.created_at <= report_time,
            )
        ).all()
        if complaint.lat is None or complaint.lon is None:
            return None
        new = dedup.ComplaintRecord(
            complaint.id,
            complaint.category,
            complaint.lat,
            complaint.lon,
            report_time,
            complaint.household_id,
        )
        existing = [
            dedup.ComplaintRecord(
                row.id, row.category, row.lat, row.lon, as_utc(row.created_at), row.household_id
            )
            for row in rows
            if row.lat is not None and row.lon is not None
        ]
        match = dedup.find_parent(new, existing, rule)
        if match is None:
            return None
        root = session.scalars(
            select(DuplicateLink.parent_id).where(DuplicateLink.child_id == match.parent_id)
        ).first()
        root = root or match.parent_id
        session.add(
            DuplicateLink(
                child_id=complaint.id,
                parent_id=root,
                matched_id=match.parent_id,
                rule=match.rule,
                distance_m=match.distance_m,
                hours_apart=match.hours_apart,
            )
        )
        return root

    # --- after the transaction -------------------------------------------------------------

    def _after(self, item: IntakeItem, result: IntakeResult) -> IntakeResult:
        seq = None
        if result.status in ("created", "merged"):
            if result.complaint_status == "awaiting_location" and item.phone:
                self._sms.send(
                    SmsMessage(
                        to=item.phone,
                        template_key=ASK_LOCATION_TEMPLATE,
                        language=message_language(result.language),
                    )
                )
            seq = self._log(
                result.status,
                {
                    "entity_type": "complaint",
                    "entity_id": result.complaint_id,
                    "intake_id": result.intake_id,
                    "channel": item.message.channel,
                    "category": result.category,
                    "language": result.language,
                    "parent_id": result.parent_id,
                    "complaint_status": result.complaint_status,
                    "is_synthetic": item.message.is_synthetic,
                },
            )
        elif result.status == "spam":
            seq = self._log(
                "spam",
                {
                    "entity_type": "intake_item",
                    "entity_id": result.intake_id,
                    "intake_id": result.intake_id,
                    "channel": item.message.channel,
                    "spam_score": result.spam_score,
                    "is_synthetic": item.message.is_synthetic,
                },
            )
        if seq is None:
            return result
        if result.intake_id:  # written: clear the "ledger entry missing" marker
            with self._sessions() as session, session.begin():
                session.execute(
                    update(IntakeItemRecord)
                    .where(IntakeItemRecord.id == result.intake_id)
                    .values(ledger_missing=False)
                )
        return replace(result, ledger_seq=seq)

    def _expects_ledger(self, kind: str) -> bool:
        return self._ledger is not None and PROPOSED_EVENTS[kind] in ledger.EVENT_TYPES

    def intake_ids_missing_ledger(self) -> list[str]:
        """Items saved without their ledger entry (to log again once the ledger works)."""
        with self._sessions() as session:
            return list(
                session.scalars(
                    select(IntakeItemRecord.id)
                    .where(IntakeItemRecord.ledger_missing.is_(True))
                    .order_by(IntakeItemRecord.created_at)
                )
            )

    def _log(self, kind: str, payload: dict[str, Any]) -> int | None:
        """Write the intake event; a ledger failure is logged and never loses the report."""
        event = PROPOSED_EVENTS[kind]
        if self._ledger is None or event not in ledger.EVENT_TYPES:
            return None
        extra = set(payload) - LEDGER_PAYLOAD_KEYS
        if extra:  # ids, codes and numbers only (never phone numbers, names or free text)
            raise ValueError(f"Ledger payload keys not allowed: {sorted(extra)}")
        try:
            entry = self._ledger.append(event, payload, "intake")
        except Exception:
            logger.exception("Ledger write failed for %s %s", event, payload.get("entity_id"))
            return None
        return getattr(entry, "seq", None)


_default: IntakeService | None = None


def default_service() -> IntakeService:
    """The application's intake (DATABASE_URL, SMS_PROVIDER, ASR_MODE, PHONE_HASH_KEY), logging to
    the stored ledger (T6, LEDGER_HMAC_KEY)."""
    global _default
    if _default is None:
        engine = make_engine()
        create_all(engine)
        _default = IntakeService(engine, ledger=ledger_store.get_ledger())
    return _default
