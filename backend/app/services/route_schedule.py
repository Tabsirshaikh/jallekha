"""Tanker routes of a plan by section: who drives where, in what order, and when.

A booking is one tanker load, so a trip is station -> place -> station and a tanker's day is a list
of round trips from its home station. The plan (A7) already decided WHICH loads are served; this
turns them into named tankers with times:

* **Tankers** on the road at a station follow the station's trips of the day (largest remainder,
  at least one), out of the fleet of 1,150.
* **Loads**, in priority order: critical facilities (F10), cut sections (F10), sections on
  scheduled supply (F9), then the booked queue in the order the fair queue (F8) served it. A load
  that a neighbouring station lent its spare trip for is driven from the lending station.
* **Special loads** (F9, F10) have no home station: each goes to the nearest station that still
  has a spare special trip, so the tanker that serves a flagged section is one that is close by.
* **Scheduling**: every load goes to the station's tanker that is free first (so the highest
  priority loads leave in the first wave and no tanker idles while loads wait), if the whole trip
  fits in the working day; a load that cannot be fitted is listed, never dropped silently.
* **Road legs**: OSRM car legs (cached, DERIVED, free-flow so optimistic) where the section was
  placed when they were built; the straight line x 1.35 at 25 km/h (ESTIMATE) otherwise. Each
  way adds the drive inside the section to the household (A8, about 1 km): a station that
  stands on a section's centre point is not a zero-kilometre trip.

Pure function over the plan and files; no clock, no randomness.
"""

from __future__ import annotations

import csv
import heapq
import math
import statistics
from collections import defaultdict
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.config.allocation import ALLOCATION_CONFIG
from app.config.sandbox import SANDBOX_CONFIG
from app.config.section_plan import SECTION_PLAN_CONFIG as CFG
from app.services import planner, section_plan

OSRM_SECTION_STATION = "data/derived/routing/osrm_section_station.csv"
STATIONS = "data/derived/sandbox/stations.csv"
SECTION_PREFIX = section_plan.SECTION_PREFIX
KIND_ORDER = {"critical": 0, "outage": 1, "scheduled": 2, "booked": 3}


@dataclass(frozen=True)
class Load:
    kind: str  # critical | outage | scheduled | booked
    group: str  # the section's group id ("section:NAME")
    name: str  # what is shown: a facility, or the section
    lat: float | None
    lng: float | None
    booking_id: str | None = None
    station: str | None = None  # the station that must drive it (booked); None = nearest


@lru_cache(maxsize=2)
def _stations(root: str) -> dict[str, tuple[float, float]]:
    with (Path(root) / STATIONS).open(encoding="utf-8", newline="") as handle:
        return {r["station_id"]: (float(r["lat"]), float(r["lng"])) for r in csv.DictReader(handle)}


@lru_cache(maxsize=2)
def _osrm(root: str) -> dict[tuple[str, str], tuple[float, float, float, float]]:
    out: dict[tuple[str, str], tuple[float, float, float, float]] = {}
    with (Path(root) / OSRM_SECTION_STATION).open(encoding="utf-8", newline="") as handle:
        for r in csv.DictReader(handle):
            out[(r["section"], r["station_id"])] = (
                float(r["out_km"]),
                float(r["out_min"]),
                float(r["back_km"]),
                float(r["back_min"]),
            )
    return out


def _haversine(a: tuple[float, float], b: tuple[float, float]) -> float:
    p1, p2 = math.radians(a[0]), math.radians(b[0])
    h = (
        math.sin((p2 - p1) / 2) ** 2
        + math.cos(p1) * math.cos(p2) * math.sin(math.radians(b[1] - a[1]) / 2) ** 2
    )
    return 12742.0 * math.asin(math.sqrt(h))


def leg(
    root: Path,
    station: str,
    section: str | None,
    lat: float | None,
    lng: float | None,
    access: bool = True,
) -> tuple[float, float, float, float, str]:
    """(km there, minutes there, km back, minutes back, basis) between a station and a place.

    A section is an area, not a point, so unless the place is one address (`access` False) each
    way adds the drive inside the section to the household: `section_access_km` x road factor
    (A8, 0.732 km x 1.35 each way, DERIVED), at the average speed."""
    inside_km = SANDBOX_CONFIG.section_access_km * ALLOCATION_CONFIG.road_factor if access else 0.0
    inside_min = inside_km / ALLOCATION_CONFIG.avg_speed_kmph * 60
    known = _osrm(str(root)).get((section or "", station))
    if known is not None:
        out_km, out_min, back_km, back_min = known
        return (
            out_km + inside_km,
            out_min + inside_min,
            back_km + inside_km,
            back_min + inside_min,
            "OSRM",
        )
    here = _stations(str(root))[station]
    if lat is not None and lng is not None:
        km = _haversine(here, (lat, lng)) * ALLOCATION_CONFIG.road_factor + inside_km
        minutes = km / ALLOCATION_CONFIG.avg_speed_kmph * 60
        return km, minutes, km, minutes, "ESTIMATE"
    # No location at all: the typical leg of this station.
    table = [v for (s, st), v in _osrm(str(root)).items() if st == station]
    if table:
        return (
            statistics.median(v[0] for v in table) + inside_km,
            statistics.median(v[1] for v in table) + inside_min,
            statistics.median(v[2] for v in table) + inside_km,
            statistics.median(v[3] for v in table) + inside_min,
            "ESTIMATE",
        )
    return 5.0 + inside_km, 12.0 + inside_min, 5.0 + inside_km, 12.0 + inside_min, "ESTIMATE"


def hhmm(minute: float) -> str:
    m = int(round(minute))
    return f"{m // 60:02d}:{m % 60:02d}"


def _tankers_per_station(plan: planner.DailyPlan) -> dict[str, int]:
    """Tankers on the road at each station: the fleet shared by station trips (largest
    remainder), at least one where a station has trips. In the tight scenario the fleet has
    fewer trips to run, so only as many tankers are needed as trips / 9 (the rest stay idle)."""
    trips = {s: p.trips for s, p in plan.stations.items() if p.trips > 0}
    total = sum(trips.values())
    if total == 0:
        return {}
    fleet = min(
        SANDBOX_CONFIG.fleet_tankers, math.ceil(total / SANDBOX_CONFIG.trips_per_tanker_day)
    )
    exact = {s: fleet * t / total for s, t in trips.items()}
    out = {s: max(1, math.floor(v)) for s, v in exact.items()}
    spare = fleet - sum(out.values())
    for s in sorted(trips, key=lambda s: (-(exact[s] - math.floor(exact[s])), s))[: max(0, spare)]:
        out[s] += 1
    return out


def _special_loads(
    plan: planner.DailyPlan,
    inputs: planner.PlanInputs,
    sections: dict[str, section_plan.SectionInfo],
) -> list[Load]:
    load_litres = ALLOCATION_CONFIG.tanker_load_litres
    out: list[Load] = []

    def place(group: str) -> tuple[float | None, float | None]:
        info = sections.get(group.removeprefix(SECTION_PREFIX))
        return (info.lat, info.lng) if info else (None, None)

    for c in plan.outage.critical:
        if c.litres <= 0:
            continue
        where = inputs.critical_locations.get(c.stop_id)
        name = next((s.name for s in inputs.critical_stops if s.stop_id == c.stop_id), c.stop_id)
        for _ in range(max(1, math.ceil(c.litres / load_litres))):
            out.append(Load("critical", c.ward_id, name, where[0] if where else None,
                            where[1] if where else None))  # fmt: skip
    for a in plan.outage.allocations:
        if a.litres <= 0:
            continue
        people = {g: sections[g.removeprefix(SECTION_PREFIX)].people for g in a.ward_ids
                  if g.removeprefix(SECTION_PREFIX) in sections}  # fmt: skip
        total = sum(people.values()) or 1.0
        for group, p in sorted(people.items()):
            lat, lng = place(group)
            for _ in range(max(1, math.ceil(a.litres * p / total / load_litres))):
                out.append(Load("outage", group, group.removeprefix(SECTION_PREFIX), lat, lng))
    for group, share in sorted(plan.scheduled.items()):
        if share.litres <= 0:
            continue
        lat, lng = place(group)
        for _ in range(max(1, round(share.litres / load_litres))):
            out.append(Load("scheduled", group, group.removeprefix(SECTION_PREFIX), lat, lng))
    return out


def build_routes(
    root: Path,
    plan: planner.DailyPlan,
    inputs: planner.PlanInputs,
    sections: dict[str, section_plan.SectionInfo],
) -> dict[str, Any]:
    cfg = CFG
    fill, service = ALLOCATION_CONFIG.fill_minutes, ALLOCATION_CONFIG.service_minutes
    day_start, day_end = cfg.route_day_start_minute, cfg.route_day_end_minute
    stations = _stations(str(root))
    tankers_at = _tankers_per_station(plan)

    # -- booked loads by the station that drives them, in the order the plan served them
    booked: dict[str, list[tuple[int, str, planner.ServedBooking]]] = defaultdict(list)
    for station, sp in plan.stations.items():
        for b in sp.served:
            booked[b.lender or station].append((b.position, station, b))
    loads_at: dict[str, list[Load]] = defaultdict(list)
    for station, rows in booked.items():
        for _, _, b in sorted(rows, key=lambda r: (r[2].lender is not None, r[0], r[1])):
            info = sections.get(b.group.removeprefix(SECTION_PREFIX))
            loads_at[station].append(
                Load(
                    "booked",
                    b.group,
                    b.group.removeprefix(SECTION_PREFIX),
                    info.lat if info else None,
                    info.lng if info else None,
                    b.booking_id,
                    station,
                )  # fmt: skip
            )

    # -- special loads go to the nearest station with a spare special trip
    spare = {s: max(0, p.trips - p.booked_trips) for s, p in plan.stations.items()}
    specials_at: dict[str, list[Load]] = defaultdict(list)
    for load in sorted(_special_loads(plan, inputs, sections), key=lambda x: KIND_ORDER[x.kind]):
        name = load.group.removeprefix(SECTION_PREFIX)
        ranked = sorted(
            tankers_at,
            key=lambda s: (leg(root, s, name, load.lat, load.lng)[1], s),
        )
        pick = next((s for s in ranked if spare.get(s, 0) > 0), ranked[0] if ranked else None)
        if pick is None:
            continue
        spare[pick] = spare.get(pick, 0) - 1
        specials_at[pick].append(Load(load.kind, load.group, load.name, load.lat, load.lng,
                                      None, pick))  # fmt: skip

    # -- schedule, station by station
    tanker_rows: list[dict[str, Any]] = []
    station_rows: list[dict[str, Any]] = []
    unscheduled: list[dict[str, Any]] = []
    serial = 0
    for station in sorted(set(tankers_at) | set(loads_at) | set(specials_at)):
        count = tankers_at.get(station, 0)
        if count == 0 and (loads_at.get(station) or specials_at.get(station)):
            count = 1  # a lender with no trips of its own still drives what it lent
        ids = [f"T{serial + i + 1:04d}" for i in range(count)]
        serial += count
        free = [(float(day_start), i) for i in range(count)]
        heapq.heapify(free)
        routes: list[list[dict[str, Any]]] = [[] for _ in range(count)]
        done_special = done_booked = 0
        km_total = 0.0
        queue = specials_at.get(station, []) + loads_at.get(station, [])
        for load in queue:
            kmo, mino, kmb, minb, basis = leg(root, station, load.name if load.kind != "critical"
                                              else load.group.removeprefix(SECTION_PREFIX),
                                              load.lat, load.lng)  # fmt: skip
            if load.kind == "critical" and load.lat is not None:  # one address, no drive inside
                kmo, mino, kmb, minb, basis = leg(root, station, None, load.lat, load.lng, False)
            duration = fill + mino + service + minb
            if not free or free[0][0] + duration > day_end:
                unscheduled.append(
                    {"kind": load.kind, "group": load.group, "name": load.name,
                     "booking_id": load.booking_id, "station_id": station, "reason": "NO_TIME_LEFT"}
                )  # fmt: skip
                continue
            start, idx = heapq.heappop(free)
            end = start + duration
            routes[idx].append(
                {
                    "n": len(routes[idx]) + 1,
                    "kind": load.kind,
                    "group": load.group,
                    "name": load.name,
                    "booking_id": load.booking_id,
                    "lat": load.lat,
                    "lng": load.lng,
                    "depart": hhmm(start + fill),
                    "arrive": hhmm(start + fill + mino),
                    "unloaded": hhmm(start + fill + mino + service),
                    "back": hhmm(end),
                    "km": round(kmo + kmb, 2),
                    "minutes": round(duration, 1),
                    "leg_basis": basis,
                }
            )
            km_total += kmo + kmb
            done_special += load.kind != "booked"
            done_booked += load.kind == "booked"
            heapq.heappush(free, (end, idx))
        finish = 0.0
        for i, trips in enumerate(routes):
            if not trips:
                continue
            last = trips[-1]["back"]
            finish = max(finish, int(last[:2]) * 60 + int(last[3:]))
            tanker_rows.append(
                {
                    "tanker_id": ids[i],
                    "station_id": station,
                    "trips": trips,
                    "km": round(sum(t["km"] for t in trips), 1),
                    "finish": last,
                    "sections_reached": len({t["group"] for t in trips}),
                }
            )
        lat, lng = stations[station]
        station_rows.append(
            {
                "station_id": station,
                "lat": lat,
                "lng": lng,
                "tankers": count,
                "tankers_used": sum(1 for t in routes if t),
                "capacity_trips": plan.stations[station].trips if station in plan.stations else 0,
                "trips": done_special + done_booked,
                "special_trips": done_special,
                "km": round(km_total, 1),
                "finish": hhmm(finish) if finish else None,
                "unscheduled": sum(1 for u in unscheduled if u["station_id"] == station),
            }
        )
    trips_all = [t for row in tanker_rows for t in row["trips"]]
    summary = {
        "tankers": sum(r["tankers_used"] for r in station_rows),
        "fleet": SANDBOX_CONFIG.fleet_tankers,
        "stations": len(station_rows),
        "trips": len(trips_all),
        "special_trips": sum(1 for t in trips_all if t["kind"] != "booked"),
        "unscheduled": len(unscheduled),
        "total_km": round(sum(t["km"] for t in trips_all), 1),
        "sections_reached": len({t["group"] for t in trips_all}),
        "legs_estimated": sum(1 for t in trips_all if t["leg_basis"] != "OSRM"),
        "latest_finish": max((r["finish"] for r in tanker_rows), default=None),
        "average_trips_per_tanker": round(len(trips_all) / max(1, len(tanker_rows)), 1),
    }
    return {
        "summary": summary,
        "stations": sorted(station_rows, key=lambda r: -r["trips"]),
        "tankers": tanker_rows,
        "unscheduled": unscheduled,
        "basis": {
            "trips": "Each served booking is one tanker load driven station -> section -> "
            "station; loads go in the plan's priority order to the tanker free first",
            "legs": "DERIVED where OSRM road legs were built (free-flow car, no traffic), "
            "ESTIMATE (straight line x 1.35 at 25 km/h) for sections placed after review and "
            "for facilities, plus about 1 km each way inside the section to the household (A8)",
            "times": f"Fill {fill} min, unload {service} min (ASSUMED); working day "
            f"{hhmm(day_start)}-{hhmm(day_end)} (two shifts, ASSUMED)",
            "tankers": "Tankers per station follow its trips of the day; the fleet is 1,150 "
            "(from news)",
            "special": "Scheduled-supply and outage loads go to the nearest station with a "
            "spare special trip; stops are the estimated centre of the section",
        },
    }


KINDS = ("booked", "scheduled", "outage", "critical")


def compact_paths(routes: dict[str, Any]) -> list[dict[str, Any]]:
    """Every tanker's trips in a small form for the city-wide animation: per trip
    [lat, lng, depart, arrive, unloaded, back, kind] with times in minutes after midnight and kind
    an index of KINDS (trips with no known place are left out)."""

    def minute(text: str) -> int:
        return int(text[:2]) * 60 + int(text[3:])

    out = []
    for t in routes["tankers"]:
        trips = [
            [
                round(x["lat"], 4),
                round(x["lng"], 4),
                minute(x["depart"]),
                minute(x["arrive"]),
                minute(x["unloaded"]),
                minute(x["back"]),
                KINDS.index(x["kind"]),
            ]
            for x in t["trips"]
            if x["lat"] is not None and x["lng"] is not None
        ]
        out.append({"tanker_id": t["tanker_id"], "station_id": t["station_id"], "trips": trips})
    return out
