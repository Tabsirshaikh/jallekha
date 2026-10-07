"""Stops of an approved plan that a driver marked visited in local test mode (SIMULATION).

After unloading, the driver types the code of each of ROUTE_VISIT_CONFIG.residents_per_stop
residents; in this simulation every code is the fixed one in the config (no SMS, no OTP). A visit
counts only when every code is right, and the first time it counts is kept. Visits live in server
memory per (plan, tanker): a restart clears them, they are never water debt and never on the
ledger. The real delivery proof for a booking made through JalLekha stays the F12 code flow.
"""

from __future__ import annotations

import threading
from collections import defaultdict
from datetime import datetime

from app.config.route_visits import ROUTE_VISIT_CONFIG as CFG

BASIS = "SIMULATION"


def check_codes(codes: list[str]) -> list[bool]:
    """One answer per resident: did they give the code? Missing codes are wrong."""
    given = [str(c).strip() for c in codes][: CFG.residents_per_stop]
    given += [""] * (CFG.residents_per_stop - len(given))
    return [c == CFG.code for c in given]


class RouteVisitStore:
    """When each trip of a tanker in a plan was first confirmed (in memory)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._visits: dict[tuple[str, str], dict[int, datetime]] = defaultdict(dict)

    def visit(self, plan_id: str, tanker_id: str, n: int, at: datetime) -> datetime:
        with self._lock:
            return self._visits[(plan_id, tanker_id)].setdefault(n, at)

    def visits(self, plan_id: str, tanker_id: str) -> dict[int, datetime]:
        with self._lock:
            return dict(self._visits.get((plan_id, tanker_id), {}))

    def of_plan(self, plan_id: str) -> list[tuple[str, int, datetime]]:
        with self._lock:
            return sorted(
                (tanker, n, at)
                for (plan, tanker), trips in self._visits.items()
                if plan == plan_id
                for n, at in trips.items()
            )
