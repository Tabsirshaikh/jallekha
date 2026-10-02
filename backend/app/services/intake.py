"""Intake checks that do not need the database (F14). Ported from v1 (S3).

The full pipeline (area lookup, language, tagging, spam, duplicates, storage) is T4; it builds
on these checks. Channels follow the solution document: app, voice, SMS, missed call,
field worker.
"""

from __future__ import annotations

from dataclasses import dataclass

CHANNELS = frozenset({"app", "voice", "sms", "missed_call", "field_worker"})


@dataclass(frozen=True)
class IntakeMessage:
    channel: str
    text: str | None = None
    category: str | None = None  # chosen with a category button
    lat: float | None = None
    lng: float | None = None
    language_hint: str | None = None
    client_uuid: str | None = None  # set by offline clients so a re-sent report is not doubled
    phone_hash: str | None = None
    is_synthetic: bool = False


def validate(message: IntakeMessage) -> None:
    if message.channel not in CHANNELS:
        raise ValueError(f"Unknown channel: {message.channel}")


def clean_text(text: str | None) -> str | None:
    cleaned = (text or "").strip()
    return cleaned or None


def preset_category(message: IntakeMessage) -> str | None:
    """Category known without reading the text: a button choice, or a missed call (no water).
    None means the text must be tagged."""
    if message.category:
        return message.category
    if message.channel == "missed_call":
        # ASSUMED: a missed call carries no text, so it is read as "no water" (the v1
        # prototype's rule). No HMWSSB source; T4 may replace it with an IVR menu choice.
        return "no_water"
    return None
