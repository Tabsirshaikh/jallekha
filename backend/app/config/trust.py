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

    # --- F13 duplicate engine (T1) ---
    # Source: F13 ("Rule: 100 m radius"), calibrated on Chicago duplicates ("95% within 106 m").
    dedup_radius_metres: float = 100.0
    # Source: F13 ("48 h window for no-water / tanker-missed / dirty water, 7 days for leaks
    # and other"); calibration: "no-water duplicates 90% within 20 h; leaks 90% within about
    # 9 days". Categories outside this table are rejected. Stored as (category, hours) pairs so
    # the config stays immutable, hashable and copyable; read it with dict(...).
    dedup_window_hours: tuple[tuple[str, int], ...] = (
        ("no_water", 48),
        ("tanker_missed", 48),
        ("dirty_water", 48),
        ("leak", 168),
        ("other", 168),
    )
    # Source: F13 (multilingual sentence embeddings, "secondary signal, marked untested on
    # Indian data") and docs/research/P3.md (LaBSE covers Telugu, Urdu, Hindi, English).
    # Off by default; never decides a merge on its own.
    dedup_text_similarity_enabled: bool = False
    dedup_text_model: str = "sentence-transformers/LaBSE"


TRUST_CONFIG = TrustConfig()
