"""Outbound SMS, provider-agnostic (F12 delivery proof; F14 intake can reuse it).

Messages carry a template key, the recipient's language and parameters, never finished
text: the wording per language lives with the localisation work (P4), so this code holds no
hand-typed messages. Only the fake provider exists (`SMS_PROVIDER=fake`, config/access.py).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Protocol

from app.config.access import ACCESS_CONFIG


@dataclass(frozen=True)
class SmsMessage:
    to: str
    template_key: str
    language: str
    params: Mapping[str, str] = field(default_factory=dict)


class SmsSender(Protocol):
    def send(self, message: SmsMessage) -> None: ...


class FakeSmsSender:
    """Keeps sent messages in memory, for tests and the demo. Sends nothing."""

    def __init__(self) -> None:
        self.sent: list[SmsMessage] = []

    def send(self, message: SmsMessage) -> None:
        self.sent.append(message)


def message_language(language: str | None) -> str:
    """The recipient's language if supported, else the first supported language."""
    supported = ACCESS_CONFIG.supported_languages
    return language if language in supported else supported[0]


def get_sms_sender() -> SmsSender:
    if ACCESS_CONFIG.sms_provider == "fake":
        return FakeSmsSender()
    raise ValueError(f"No SMS provider {ACCESS_CONFIG.sms_provider!r}")
