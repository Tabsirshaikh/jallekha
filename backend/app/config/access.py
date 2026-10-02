from dataclasses import dataclass, field

from app.config.env import env_str

ASR_MODES = ("fallback", "indicconformer")
SMS_PROVIDERS = ("fake",)


@dataclass(frozen=True)
class AccessConfig:
    # Source: docs/JALLEKHA_FINAL_SOLUTION.md F14 ("Languages: Telugu, Urdu, Hindi, English").
    supported_languages: tuple[str, ...] = ("en", "te", "ur", "hi")
    # Source: docs/JALLEKHA_FINAL_SOLUTION.md F14 ("offline queue, sync later").
    offline_queue_enabled: bool = True
    # Environment: ASR_MODE. Source: F14 (IndicConformer on the server; "fallback: voice note
    # saved for a human"). Default fallback so setup needs no ML install.
    asr_mode: str = field(default_factory=lambda: env_str("ASR_MODE", "fallback"))
    # Environment: SMS_PROVIDER. Only the fake (log-only) provider exists until T3/T4.
    sms_provider: str = field(default_factory=lambda: env_str("SMS_PROVIDER", "fake"))

    def __post_init__(self) -> None:
        if self.asr_mode not in ASR_MODES:
            raise ValueError(f"ASR_MODE must be one of {ASR_MODES}, got {self.asr_mode!r}")
        if self.sms_provider not in SMS_PROVIDERS:
            raise ValueError(
                f"SMS_PROVIDER must be one of {SMS_PROVIDERS}, got {self.sms_provider!r}"
            )


ACCESS_CONFIG = AccessConfig()
