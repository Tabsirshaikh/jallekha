from dataclasses import dataclass


@dataclass(frozen=True)
class AccessConfig:
    supported_languages: tuple[str, ...] = ("en", "te", "ur", "hi")
    offline_queue_enabled: bool = True


ACCESS_CONFIG = AccessConfig()
