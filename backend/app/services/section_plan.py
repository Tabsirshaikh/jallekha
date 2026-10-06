"""Daily plan by HMWSSB section from one month's real booking totals (feat/section-queue).

HMWSSB publishes bookings per section per month, need only per ward, and no daily data. This
module makes the planner's inputs with the SECTION as the group instead of the ward:

* **Daily bookings** = the month's real total of each section divided by the days of the month,
  integers by running remainder so each section's days add up to its month exactly. Nothing is
  random. Arrival times are spread evenly over the day. Every booking is tier 2 and domestic
  (HMWSSB publishes neither), so tier 0 and tier 1 are not tested here.
* **Entitlement** of a section = its domestic connections (HMWSSB billing, REAL) x its need weight
  (Census 2011 carried onto the section by building share, DERIVED_APPROXIMATE). A section with
  no need of its own gets an ESTIMATE: the median of the sections of its division that have one,
  else of the whole city. Such a section is flagged, so an officer must check it before approval.
* **Station**: the section's home station from the sandbox network (nearest of the 90 ASSUMED
  stand-in stations). Sections placed after review, or with no point at all, get the nearest
  station by straight line, or the station most sections of their division use. Flagged too.
* **Capacity**: the A8 fleet scenario (1,150 tankers x 9 trips, ASSUMED, news) as trips per
  station, as the replay uses it.

Pure functions over files read from the repo root; no database, no clock, no randomness.
"""

from __future__ import annotations

import calendar
import csv
import json
import math
import statistics
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path

from app.services import fair_queue, planner
from app.services.service_models import NeedWeights
from app.services.water_debt import DebtAccount

SECTION_PREFIX = "section:"
SECTION_NEED = "data/derived/evidence/section_need.csv"
CHECKS = "data/derived/underserved/section_checks.csv"
SECTION_POINTS = "data/derived/sandbox/section_points.csv"
STATIONS = "data/derived/sandbox/stations.csv"
STATION_PAIRS = "data/derived/sandbox/station_station_km.csv"
SECTION_STATION_KM = "data/derived/sandbox/section_station_km.csv"
REVIEWED = "data/derived/crosswalk/section_placement_reviewed.csv"
TANKERS = "data/raw/hmwssb_tankers_portal"
SANDBOX_CHECKS = "data/verification/sandbox_checks.json"
CAPACITY_SCENARIOS = ("fleet", "tight")
PLAN_YEAR = 2025  # the last calendar year on the section names that match our section tables

NEED_OWN = "DERIVED_APPROXIMATE"
NEED_DIVISION = "ESTIMATED_DIVISION_MEDIAN"
NEED_CITY = "ESTIMATED_CITY_MEDIAN"


class SectionPlanUnavailable(LookupError):
    """The day is outside the months this plan can be made for."""


@dataclass(frozen=True)
class SectionInfo:
    section: str
    division: str
    connections: float
    connections_basis: str  # DERIVED (billing) or an ESTIMATED_* label
    wad: float
    cad: float
    hardship: float
    need_basis: str
    station: str
    station_basis: str  # NETWORK, NEAREST_STATION or DIVISION_STATION
    lat: float | None
    lng: float | None

    @property
    def group(self) -> str:
        return SECTION_PREFIX + self.section

    @property
    def estimated(self) -> bool:
        return self.need_basis != NEED_OWN or self.connections_basis != "DERIVED"

    def need_weight(self, weights: NeedWeights) -> float:
        return (
            1 + weights.wad * self.wad + weights.cad * self.cad + weights.hardship * self.hardship
        )

    def entitlement(self, weights: NeedWeights) -> float:
        return self.connections * self.need_weight(weights)


def _rows(root: Path, path: str) -> list[dict[str, str]]:
    with (root / path).open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _km(a: tuple[float, float], b: tuple[float, float]) -> float:
    p1, p2 = math.radians(a[0]), math.radians(b[0])
    h = (
        math.sin((p2 - p1) / 2) ** 2
        + math.cos(p1) * math.cos(p2) * math.sin(math.radians(b[1] - a[1]) / 2) ** 2
    )
    return 12742.0 * math.asin(math.sqrt(h))


def _num(text: str | None) -> float | None:
    return float(text) if text not in (None, "") else None


def load_sections(root: Path) -> dict[str, SectionInfo]:
    """Every section checked in 2025, with need, connections and station (estimates flagged)."""
    checks = _rows(root, CHECKS)
    own = {r["section"]: r for r in _rows(root, SECTION_NEED)}
    points = {r["section"]: r for r in _rows(root, SECTION_POINTS)}
    reviewed = {
        r["section"]: r
        for r in _rows(root, REVIEWED)
        if r["final_status"] in ("ACCEPT_AUTO", "ACCEPT_REVIEWED") and r["lat"] and r["lng"]
    }
    stations = {r["station_id"]: (float(r["lat"]), float(r["lng"])) for r in _rows(root, STATIONS)}

    division = {r["section"]: r["division"] for r in checks}
    by_division: dict[str, list[dict[str, str]]] = defaultdict(list)
    for name, row in own.items():
        by_division[division.get(name, row["division"])].append(row)

    def median(rows: Iterable[dict[str, str]], key: str) -> float:
        return statistics.median(float(r[key]) for r in rows)

    city = list(own.values())
    conns_by_division: dict[str, list[float]] = defaultdict(list)
    for r in checks:
        if _num(r["domestic_connections"]):
            conns_by_division[r["division"]].append(float(r["domestic_connections"]))
    city_conns = statistics.median(v for vs in conns_by_division.values() for v in vs)

    home_by_division: dict[str, Counter[str]] = defaultdict(Counter)
    for name, p in points.items():
        if p["home_station"] and name in division:
            home_by_division[division[name]][p["home_station"]] += 1

    out: dict[str, SectionInfo] = {}
    for r in checks:
        name, div = r["section"], r["division"]
        if name in own:
            n = own[name]
            wad, cad, hard, basis = float(n["wad"]), float(n["cad"]), float(n["hardship"]), NEED_OWN
        elif by_division.get(div):
            peers = by_division[div]
            wad, cad, hard = (median(peers, k) for k in ("wad", "cad", "hardship"))
            basis = NEED_DIVISION
        else:
            wad, cad, hard = (median(city, k) for k in ("wad", "cad", "hardship"))
            basis = NEED_CITY
        conns = _num(r["domestic_connections"])
        if conns:
            conns_basis = "DERIVED"
        elif conns_by_division.get(div):
            conns, conns_basis = (
                statistics.median(conns_by_division[div]),
                "ESTIMATED_DIVISION_MEDIAN",
            )
        else:
            conns, conns_basis = city_conns, "ESTIMATED_CITY_MEDIAN"
        lat = lng = None
        if name in reviewed:
            lat, lng = float(reviewed[name]["lat"]), float(reviewed[name]["lng"])
        elif name in points and points[name]["lat"]:
            lat, lng = float(points[name]["lat"]), float(points[name]["lng"])
        home = points.get(name, {}).get("home_station") or ""
        if home:
            station, station_basis = home, "NETWORK"
        elif lat is not None:
            station = min(stations, key=lambda s: _km((lat, lng), stations[s]))
            station_basis = "NEAREST_STATION"
        elif home_by_division.get(div):
            station, station_basis = home_by_division[div].most_common(1)[0][0], "DIVISION_STATION"
        else:
            station = min(stations)  # no information at all: first station, flagged below
            station_basis = "DIVISION_STATION"
        out[name] = SectionInfo(name, div, conns, conns_basis, wad, cad, hard, basis, station,
                                station_basis, lat, lng)  # fmt: skip
    return out


def month_totals(root: Path, year: int, month: int) -> dict[str, int]:
    """The real bookings of each section in the month (HMWSSB portal)."""
    path = root / TANKERS / f"{year}-{month:02}.csv"
    if not path.exists():
        raise SectionPlanUnavailable(f"No booking data for {year}-{month:02}")
    totals: dict[str, int] = defaultdict(int)
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            if row["section"].strip():
                totals[row["section"].strip()] += int(float(row["noofbookings"] or 0))
    return dict(totals)


def daily_count(total: int, days: int, index: int) -> int:
    """Bookings of one section on day `index` (0-based): total / days by running remainder, so the
    days add up to the total exactly and no day differs from another by more than one."""
    return total * (index + 1) // days - total * index // days


def make_bookings(
    sections: Mapping[str, SectionInfo], totals: Mapping[str, int], day: date
) -> tuple[list[fair_queue.QueueBooking], list[tuple[str, int]]]:
    """The day's bookings from month totals, and the sections left out (no section row)."""
    days = calendar.monthrange(day.year, day.month)[1]
    index = day.day - 1
    out: list[fair_queue.QueueBooking] = []
    left_out: list[tuple[str, int]] = []
    midnight = datetime.combine(day, time(0, 0), tzinfo=UTC) - timedelta(hours=5, minutes=30)
    for name in sorted(totals):
        n = daily_count(totals[name], days, index)
        if name not in sections:
            if n:
                left_out.append((name, n))
            continue
        for k in range(n):
            out.append(
                fair_queue.QueueBooking(
                    booking_id=f"{name}|{day.isoformat()}|{k + 1}",
                    group=SECTION_PREFIX + name,
                    arrived_at=midnight + timedelta(seconds=int(86400 * (k + 0.5) / n)),
                    tier=2,
                    consumer_id=f"{name}|{day.isoformat()}|{k + 1}",
                    category="domestic",
                )
            )
    return out, left_out


def total_trips(root: Path, scenario: str) -> int:
    """Trips a day: the full fleet (1,150 tankers x 9, ASSUMED, news) or the `tight` scenario, the
    replay's trips calibrated to the REAL Jun-Aug 2026 delivered share (A8, DERIVED)."""
    if scenario == "fleet":
        return trips_per_day()
    if scenario == "tight":
        checks = json.loads((root / SANDBOX_CHECKS).read_text(encoding="utf-8"))
        return int(sum(checks["capacities"]["main_2025"]["tight"].values()))
    raise ValueError(f"capacity must be one of {CAPACITY_SCENARIOS}")


def station_capacity(
    root: Path, sections: Mapping[str, SectionInfo], scenario: str = "fleet"
) -> dict[str, int]:
    """Trips per station: the fleet's trips a day (1,150 tankers x 9, ASSUMED, news) shared out in
    proportion to the year's real bookings of the sections each station serves (largest
    remainder), at least one trip for any station that serves a section. Capacity follows where
    the year's demand is, so a month that is busy in a few places leaves those stations short."""
    year_total: dict[str, int] = defaultdict(int)
    for month in range(1, 13):
        for name, n in month_totals(root, PLAN_YEAR, month).items():
            if name in sections:
                year_total[sections[name].station] += n
    stations = {s.station for s in sections.values()}
    trips_in_total = total_trips(root, scenario)
    grand = sum(year_total.values())
    exact = {st: trips_in_total * year_total.get(st, 0) / grand for st in stations}
    trips = {st: max(1, math.floor(v)) for st, v in exact.items()}
    spare = trips_in_total - sum(trips.values())
    by_remainder = sorted(stations, key=lambda st: (-(exact[st] - math.floor(exact[st])), st))
    for st in by_remainder[: max(0, spare)]:
        trips[st] += 1
    return trips


def station_pairs(root: Path) -> dict[tuple[str, str], float]:
    return {
        (r["station_a"], r["station_b"]): float(r["round_trip_km"])
        for r in _rows(root, STATION_PAIRS)
    }


@dataclass(frozen=True)
class SectionGate:
    """The confidence gate for section groups: a section whose need or connection count is an
    estimate has confidence 0 and needs an officer's check; the others pass. (T9's census and
    location signals are written for wards, so they are not used here.)"""

    sections: Mapping[str, SectionInfo]

    def assess(self, groups: Iterable[str]) -> dict[str, planner.Assessment]:
        out: dict[str, planner.Assessment] = {}
        for g in sorted(set(groups)):
            info = self.sections.get(g.removeprefix(SECTION_PREFIX))
            if info is None:
                out[g] = planner.Assessment(0.0, True, "UNKNOWN_SECTION", "SECTION_GATE")
            elif info.need_basis != NEED_OWN:
                out[g] = planner.Assessment(0.0, True, "NEED_IS_AN_ESTIMATE", "SECTION_GATE")
            elif info.connections_basis != "DERIVED":
                out[g] = planner.Assessment(
                    0.0, True, "CONNECTIONS_ARE_AN_ESTIMATE", "SECTION_GATE"
                )
            else:
                out[g] = planner.Assessment(1.0, False, "OK", "SECTION_GATE")
        return out


def plan_inputs(
    root: Path,
    day: date,
    weights: NeedWeights,
    plan_id: str,
    debts: Iterable[DebtAccount] = (),
    scenario: str = "fleet",
) -> tuple[planner.PlanInputs, dict[str, SectionInfo], list[tuple[str, int]]]:
    if day.year != PLAN_YEAR:
        raise SectionPlanUnavailable(
            f"Section plans use the {PLAN_YEAR} section names; choose a day in {PLAN_YEAR}"
        )
    sections = load_sections(root)
    totals = month_totals(root, day.year, day.month)
    bookings, left_out = make_bookings(sections, totals, day)
    pending = [
        planner.PlannerBooking(b, sections[b.group.removeprefix(SECTION_PREFIX)].station)
        for b in bookings
    ]
    inputs = planner.PlanInputs(
        plan_id=plan_id,
        day=day,
        capacity=station_capacity(root, sections, scenario),
        pending=pending,
        entitlement={s.group: s.entitlement(weights) for s in sections.values()},
        queue_states={},
        debts={a.account_id: a for a in debts},
        station_km=station_pairs(root),
    )
    return inputs, sections, left_out


def trips_per_day() -> int:
    from app.config.sandbox import SANDBOX_CONFIG

    return int(SANDBOX_CONFIG.fleet_tankers * SANDBOX_CONFIG.trips_per_tanker_day)
