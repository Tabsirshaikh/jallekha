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
    # Source: OPEN, owner to confirm. OTP tries from outside the geofence per stop visit that
    # are written to the ledger. They never use up an attempt and reveal nothing about the code;
    # the cap only stops ledger flooding. Try cap+1 writes one outside_tries_exceeded entry,
    # later tries write nothing. 10 is a proposal.
    outside_tries_max: int = 10
    # No source in docs/JALLEKHA_FINAL_SOLUTION.md. Related rule, F11: only Confirmed
    # deliveries (F12) count. Meaning and value to be decided in T3 / A6.
    unresolved_delivery_changes_shortfall: bool = False
    # Environment: LEDGER_HMAC_KEY (F18 "SHA-256 hash chain with HMAC"). No default: the
    # ledger must refuse to write without a key. Hidden from repr so it is never logged.
    ledger_hmac_key: str | None = field(
        default_factory=lambda: env_str("LEDGER_HMAC_KEY"), repr=False
    )
    # --- F18 stored ledger (T6) ---
    # Environment: LEDGER_KEY_ID, the id of LEDGER_HMAC_KEY. Source: F18 and docs/research/P3.md
    # F18 ("key_id per entry for key rotation"). Each entry records the key id it was signed with.
    ledger_key_id: str = field(default_factory=lambda: env_str("LEDGER_KEY_ID", "k1") or "k1")
    # Environment: LEDGER_OLD_HMAC_KEYS, "id:key,id:key" for retired keys, so entries signed
    # before a rotation still verify. Hidden from repr.
    ledger_old_hmac_keys: str | None = field(
        default_factory=lambda: env_str("LEDGER_OLD_HMAC_KEYS"), repr=False
    )
    # Source: OPEN, owner to confirm. How often the HMAC key is rotated. The research note
    # decides key ids and rotation, not the period; 90 days is a proposal. Not enforced in code.
    ledger_key_rotation_days: int = 90
    # Source: F18 ("the head hash is published daily"). The day boundary and publish time are
    # OPEN, owner to confirm: proposal = Hyderabad local day (UTC+05:30, minutes below) and
    # publishing at 06:00 local, before the day's plan. Channel (ward report card / SMS) is P4/T5.
    ledger_head_utc_offset_minutes: int = 330
    ledger_head_publish_time_local: str = "06:00"
    # Retries when two writers take the same sequence number at once. Technical, ASSUMED.
    ledger_append_retries: int = 20

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

    def ledger_keyring(self) -> dict[str, str]:
        """Current key (by LEDGER_KEY_ID) plus retired keys; empty when no key is set."""
        keys: dict[str, str] = {}
        if self.ledger_hmac_key:
            keys[self.ledger_key_id] = self.ledger_hmac_key
        for item in (self.ledger_old_hmac_keys or "").split(","):
            if not item.strip():
                continue
            key_id, sep, secret = item.strip().partition(":")
            if not sep or not key_id.strip() or not secret.strip():
                raise ValueError("LEDGER_OLD_HMAC_KEYS must look like 'id:key,id:key'")
            keys.setdefault(key_id.strip(), secret.strip())
        return keys


TRUST_CONFIG = TrustConfig()
