from dataclasses import dataclass


@dataclass(frozen=True)
class AccessConfig:
    # Source: docs/JALLEKHA_FINAL_SOLUTION.md F14 ("Languages: Telugu, Urdu, Hindi, English").
    supported_languages: tuple[str, ...] = ("en", "te", "ur", "hi")
    # Source: docs/JALLEKHA_FINAL_SOLUTION.md F14 ("offline queue, sync later").
    offline_queue_enabled: bool = True


ACCESS_CONFIG = AccessConfig()
