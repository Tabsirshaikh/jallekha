"""What a plan by section does, in figures an officer can read (the plan screen's overview).

From the plan and its inputs only (nothing new is decided here):

* **facts**: bookings of the day (new and carried over), priority classes, trips available, trips
  kept for scheduled supply and supply cuts, served and waiting;
* **sections**: per section its bookings and how many were served by priority class, its service
  type (F7, below), scheduled supply or outage water, and why it is on scheduled supply;
* **stations**: per filling station the bookings of each section it holds, so the screen can
  replay the station's queue in the order the fair queue (F8) served it.

Service types (F7: booked service, scheduled supply, outage response), one per section:

1. ``cut``: water cut today by a supply notice (F10 outage response);
2. ``scheduled``: books far fewer tankers than similar sections, so water is sent on a schedule
   (F9, the sections the field-check screen F4 flags);
3. ``heavy``: books many tankers for its homes (the top quarter of 2025 bookings per 1,000
   domestic connections): the pipes fall short, served through the booked queue (F8);
4. ``normal``: books now and then, served through the booked queue (F8);
5. ``unknown``: no connection count to judge by.

Basis: DERIVED from REAL bookings (D1) and connections (D19); the cut-off is ASSUMED.
"""

from __future__ import annotations

import csv
import math
import statistics
from collections import Counter, defaultdict
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.config.allocation import ALLOCATION_CONFIG
from app.config.sandbox import SANDBOX_CONFIG
from app.config.section_plan import SECTION_PLAN_CONFIG as CFG
from app.services import planner, section_plan
from app.services.service_models import NeedWeights

CHECKS = section_plan.CHECKS
PREFIX = section_plan.SECTION_PREFIX


@lru_cache(maxsize=2)
def _checks(root: str) -> dict[str, dict[str, Any]]:
    """Per section: 2025 bookings per 1,000 domestic connections, the peers' rate, the F4 flag."""
    out: dict[str, dict[str, Any]] = {}
    with (Path(root) / CHECKS).open(encoding="utf-8", newline="") as handle:
        for r in csv.DictReader(handle):
            rate = float(r["rate"]) if r["rate"] else None
            ref = float(r["reference_rate"]) if r["reference_rate"] else None
            out[r["section"]] = {"rate": rate, "reference_rate": ref}
    return out


def heavy_cutoff(root: Path) -> float | None:
    """Bookings per 1,000 connections above which a section is a heavy tanker user."""
    rates = [c["rate"] for c in _checks(str(root)).values() if c["rate"] is not None]
    if len(rates) < 4:
        return None
    return statistics.quantiles(rates, n=100)[CFG.heavy_use_percentile - 1]


def _category(
    group: str,
    cut: set[str],
    scheduled: set[str],
    rate: float | None,
    cutoff: float | None,
) -> str:
    if group in cut:
        return "cut"
    if group in scheduled:
        return "scheduled"
    if rate is None or cutoff is None:
        return "unknown"
    return "heavy" if rate >= cutoff else "normal"


def _moved(root: Path, scenario: str | None, plan: planner.DailyPlan) -> int:
    if scenario not in section_plan.CAPACITY_SCENARIOS:
        return 0
    usual = section_plan._static(str(root), scenario).capacity
    return sum(max(0, sp.trips - usual.get(s, 0)) for s, sp in plan.stations.items())


def section_overview(
    root: Path,
    inputs: planner.PlanInputs,
    plan: planner.DailyPlan,
    capacity_scenario: str | None,
    weights: NeedWeights | None = None,
) -> dict[str, Any]:
    sections = section_plan.static_sections(root)
    weights = weights or NeedWeights.default()
    checks = _checks(str(root))
    cutoff = heavy_cutoff(root)
    load = ALLOCATION_CONFIG.tanker_load_litres
    lpcd = ALLOCATION_CONFIG.minimum_litres_per_person_day

    tier_of = {p.booking.booking_id: p.booking.tier for p in inputs.pending}
    rows: dict[str, dict[str, Any]] = {}

    def row(group: str) -> dict[str, Any]:
        if group not in rows:
            rows[group] = {
                "group": group,
                "bookings": 0,
                "carried": 0,
                "tiers": [0, 0, 0],
                "served": 0,
                "served_tiers": [0, 0, 0],
                "waiting": 0,
                "live": 0,  # bookings made through JalLekha (REAL); the rest are estimates
            }
        return rows[group]

    for name in sections:  # every section, also the ones with no booking today
        row(PREFIX + name)
    # Bookings that arrived before midnight at the start of the day were carried over.
    d = plan.day
    day_start = datetime(d.year, d.month, d.day, tzinfo=section_plan.IST)
    for p in inputs.pending:
        r = row(p.booking.group)
        r["bookings"] += 1
        r["tiers"][min(2, p.booking.tier)] += 1
        r["carried"] += p.booking.arrived_at < day_start
        r["live"] += "|" not in p.booking.booking_id  # estimated ids are "SECTION|day|k"
    by_station: dict[str, Counter[str]] = defaultdict(Counter)
    for p in inputs.pending:
        by_station[p.station][p.booking.group] += 1
    for sp in plan.stations.values():
        for b in sp.served:
            r = row(b.group)
            r["served"] += 1
            r["served_tiers"][min(2, tier_of.get(b.booking_id, 2))] += 1
    for r in rows.values():
        r["waiting"] = r["bookings"] - r["served"]

    scheduled_people = {w.ward_id: w.people_off_premises for w in inputs.scheduled}
    for group, share in plan.scheduled.items():
        r = row(group)
        r["scheduled"] = {
            "litres": round(share.litres),
            "people": round(scheduled_people.get(group, 0.0)),
            "litres_per_person": lpcd,
            "loads": max(1, round(share.litres / load)) if share.litres > 0 else 0,
            "full": share.litres + 1e-6 >= share.target,
        }
    cut: set[str] = set()
    for a in plan.outage.allocations:
        people = {g: sections[g.removeprefix(PREFIX)].people for g in a.ward_ids
                  if g.removeprefix(PREFIX) in sections}  # fmt: skip
        total = sum(people.values()) or 1.0
        for group, n in people.items():
            cut.add(group)
            r = row(group)
            r["outage"] = {
                "litres": round(a.litres * n / total),
                "people": round(n),
                "hours_cut_off": round(a.hours_cut_off, 1),
                "loads": max(1, math.ceil(a.litres * n / total / load)) if a.litres > 0 else 0,
                "full": a.status == "TARGET_MET",
            }
    for c in plan.outage.critical:
        r = row(c.ward_id)
        r["critical_litres"] = r.get("critical_litres", 0) + round(c.litres)

    out_rows = []
    for group, r in rows.items():
        name = group.removeprefix(PREFIX)
        info = sections.get(name)
        check = checks.get(name, {})
        rate = check.get("rate")
        r["name"] = name
        r["category"] = _category(group, cut, set(plan.scheduled), rate, cutoff)
        r["bookings_per_1000"] = round(rate, 1) if rate is not None else None
        ref = check.get("reference_rate")
        r["peer_bookings_per_1000"] = round(ref, 1) if ref is not None else None
        r["station"] = info.station if info else None
        r["need_estimated"] = info.estimated if info else True
        r["no_water_share"] = round(info.wad, 4) if info else None
        r["fair_share"] = round(plan.effective_entitlement.get(group, 0.0), 6)
        # A: this plan's turns against the Census turns (1 = Census only; below 1 = served well
        # lately, above 1 = left waiting lately)
        census = info.entitlement(weights) if info else 0.0
        r["turn_factor"] = (
            round(inputs.entitlement.get(group, census) / census, 3) if census else None
        )
        r.setdefault("scheduled", None)
        r.setdefault("outage", None)
        r.setdefault("critical_litres", 0)
        out_rows.append(r)
    out_rows.sort(key=lambda r: r["name"])

    tiers = [sum(r["tiers"][i] for r in out_rows) for i in range(3)]
    served_tiers = [sum(r["served_tiers"][i] for r in out_rows) for i in range(3)]
    trips = sum(sp.trips for sp in plan.stations.values())
    scheduled_litres = sum(s.litres for s in plan.scheduled.values())
    facts = {
        "day": plan.day.isoformat(),
        "capacity_scenario": capacity_scenario,
        "bookings": sum(r["bookings"] for r in out_rows),
        "carried": sum(r["carried"] for r in out_rows),
        "live_bookings": sum(r["live"] for r in out_rows),
        "live_sections": sum(1 for r in out_rows if r["live"]),
        "commercial": sum(1 for p in inputs.pending if p.booking.category == "commercial"),
        "tiers": tiers,
        "served_tiers": served_tiers,
        "served": sum(served_tiers),
        "waiting": sum(r["waiting"] for r in out_rows),
        "trips": trips,
        "fleet_tankers": SANDBOX_CONFIG.fleet_tankers,
        "trips_per_tanker": SANDBOX_CONFIG.trips_per_tanker_day,
        "reserve_trips": plan.reserve_trips,
        "reserve_used_trips": math.ceil(scheduled_litres / load - 1e-9),
        "outage_trips": plan.outage_trips,
        "booked_trips": sum(sp.booked_trips for sp in plan.stations.values()),
        # B: trips moved to other stations than their usual share (0 when B is off)
        "trips_moved": _moved(root, capacity_scenario, plan),
        "scheduled_sections": sum(1 for s in plan.scheduled.values() if s.litres > 0),
        "cut_sections": len(cut),
        "critical_stops": len(plan.outage.critical),
        "stations": len(plan.stations),
        "load_litres": load,
        "litres_per_person": lpcd,
    }
    stations = [
        {
            "station_id": s,
            "trips": sp.trips,
            "booked_trips": sp.booked_trips,
            "bookings": dict(sorted(by_station.get(s, Counter()).items())),
        }
        for s, sp in sorted(plan.stations.items())
    ]
    return {
        "facts": facts,
        "sections": out_rows,
        "stations": stations,
        "categories": {
            "heavy_cutoff": round(cutoff, 1) if cutoff is not None else None,
            "heavy_percentile": CFG.heavy_use_percentile,
        },
        "basis": {
            "bookings": "REAL monthly totals (HMWSSB) divided by the days of the month; carried = "
            "bookings left waiting on the days before",
            "tiers": "ESTIMATED priority classes (section_plan.py)",
            "categories": "DERIVED service type from REAL 2025 bookings and connections; cut-off "
            f"the {CFG.heavy_use_percentile}th percentile of bookings per 1,000 connections "
            "(ASSUMED)",
            "scheduled": f"Litres = people x {lpcd:g} litres a day (ASSUMED floor, F9)",
        },
    }
