"""T10 API settings. Tokens and keys come from the environment only and are never committed."""

from __future__ import annotations

import os
from dataclasses import dataclass, field

# Agreed with P4 (docs/api_shapes.md, 2026-10-03): user roles with bearer tokens, plus a separate
# gateway credential for SMS / telephony webhooks. Councillor role: OPEN, owner to confirm.
ROLES: tuple[str, ...] = ("officer", "driver", "resident", "field_worker")


def _tokens(raw: str) -> dict[str, str]:
    """`API_TOKENS` = comma-separated `role:token` pairs, e.g. `officer:abc,driver:def`."""
    out: dict[str, str] = {}
    for pair in raw.split(","):
        role, sep, token = pair.strip().partition(":")
        if sep and token and role in ROLES:
            out[token] = role
    return out


@dataclass(frozen=True)
class ApiConfig:
    # token -> role. Environment: API_TOKENS. No default: without tokens every protected
    # endpoint answers 401.
    tokens: dict[str, str] = field(default_factory=dict, repr=False)
    # Local development token: accepted for every user role. Environment: API_DEV_TOKEN.
    # Never committed; leave unset outside a developer's machine.
    dev_token: str | None = field(default=None, repr=False)
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
        return cls(
            tokens=_tokens(os.environ.get("API_TOKENS", "")),
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
        "need class {service_class}. Deliveries, water debt and schedule not available yet. "
        "Ledger head {ledger_head}."
    ),
}
SMS_SUMMARY_TEMPLATE_KEY = "ward.sms_summary"
