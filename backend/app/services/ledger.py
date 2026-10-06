"""Tamper-evident hash-chained ledger (F18). Pure core ported from v1 (S3).

hash      = sha256(canonical JSON of every stored field except hash and signature)
signature = HMAC_SHA256(key, hash)

Every field of LedgerEntry (seq, prev_hash, event_type, entity_type, entity_id, payload,
created_at_iso, and any field added later) is part of the hash, so editing any of them is
detected. NaN and Infinity are rejected because they are not valid JSON.

The first entry uses prev_hash = "GENESIS". Payloads hold ids and numbers only (no personal
data). Storage, locking and wiring to other features are T6; T6 may extend EVENT_TYPES.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import asdict, dataclass, replace
from typing import Any

GENESIS = "GENESIS"
EVENT_TYPES = frozenset(
    {
        "ledger_initialized",
        "plan_created",
        "plan_approved",
        "plan_dispatched",
        "plan_replanned",
        "override",
        "otp_issued",
        "delivery_verified",
        "delivery_failed",
        "water_debt_changed",
        # A6 on stored plans: an officer closes a day, settling every ward's debt (F11, F20)
        "debt_day_closed",
        "station_paused",
        "station_resumed",
        "weights_changed",
        "issue_status_changed",
        "ward_reviewed",
        # T3 delivery proof (F12)
        "delivery_started",
        "geofence_checked",
        "otp_attempted",
        "residents_sampled",
        "resident_replied",
        "delivery_outcome",
        "outside_tries_exceeded",
        # A4 scheduled supply (F9)
        "service_point_registered",
        # A5 outage response (F10)
        "outage_created",
        # T6: other modules (plan, override, weights and debt use the types above; outages use
        # A5's outage_created)
        "notice_published",  # T5 supply notice (F15)
        "contest_filed",  # T7 contest (F16)
        "contest_replied",  # T7 officer reply (F16)
        "field_check_recorded",  # field check
        "section_check_recorded",  # exact-section booking-access observation, note digest only
        # T4 intake (F14): ids, codes and numbers only in payloads
        "complaint_received",
        "complaint_merged",
        "complaint_marked_spam",
    }
)


@dataclass(frozen=True)
class LedgerEntry:
    seq: int
    event_type: str
    entity_type: str
    entity_id: str
    payload: dict[str, Any]
    prev_hash: str
    hash: str
    signature: str
    created_at_iso: str


def canonical_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Normalise to JSON-native types so the stored payload re-hashes identically."""
    return json.loads(json.dumps(payload, default=str, allow_nan=False))


def payload_json(payload: dict[str, Any]) -> str:
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    )


def entry_hash(entry: LedgerEntry) -> str:
    """sha256 over every stored field except the hash and signature themselves."""
    content = {k: v for k, v in asdict(entry).items() if k not in ("hash", "signature")}
    return hashlib.sha256(payload_json(content).encode("utf-8")).hexdigest()


def sign(hash_hex: str, key: str | None) -> str:
    if not key:
        raise ValueError("Ledger HMAC key is not set (LEDGER_HMAC_KEY)")
    return hmac.new(key.encode(), hash_hex.encode(), hashlib.sha256).hexdigest()


def next_entry(
    last: LedgerEntry | None,
    event_type: str,
    entity_type: str,
    entity_id: Any,
    payload: dict[str, Any] | None,
    created_at_iso: str,
    key: str | None,
) -> LedgerEntry:
    """Build the entry that follows `last` (None for the first entry). The caller stores it."""
    if event_type not in EVENT_TYPES:
        raise ValueError(f"Unknown ledger event type: {event_type}")
    unsigned = LedgerEntry(
        seq=(last.seq + 1) if last else 1,
        event_type=event_type,
        entity_type=entity_type,
        entity_id=str(entity_id),
        payload=canonical_payload(payload or {}),
        prev_hash=last.hash if last else GENESIS,
        hash="",
        signature="",
        created_at_iso=created_at_iso,
    )
    digest = entry_hash(unsigned)
    return replace(unsigned, hash=digest, signature=sign(digest, key))


def verify_entries(entries: list[LedgerEntry], key: str | None) -> dict[str, Any]:
    """Check every link and signature in order; report the first broken entry."""
    prev_hash = GENESIS
    for position, entry in enumerate(entries, start=1):
        try:
            expected = entry_hash(entry)
        except (TypeError, ValueError):  # a stored payload that is not valid JSON
            expected = None
        if entry.seq != position or entry.prev_hash != prev_hash or entry.hash != expected:
            return {
                "valid": False,
                "broken_at": entry.seq,
                "reason": "hash_mismatch",
                "checked": entry.seq,
            }
        if not hmac.compare_digest(entry.signature, sign(entry.hash, key)):
            return {
                "valid": False,
                "broken_at": entry.seq,
                "reason": "signature_mismatch",
                "checked": entry.seq,
            }
        prev_hash = entry.hash
    return {"valid": True, "broken_at": None, "checked": len(entries), "head": prev_hash}
