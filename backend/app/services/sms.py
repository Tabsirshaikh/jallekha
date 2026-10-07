"""Outbound SMS, provider-agnostic (F12 delivery proof; F14 intake can reuse it).

Messages carry a template key, the recipient's language and parameters, never finished
text: the wording per language lives with the localisation work (P4), so this code holds no
hand-typed messages. No real provider exists yet (an owner decision: which SMS company, keys in
the environment). `SMS_PROVIDER=fake` keeps nothing (tests); `SMS_PROVIDER=outbox` is a test mode
that keeps the last messages in the server's memory so a tester can read a delivery code and
answer "did you get water?" on the screen (routers/sms_outbox.py). Nothing leaves the machine.
"""

from __future__ import annotations

import threading
from collections import deque
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
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


@dataclass(frozen=True)
class OutboxEntry:
    at: datetime
    message: SmsMessage


class OutboxSmsSender:
    """Test mode: keeps the last `size` messages in memory, newest last. Sends nothing."""

    def __init__(self, size: int = 500) -> None:
        self._entries: deque[OutboxEntry] = deque(maxlen=size)
        self._lock = threading.Lock()

    def send(self, message: SmsMessage) -> None:
        with self._lock:
            self._entries.append(OutboxEntry(datetime.now(UTC), message))

    def to(self, phone_key: str, key: object) -> list[OutboxEntry]:
        """Messages whose number's key (last 10 digits, via `key`) equals `phone_key`."""
        with self._lock:
            return [e for e in self._entries if key(e.message.to) == phone_key]  # type: ignore[operator]


_OUTBOX = OutboxSmsSender()


def outbox() -> OutboxSmsSender | None:
    """The test-mode outbox, or None when SMS_PROVIDER is not `outbox`."""
    return _OUTBOX if ACCESS_CONFIG.sms_provider == "outbox" else None


def get_sms_sender() -> SmsSender:
    if ACCESS_CONFIG.sms_provider == "fake":
        return FakeSmsSender()
    if ACCESS_CONFIG.sms_provider == "outbox":
        return _OUTBOX
    raise ValueError(f"No SMS provider {ACCESS_CONFIG.sms_provider!r}")
