"""A7 planner replay for P3's T9 (F17): the real daily planner run on the A8 replay.

Usage:
    python scripts/sandbox/build_planner_replay.py

Replays Mar-Jul 2025 (seed 0; monthly totals REAL, daily arrivals SYNTHETIC) through
services/planner.build_plan with A8's tight capacity (B1 = 90%, the REAL Jun-Aug 2026 level),
3 km station sharing and the scheduled reserve. Unserved bookings wait up to
booking_expiry_days, then count as expired. No outages are replayed, debt is not settled
(deliveries are not simulated) and no fleet is given, so scheduled needs are listed as
unrouted.

Outputs (SIMULATION):
- data/derived/planner_replay/days.csv: one row per day (trips, reserve, served, waiting,
  expired, trips lent, flagged groups, plan digest);
- data/derived/planner_replay/groups.csv: one row per day and group with pending bookings
  (pending, served, served by a lent trip, waiting, entitlement, and the quality signals T9
  scores: need basis CENSUS_2011 or FALLBACK_MEDIAN, location status, flag).

For T9: `replay(setup, entitlement=..., fallback_groups=...)` re-runs the same days with a
degraded signal; compare each day's plan with the full-information plan (same digest = same
decisions).
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import statistics
import sys
from collections import Counter
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import build_sandbox  # noqa: E402

from app.config.sandbox import SANDBOX_CONFIG  # noqa: E402
from app.services import (  # noqa: E402
    booking_groups,
    fair_queue,
    planner,
    sandbox,
    service_models,
)
from app.services.ledger_port import InMemoryLedger  # noqa: E402
from app.services.replay import IST  # noqa: E402

DAYS = "data/derived/planner_replay/days.csv"
GROUPS = "data/derived/planner_replay/groups.csv"
CHECKS = "data/verification/planner_replay_checks.json"
REPLAY, SCENARIO, SEED = "main_2025", "tight", 0
LABEL = "SIMULATION"
REPLAY_LEDGER_KEY = "planner-replay-simulation"  # in-memory only, never a real key


@dataclass(frozen=True)
class Setup:
    ctx: build_sandbox.Context
    capacity: dict[str, int]
    bookings: list[sandbox.SimBooking]
    fallback_groups: frozenset[str]
    location_status: dict[str, str]  # group -> PLACED_IN_WARD or the crosswalk status
    start: date


@dataclass(frozen=True)
class DayResult:
    index: int
    day: date
    inputs: planner.PlanInputs
    plan: planner.DailyPlan
    expired: tuple[str, ...]


def load(root: Path = ROOT) -> Setup:
    ctx = build_sandbox.load_context(root)
    checks = json.loads((root / build_sandbox.CHECKS).read_text(encoding="utf-8"))
    capacity = checks["capacities"][REPLAY][SCENARIO]
    months = build_sandbox.REPLAYS[REPLAY]
    bookings, _ = build_sandbox.bookings_for(ctx, months, SEED)
    needs = service_models.build_ward_needs(service_models.load_evidence(root), [])
    _, fallback = booking_groups.group_entitlements(needs, ctx.mapping)
    status = {}
    for section, link in ctx.mapping.items():
        group = booking_groups.group_for(section, ctx.mapping)
        status[group] = "PLACED_IN_WARD" if link.ward_id else link.status
    return Setup(ctx, capacity, bookings, frozenset(fallback), status, date(*months[0], 1))


def fallback_value(setup: Setup) -> float:
    """The A3 fallback entitlement (median ward entitlement)."""
    wards = [v for g, v in setup.ctx.entitlement.items() if g not in setup.fallback_groups]
    return statistics.median(wards)


def replay(
    setup: Setup,
    max_days: int | None = None,
    entitlement: Mapping[str, float] | None = None,
    fallback_groups: frozenset[str] | None = None,
) -> Iterator[DayResult]:
    """Run the planner day by day; pending bookings carry over until they expire."""
    ctx = setup.ctx
    entitlement = dict(entitlement or ctx.entitlement)
    gate = planner.ProvisionalGate(
        setup.fallback_groups if fallback_groups is None else fallback_groups
    )
    ledger = InMemoryLedger(key=REPLAY_LEDGER_KEY)
    expiry = SANDBOX_CONFIG.booking_expiry_days
    days = build_sandbox._days_in(build_sandbox.REPLAYS[REPLAY])
    days = days if max_days is None else min(days, max_days)
    arriving: dict[int, list[sandbox.SimBooking]] = {}
    for b in setup.bookings:
        arriving.setdefault(b.day, []).append(b)
    pending: list[sandbox.SimBooking] = []
    states: dict[str, fair_queue.QueueState] = {}
    for index in range(days):
        day = setup.start + timedelta(days=index)
        expired = tuple(b.booking_id for b in pending if index - b.day >= expiry)
        pending = [b for b in pending if index - b.day < expiry] + arriving.get(index, [])
        inputs = planner.PlanInputs(
            plan_id=f"replay-{day.isoformat()}",
            day=day,
            capacity=setup.capacity,
            pending=[
                planner.PlannerBooking(sandbox.queue_booking(b), ctx.network.home[b.section])
                for b in pending
            ],
            entitlement=entitlement,
            queue_states=states,
            scheduled=ctx.scheduled,
            station_km=ctx.network.station_km,
        )
        plan = planner.build_plan(inputs, gate, ledger, planner_now(day))
        served = {s.booking_id for p in plan.stations.values() for s in p.served}
        pending = [b for b in pending if b.booking_id not in served]
        states = plan.queue_states
        yield DayResult(index, day, inputs, plan, expired)


def planner_now(day: date) -> datetime:
    """Plans are made at 05:00 local time on their day."""
    return datetime(day.year, day.month, day.day, 5, 0, tzinfo=IST)


def _csv(rows: list[dict[str, Any]]) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode()


def build(root: Path = ROOT) -> dict[str, bytes]:
    setup = load(root)
    day_rows, group_rows = [], []
    for result in replay(setup):
        plan = result.plan
        pending = Counter(p.booking.group for p in result.inputs.pending)
        served = Counter(s.group for p in plan.stations.values() for s in p.served)
        lent = Counter(s.group for p in plan.stations.values() for s in p.served if s.lender)
        day_rows.append(
            {
                "day": result.day.isoformat(),
                "trips": sum(setup.capacity.values()),
                "reserve_trips": plan.reserve_trips,
                "booked_served": sum(served.values()),
                "booked_waiting": sum(len(p.waiting) for p in plan.stations.values()),
                "expired_before_planning": len(result.expired),
                "trips_lent": sum(t.trips for t in plan.transfers),
                "flagged_groups": len(plan.flags),
                "digest": plan.digest,
                "label": LABEL,
            }
        )
        for group in sorted(pending):
            group_rows.append(
                {
                    "day": result.day.isoformat(),
                    "group": group,
                    "pending": pending[group],
                    "served": served[group],
                    "served_by_lent_trip": lent[group],
                    "waiting": pending[group] - served[group],
                    "entitlement": round(result.inputs.entitlement[group], 6),
                    "effective_entitlement": round(plan.effective_entitlement[group], 6),
                    "need_basis": "FALLBACK_MEDIAN"
                    if group in setup.fallback_groups
                    else "CENSUS_2011",
                    "location_status": setup.location_status.get(group, "UNKNOWN"),
                    "flagged": int(group in plan.flags),
                    "label": LABEL,
                }
            )
    artifacts = {DAYS: _csv(day_rows), GROUPS: _csv(group_rows)}
    checks = {
        "replay": REPLAY,
        "scenario": SCENARIO,
        "seed": SEED,
        "days": len(day_rows),
        "inputs_sha256": {
            build_sandbox.CHECKS: hashlib.sha256(
                (root / build_sandbox.CHECKS).read_bytes()
            ).hexdigest()
        },
        "outputs_sha256": {p: hashlib.sha256(c).hexdigest() for p, c in artifacts.items()},
    }
    artifacts[CHECKS] = (json.dumps(checks, indent=2, sort_keys=True) + "\n").encode()
    return artifacts


if __name__ == "__main__":
    for name, content in build().items():
        path = ROOT / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    print("A7 planner replay built (SIMULATION).")
