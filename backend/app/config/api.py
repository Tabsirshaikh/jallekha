"""T10 API settings. Tokens and keys come from the environment only and are never committed."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import NamedTuple

# Agreed with P4 (docs/api_shapes.md, 2026-10-03): user roles with bearer tokens, plus a separate
# gateway credential for SMS / telephony webhooks. The councillor role (F16: may file contests
# and read what residents read, nothing officer-only) is OPEN, owner to confirm.
ROLES: tuple[str, ...] = ("officer", "driver", "resident", "field_worker", "councillor")

# A token-bound user id starts with a letter, so it can never be a phone number (the same rule
# as a contest's `filed_by`); no colon, as that separates the fields of an `API_TOKENS` pair.
_USER_ID = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{0,63}$")


class ParsedTokens(NamedTuple):
    roles: dict[str, str]  # token -> role
    users: dict[str, str]  # token -> user id (only for tokens that carry one)


def _tokens(raw: str) -> ParsedTokens:
    """`API_TOKENS` = comma-separated `role:token[:user_id]` pairs, e.g.
    `officer:abc,resident:def:resident-demo-01`. The user id is optional. A malformed pair
    (unknown role, empty token, empty or invalid user id) is ignored, so its token is not
    accepted rather than accepted with a wrong identity."""
    roles: dict[str, str] = {}
    users: dict[str, str] = {}
    for pair in raw.split(","):
        parts = pair.strip().split(":")
        if len(parts) not in (2, 3):
            continue
        role, token = parts[0], parts[1]
        if not token or role not in ROLES:
            continue
        if len(parts) == 3:
            if not _USER_ID.match(parts[2]):
                continue
            users[token] = parts[2]
        else:
            users.pop(token, None)  # a later pair for the same token replaces an earlier one
        roles[token] = role
    return ParsedTokens(roles, users)


@dataclass(frozen=True)
class ApiConfig:
    # token -> role. Environment: API_TOKENS. No default: without tokens every protected
    # endpoint answers 401.
    tokens: dict[str, str] = field(default_factory=dict, repr=False)
    # token -> user id, for tokens given as `role:token:user_id` (optional).
    token_users: dict[str, str] = field(default_factory=dict, repr=False)
    # Local development token: accepted for every user role. Environment: API_DEV_TOKEN.
    # Never committed; leave unset outside a developer's machine.
    dev_token: str | None = field(default=None, repr=False)
    # Sign-in. Environment: AUTH_REQUIRED. When the environment variable is unset the running app
    # needs no token: every caller acts as the local "dev" principal (all user roles) and the
    # screens never ask anyone to sign in. AUTH_REQUIRED=true brings the token checks back
    # (API_TOKENS roles and user ids). A config built directly (tests) requires tokens.
    auth_required: bool = True
    # SMS / telephony webhook credential (header X-Gateway-Token). Environment: GATEWAY_TOKEN.
    gateway_token: str | None = field(default=None, repr=False)
    # OTP signing key for delivery proof (T3 takes it as an argument). Environment: OTP_HMAC_KEY.
    otp_key: str | None = field(default=None, repr=False)
    # Frontend origins allowed by CORS. Environment: CORS_ORIGINS (comma-separated). Default:
    # the Vite dev server.
    cors_origins: tuple[str, ...] = ("http://localhost:5173",)
    # Lists: offset / limit / total (agreed with P4). Basis: ASSUMED.
    default_limit: int = 50
    max_limit: int = 200

    @classmethod
    def from_env(cls) -> ApiConfig:
        origins = tuple(
            o.strip() for o in os.environ.get("CORS_ORIGINS", "").split(",") if o.strip()
        )
        parsed = _tokens(os.environ.get("API_TOKENS", ""))
        return cls(
            tokens=parsed.roles,
            token_users=parsed.users,
            auth_required=os.environ.get("AUTH_REQUIRED", "").strip().lower()
            in ("1", "true", "yes"),  # unset: open
            dev_token=os.environ.get("API_DEV_TOKEN") or None,
            gateway_token=os.environ.get("GATEWAY_TOKEN") or None,
            otp_key=os.environ.get("OTP_HMAC_KEY") or None,
            cors_origins=origins or cls.cors_origins,
        )


# Ward SMS summary (F20). PROPOSED English wording, OPEN: native speakers and P4 to review;
# te / ur / hi fall back to English until reviewed (agreed: SMS built server-side, English
# fallback). Parameters are filled from the report card only.
SMS_SUMMARY_TEMPLATES: dict[str, str] = {
    "en": (
        "{ward_name}: {bookings} tanker bookings {period_from} to {period_to}; "
        "need class {service_class}. Deliveries (last {window_days} days): {deliveries}. "
        "Water debt: {debt}. Plan: {schedule}. Ledger head {ledger_head}."
    ),
}
SMS_SUMMARY_TEMPLATE_KEY = "ward.sms_summary"
