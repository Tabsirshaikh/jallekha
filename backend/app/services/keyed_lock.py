"""One lock per key (a plan id, a delivery id) for a read, change, save sequence.

Inside one process this makes the sequence atomic, so a change and its ledger entry are never
half-applied. Across processes the stored version still refuses a stale write (409).
"""

from __future__ import annotations

import threading
from collections.abc import Iterator
from contextlib import contextmanager


class KeyedLocks:
    def __init__(self) -> None:
        self._guard = threading.Lock()
        self._locks: dict[str, threading.Lock] = {}

    @contextmanager
    def hold(self, key: str) -> Iterator[None]:
        with self._guard:
            lock = self._locks.setdefault(key, threading.Lock())
        with lock:
            yield
