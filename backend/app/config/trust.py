from dataclasses import dataclass, field

from app.config.env import env_str


@dataclass(frozen=True)
class TrustConfig:
    # Source: docs/JALLEKHA_FINAL_SOLUTION.md F12 ("server-side geofence (150 m)").
    geofence_radius_metres: int = 150
    # Upper bound for a per-stop radius override. Ported from v1 config (S3). Basis: ASSUMED.
    geofence_max_radius_metres: int = 300
    # Delivery OTP length and wrong tries allowed. Ported from v1 config (S3). Basis: ASSUMED.
    otp_digits: int = 4
    otp_max_attempts: int = 3
    # No source in docs/JALLEKHA_FINAL_SOLUTION.md. Related rule, F11: only Confirmed
    # deliveries (F12) count. Meaning and value to be decided in T3 / A6.
    unresolved_delivery_changes_shortfall: bool = False
    # Environment: LEDGER_HMAC_KEY (F18 "SHA-256 hash chain with HMAC"). No default: the
    # ledger must refuse to write without a key. Hidden from repr so it is never logged.
    ledger_hmac_key: str | None = field(
        default_factory=lambda: env_str("LEDGER_HMAC_KEY"), repr=False
    )


TRUST_CONFIG = TrustConfig()
