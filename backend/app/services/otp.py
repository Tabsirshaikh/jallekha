"""Delivery OTPs (F12). Ported from v1 (S3); the delivery flow that uses them is T3.

The code is HMAC(key, "stop_id:nonce:digits") mod 10^digits, so the same inputs always give
the same code even if the configured length changes later (store the digit count with an
issued OTP and pass it when re-deriving). The plain code is never stored:
only the nonce and sha256(code + stop_id + key) are kept. The server can re-derive the code
to show it to the verified recipient.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime

from app.config.trust import TRUST_CONFIG


def _require(key: str | None) -> str:
    if not key:
        raise ValueError("OTP key is not set")
    return key


def derive_code(key: str | None, stop_id: object, nonce: str, digits: int | None = None) -> str:
    digits = TRUST_CONFIG.otp_digits if digits is None else digits
    if not isinstance(digits, int) or not 1 <= digits <= 12:
        raise ValueError(f"OTP digit count must be 1-12, got {digits}")
    digest = hmac.new(
        _require(key).encode(), f"{stop_id}:{nonce}:{digits}".encode(), hashlib.sha256
    ).hexdigest()
    return f"{int(digest, 16) % (10**digits):0{digits}d}"


def code_hash(key: str | None, code: str, stop_id: object) -> str:
    return hashlib.sha256(f"{code}{stop_id}{_require(key)}".encode()).hexdigest()


def new_nonce() -> str:
    return secrets.token_hex(8)


def check(key: str | None, code: str, stop_id: object, stored_hash: str) -> bool:
    return hmac.compare_digest(code_hash(key, code.strip(), stop_id), stored_hash)


def is_expired(expires_at: datetime, now: datetime) -> bool:
    return now > expires_at
