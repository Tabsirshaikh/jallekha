from dataclasses import dataclass, field

from app.config.env import REPO_ROOT, env_str

# Category keyword lists for deterministic tagging (F14, T4; no LLM). Checked in this order, so
# the more specific categories win ("tanker did not come" is tanker_missed, not no_water).
# Basis: ASSUMED, written for this project; there is no published HMWSSB list. OPEN, owner to
# confirm: native speakers should review each list before real use.
CATEGORY_ORDER: tuple[str, ...] = ("tanker_missed", "dirty_water", "leak", "no_water")

KEYWORDS: dict[str, dict[str, tuple[str, ...]]] = {
    "te": {
        "tanker_missed": ("ట్యాంకర్", "టాంకర్"),
        "dirty_water": ("మురికి", "కలుషిత", "బురద"),
        "leak": ("లీక్", "పగిలింది", "లీకేజ్"),
        "no_water": ("నీళ్లు రాలేదు", "నీళ్ళు రాలేదు", "నీరు రాలేదు", "నీళ్లు లేవు", "నీరు లేదు"),
    },
    "hi": {
        "tanker_missed": ("टैंकर", "टेंकर"),
        "dirty_water": ("गंदा", "गन्दा", "मैला"),
        "leak": ("लीक", "रिसाव", "पाइप फट"),
        "no_water": ("पानी नहीं", "पानी नही"),
    },
    "ur": {
        "tanker_missed": ("ٹینکر",),
        "dirty_water": ("گندا", "میلا"),
        "leak": ("لیک", "رساؤ", "پائپ پھٹ"),
        "no_water": ("پانی نہیں",),
    },
    # Latin script: English and romanised Telugu / Hindi (whole words only).
    "en": {
        "tanker_missed": ("tanker",),
        "dirty_water": ("dirty", "muddy", "contaminated", "smelly", "ganda"),
        "leak": ("leak", "leaking", "burst", "pipe broken"),
        "no_water": (
            "no water",
            "water not come",
            "water did not come",
            "no supply",
            "neellu raledu",
            "neeru raledu",
            "neellu levu",
            "pani nahi",
            "paani nahi",
        ),
    },
}

# Payload field names used by different SMS gateways, tried in this order (provider-agnostic).
SMS_SENDER_FIELDS = ("from", "sender", "msisdn", "mobile", "phone", "source")
SMS_TEXT_FIELDS = ("body", "text", "message", "content", "msg")
SMS_TIME_FIELDS = ("timestamp", "received_at", "time", "date")
CALLER_FIELDS = ("caller", "from", "msisdn", "mobile", "phone", "cli")


@dataclass(frozen=True)
class IntakeConfig:
    # S3 review D14 / services/intake.py: a missed call has no text and is read as "no water".
    # Basis: ASSUMED (v1 prototype rule, no HMWSSB source).
    missed_call_category_basis: str = (
        "ASSUMED: missed call read as no_water (v1 prototype rule; S3 review D14)"
    )
    # Latin-script text is tagged "en", although it may be romanised Telugu or Hindi. ASSUMED.
    latin_language: str = "en"
    # OPEN, owner to confirm: which time a synced offline report counts from for duplicates and
    # waiting time. "server" (received time, cannot be faked) or "client" (the phone's time, used
    # only if it is not in the future and not older than max_offline_age_hours). Proposal: server.
    offline_report_time: str = "server"
    max_offline_age_hours: int = 72
    # OPEN, owner to confirm: there is no resident phone registry yet, so app / SMS / voice phones
    # count as unregistered for the spam score (S3 spam rule). Field workers count as registered.
    phone_registry_available: bool = False
    # Environment: PHONE_HASH_KEY. Phone numbers are stored only as HMAC-SHA256 with this key
    # (used for the spam burst count). No default: a report with a phone is refused without it.
    phone_hash_key: str | None = field(
        default_factory=lambda: env_str("PHONE_HASH_KEY"), repr=False
    )
    # Environment: INTAKE_AUDIO_DIR. Where voice notes are kept (git-ignored /uploads/).
    audio_dir: str = field(
        default_factory=lambda: env_str("INTAKE_AUDIO_DIR", str(REPO_ROOT / "uploads" / "audio"))
        or str(REPO_ROOT / "uploads" / "audio")
    )
    # Source: docs/research/P3.md F14 (IndicConformer-600M multilingual: Telugu, Hindi, Urdu;
    # transformers + onnxruntime, no NeMo). Optional `ml` extra. The model loads remote code, so
    # a revision should be pinned: OPEN, owner to confirm which (None = latest).
    asr_model_id: str = "ai4bharat/indic-conformer-600m-multilingual"
    asr_model_revision: str | None = None
    # Technical limits. Basis: ASSUMED.
    max_audio_bytes: int = 10_000_000
    max_batch_items: int = 200
    # Audio types accepted, with the file extension used when storing.
    audio_types: tuple[tuple[str, str], ...] = (
        ("audio/wav", ".wav"),
        ("audio/x-wav", ".wav"),
        ("audio/ogg", ".ogg"),
        ("audio/webm", ".webm"),
        ("audio/mpeg", ".mp3"),
        ("audio/mp4", ".m4a"),
        ("audio/amr", ".amr"),
    )


INTAKE_CONFIG = IntakeConfig()
