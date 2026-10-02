from dataclasses import dataclass, field

from app.config.env import env_str


@dataclass(frozen=True)
class TrustConfig:
    # Source: docs/JALLEKHA_FINAL_SOLUTION.md F12 ("server-side geofence (150 m)").
    geofence_radius_metres: int = 150
    # Upper bound for a per-stop radius override. Ported from v1 config (S3). Basis: ASSUMED.
    geofence_max_radius_metres: int = 300
    # --- F12 delivery OTP (S3 functions, T3 flow). Decision (a) is OPEN, owner to confirm. ---
    # Source: OPEN, owner to confirm. Proposal: 6 digits (NIST SP 800-63B v4 section 3.1.3.2,
    # "at least six decimal digits"; a reference point, not a rule). Was 4, ported from v1
    # (ASSUMED). See docs/reviews/S3-review.md D12.
    otp_digits: int = 6
    # Source: OPEN, owner to confirm. Proposal: 3 wrong tries per stop visit, counted across
    # reissued OTPs (a new OTP does not reset the count). Ported from v1 (ASSUMED).
    otp_max_attempts: int = 3
    # Source: OPEN, owner to confirm. Proposal: 10 minutes (NIST SP 800-63B v4 section 3.1.3.2,
    # "within 10 minutes").
    otp_valid_minutes: int = 10
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

    # --- F12 delivery proof (T3) ---
    # Source: F12 ("OTP to one of 2-3 registered representatives per stop").
    delivery_representatives_min: int = 2
    delivery_representatives_max: int = 3
    # Source: F12 ("then 3-5 random residents get 'Did you get water? 1 yes / 2 no'").
    delivery_residents_min: int = 3
    delivery_residents_max: int = 5
    # Decision (b) is OPEN, owner to confirm. Silence counts for nothing (F12): only replies
    # are counted. Proposal (docs/P3_BUILD_PLAN.md T3 step 4): "mostly yes" means yes exceeds
    # no by at least this margin among replies (1 = strictly more yes than no); "mostly no"
    # likewise. A tie or zero replies is no majority.
    delivery_majority_margin: int = 1
    # Source: OPEN, owner to confirm (decision b). With no majority the outcome waits until
    # the reply window closes (or every sampled resident has replied), then falls back to the
    # OTP alone: verified -> Unconfirmed, not verified -> Failed. 120 minutes is a proposal.
    delivery_reply_window_minutes: int = 120
    delivery_no_majority_outcome: tuple[tuple[bool, str], ...] = (
        (True, "Unconfirmed"),
        (False, "Failed"),
    )


TRUST_CONFIG = TrustConfig()
