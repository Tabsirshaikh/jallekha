"""Spam score for incoming reports (F14). Ported from v1 (S3).

Score 0-1; spam when it reaches the threshold. Spam is kept and marked, never deleted.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass

from app.config.spam import SPAM_CONFIG


@dataclass(frozen=True)
class SpamSignals:
    text: str | None
    channel: str
    has_category_button: bool
    recent_from_same_phone: int  # reports from this phone in the burst window, excluding this one
    km_outside_area: float | None  # None when the report has no location
    phone_registered: bool
    area_given: bool


def non_letter_ratio(text: str) -> float:
    """Share of non-space characters that are not letters. Combining marks (Indic vowel signs)
    count as letters."""
    chars = [ch for ch in text if not ch.isspace()]
    if not chars:
        return 0.0
    letters = sum(1 for ch in chars if unicodedata.category(ch)[0] in ("L", "M"))
    return 1 - letters / len(chars)


def score(signals: SpamSignals) -> tuple[float, list[str]]:
    cfg = SPAM_CONFIG
    total = 0.0
    reasons: list[str] = []
    text = (signals.text or "").strip()

    if signals.recent_from_same_phone + 1 > cfg.burst_max_complaints:
        total += cfg.burst_points
        reasons.append(
            f"More than {cfg.burst_max_complaints} reports from the same phone within "
            f"{cfg.burst_window_minutes} minutes"
        )
    needs_text = signals.channel not in ("voice", "missed_call") and not signals.has_category_button
    if needs_text and len(text) < cfg.short_text_min_chars:
        total += cfg.short_text_points
        reasons.append("Empty or very short text with no category chosen")
    if signals.km_outside_area is not None and signals.km_outside_area > cfg.outside_area_km:
        total += cfg.outside_area_points
        reasons.append(f"Location {signals.km_outside_area:.1f} km outside the claimed area")
    if text and non_letter_ratio(text) > cfg.gibberish_nonletter_ratio:
        total += cfg.gibberish_points
        reasons.append("Text looks like gibberish")
    if not signals.phone_registered and not signals.area_given:
        total += cfg.unregistered_points
        reasons.append("Unregistered phone and no area given")

    return round(min(1.0, total), 3), reasons


def is_spam(value: float) -> bool:
    return value >= SPAM_CONFIG.threshold
