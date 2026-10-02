"""Outage response (A5, F10): sudden loss of piped supply.

- create_outage is the single way to record an outage (area = 2016 wards, start, end, source,
  reason). Sources: "complaints" (a confirmed candidate), "notice" (T5 supply-notice feed) and
  "officer". Every outage is a ledger entry.
- detect_from_complaints proposes candidates: a ward with at least N distinct "no water"
  reports (T1 duplicate links removed) in the recent window. An officer confirms them.
- plan_response: critical facilities first (tier 0), then every outage area up to the floor
  (10 lpcd) in priority order, then top-ups to the target (15 lpcd). Priority is the
  deprivation weight exp(hours cut off / tau), which rises faster the longer people wait.
- Outage water never counts toward water debt (F11 debt is for booked/entitled service).
"""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.config.allocation import ALLOCATION_CONFIG
from app.services import dedup

SOURCES = ("complaints", "notice", "officer")
OUTAGE_CATEGORIES = ("no_water",)
EPSILON = 1e-6


@dataclass(frozen=True)
class OutageEvent:
    outage_id: str
    ward_ids: tuple[str, ...]
    start: datetime
    end: datetime | None  # None while ongoing / not announced
    source: str
    reason: str
    created_by: str
    people_affected: float
    planned_hours: float | None


def create_outage(
    outage_id: str,
    ward_ids: Iterable[str],
    start: datetime,
    end: datetime | None,
    source: str,
    reason: str,
    created_by: str,
    known_wards: set[str],
    people_affected: float,
) -> tuple[OutageEvent, dict[str, Any]]:
    """Validate and record an outage; returns the event and ledger.next_entry arguments."""
    wards = tuple(ward_ids)
    if not wards or any(w not in known_wards for w in wards):
        raise ValueError(f"Outage needs known ward ids, got {wards}")
    if source not in SOURCES:
        raise ValueError(f"Unknown outage source: {source}")
    if not reason.strip():
        raise ValueError("An outage needs a written reason")
    if end is not None and end <= start:
        raise ValueError("Outage end must be after its start")
    if people_affected < 0:
        raise ValueError("people_affected cannot be negative")
    hours = (end - start).total_seconds() / 3600 if end else None
    event = OutageEvent(
        outage_id, wards, start, end, source, reason, created_by, people_affected, hours
    )
    args = {
        "event_type": "outage_created",
        "entity_type": "outage",
        "entity_id": outage_id,
        "payload": {
            "ward_ids": list(wards),
            "start": start.isoformat(),
            "end": end.isoformat() if end else None,
            "source": source,
            "reason": reason,
            "created_by": created_by,
            "people_affected": people_affected,
        },
    }
    return event, args


@dataclass(frozen=True)
class OutageCandidate:
    ward_id: str
    distinct_reports: int
    first_report_at: datetime
    report_ids: tuple[str, ...]
    needs_officer_confirmation: bool = True


def detect_from_complaints(
    complaints: Iterable[dedup.ComplaintRecord],
    now: datetime,
    rule: dedup.DedupRule | None = None,
) -> list[OutageCandidate]:
    cfg = ALLOCATION_CONFIG
    complaints = list(complaints)
    duplicates = {link.child_id for link in dedup.link_duplicates(complaints, rule)}
    since = now.timestamp() - cfg.outage_detection_window_hours * 3600
    by_ward: dict[str, list[dedup.ComplaintRecord]] = defaultdict(list)
    for c in complaints:
        if (
            c.id not in duplicates
            and c.category in OUTAGE_CATEGORIES
            and c.area
            and since < c.created_at.timestamp() <= now.timestamp()
        ):
            by_ward[c.area].append(c)
    return [
        OutageCandidate(
            ward_id=ward,
            distinct_reports=len(reports),
            first_report_at=min(r.created_at for r in reports),
            report_ids=tuple(sorted(r.id for r in reports)),
        )
        for ward, reports in sorted(by_ward.items())
        if len(reports) >= cfg.outage_min_distinct_reports
    ]


def deprivation_weight(hours: float) -> float:
    return math.exp(max(hours, 0.0) / ALLOCATION_CONFIG.deprivation_tau_hours)


def people_in_wards(ward_ids: Iterable[str], evidence: list[dict[str, str]]) -> float:
    wanted = set(ward_ids)
    return sum(
        float(r["population"]) for r in evidence if r["ward_id"] in wanted and r.get("population")
    )


@dataclass(frozen=True)
class CriticalStop:
    stop_id: str
    name: str
    ward_id: str
    litres: float


@dataclass(frozen=True)
class CriticalAllocation:
    stop_id: str
    ward_id: str
    litres: float


@dataclass(frozen=True)
class OutageAllocation:
    outage_id: str
    ward_ids: tuple[str, ...]
    hours_cut_off: float
    priority: float
    people: float
    floor: float
    target: float
    litres: float
    status: str  # TARGET_MET | FLOOR_MET | FLOOR_NOT_MET


@dataclass
class OutageResponse:
    critical: list[CriticalAllocation]
    allocations: list[OutageAllocation]
    ended: list[str]
    unused_litres: float
    counts_toward_water_debt: bool = False
    basis: dict[str, str] = field(
        default_factory=lambda: {
            "people": "DERIVED (Census 2011 population via E2) or officer count",
            "lpcd": "ASSUMED (F10 10-15 lpcd)",
            "priority": "ASSUMED deprivation weight exp(hours / tau)",
        }
    )


def plan_response(
    outages: list[OutageEvent],
    critical_stops: list[CriticalStop],
    capacity_litres: float,
    now: datetime,
) -> OutageResponse:
    cfg = ALLOCATION_CONFIG
    left = capacity_litres
    critical = []
    for stop in critical_stops:
        given = min(stop.litres, max(left, 0.0))
        critical.append(CriticalAllocation(stop.stop_id, stop.ward_id, given))
        left -= given

    active = [o for o in outages if o.end is None or o.end > now]
    ended = [o.outage_id for o in outages if o not in active]
    hours = {o.outage_id: max((now - o.start).total_seconds() / 3600, 0.0) for o in active}
    order = sorted(active, key=lambda o: (-hours[o.outage_id], o.start, o.outage_id))
    floor = {o.outage_id: o.people_affected * cfg.outage_floor_lpcd for o in active}
    target = {o.outage_id: o.people_affected * cfg.outage_target_lpcd for o in active}
    given = dict.fromkeys(floor, 0.0)
    for limit in (floor, target):  # everyone's floor in priority order, then top-ups
        for o in order:
            add = min(limit[o.outage_id] - given[o.outage_id], max(left, 0.0))
            given[o.outage_id] += add
            left -= add

    allocations = []
    for o in order:
        litres = given[o.outage_id]
        if litres >= target[o.outage_id] - EPSILON:
            status = "TARGET_MET"
        elif litres >= floor[o.outage_id] - EPSILON:
            status = "FLOOR_MET"
        else:
            status = "FLOOR_NOT_MET"
        allocations.append(
            OutageAllocation(
                outage_id=o.outage_id,
                ward_ids=o.ward_ids,
                hours_cut_off=round(hours[o.outage_id], 2),
                priority=deprivation_weight(hours[o.outage_id]),
                people=o.people_affected,
                floor=floor[o.outage_id],
                target=target[o.outage_id],
                litres=litres,
                status=status,
            )
        )
    return OutageResponse(critical, allocations, ended, max(left, 0.0))
