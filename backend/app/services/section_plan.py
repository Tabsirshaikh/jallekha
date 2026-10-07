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
import threading
from collections import Counter, defaultdict
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta, timezone
from functools import lru_cache
from pathlib import Path

from app.config.sandbox import SANDBOX_CONFIG
from app.config.section_plan import SECTION_PLAN_CONFIG as CFG
from app.config.weekly_priority import WEEKLY_PRIORITY_CONFIG as WEEKLY
from app.services import fair_queue, outage, planner, weekly_priority
from app.services.scheduled_supply import ScheduledWard, ServicePoint, ServicePointRegistry
from app.services.service_models import NeedWeights
from app.services.water_debt import DebtAccount

SECTION_PREFIX = "section:"
SECTION_NEED = "data/derived/evidence/section_need.csv"
CHECKS = "data/derived/underserved/section_checks.csv"
SECTION_POINTS = "data/derived/sandbox/section_points.csv"
SECTION_FACILITIES = "data/derived/evidence/section_facilities.csv"
BILLING = "data/raw/hmwssb_billing_portal"
WARD_POPULATION = "data/derived/population/ward_population_2025.csv"
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
    f4_flagged: bool = False  # flagged by the under-served field-check screen (F4)
    household_size: float = CFG.household_size_fallback

    @property
    def people(self) -> float:
        """Domestic connections x household size: an ESTIMATE (one connection can serve flats)."""
        return self.connections * self.household_size

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

    sizes = [
        float(r["household_size_2011"])
        for r in _rows(root, WARD_POPULATION)
        if r.get("household_size_2011")
    ]
    size = statistics.median(sizes) if sizes else CFG.household_size_fallback  # Census 2011

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
                                station_basis, lat, lng,
                                r["field_check_candidate"] == "True", size)  # fmt: skip
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


def estimate_year(day: date) -> int:
    """The year whose real monthly totals estimate the bookings of `day`: its own year in
    PLAN_YEAR, else the same month of PLAN_YEAR (the section names of our tables; HMWSSB re-cut
    the sections in Feb/Mar 2026). Basis: ASSUMED for days after PLAN_YEAR."""
    return day.year if day.year == PLAN_YEAR else PLAN_YEAR


def live_booking(raw: Mapping[str, object]) -> fair_queue.QueueBooking:
    """A booking made through JalLekha, as stored in a plan's recipe, as a queue booking."""
    return fair_queue.QueueBooking(
        booking_id=str(raw["booking_id"]),
        group=SECTION_PREFIX + str(raw["section"]),
        arrived_at=datetime.fromisoformat(str(raw["arrived_at"])),
        tier=int(raw["tier"]),  # type: ignore[call-overload]
        consumer_id=str(raw["consumer_id"]),
        category=str(raw["category"]),
    )


def service_factors(history: Sequence[Mapping[str, tuple[int, int]]]) -> dict[str, float]:
    """A: each section's turn factor from its last 7 days (booked, served) in `history`
    (weekly_priority.service_factor); sections with too few bookings keep 1 (Census baseline)."""
    booked: Counter[str] = Counter()
    served: Counter[str] = Counter()
    for day in history[-WEEKLY.window_days :]:
        for group, (b, s) in day.items():
            booked[group] += b
            served[group] += s
    return {
        g: weekly_priority.service_factor(max(0.0, 1 - min(1.0, served[g] / n)))
        for g, n in booked.items()
        if n >= WEEKLY.min_known_bookings
    }


def _estimated(booking_id: str) -> bool:
    """Estimated bookings (make_bookings) are named "SECTION|day|k"; real ones are not."""
    return "|" in booking_id


def daily_count(total: int, days: int, index: int) -> int:
    """Bookings of one section on day `index` (0-based): total / days by running remainder, so the
    days add up to the total exactly and no day differs from another by more than one."""
    return total * (index + 1) // days - total * index // days


@dataclass(frozen=True)
class SectionOptions:
    """What a plan by section assumes beyond the real monthly totals (stored in its recipe)."""

    priority: bool = True  # estimated tier 0 (hospitals) and tier 1 (no water on premises)
    scheduled: str = "f4"  # F9 candidates: "f4" (the F4 flagged sections) or "none"
    carry_over: bool = True  # replay the days before, carrying the waiting list and turn credits
    outages: tuple[Mapping[str, object], ...] = ()  # outage notices on the day, as stored
    # Bookings made through JalLekha that wait on the day (services/bookings.as_plan_booking).
    # A section with any of them is planned from its real bookings only; the others from the
    # month's totals divided by days.
    live: tuple[Mapping[str, object], ...] = ()
    # B: each day the trips follow the bookings waiting at each station (CFG bounds).
    rebalance: bool = False
    # A: in the days the plan replays, a section served well in the last 7 days gets fewer turns
    # and one left waiting gets more (weekly_priority.service_factor; PLANNED service, not
    # confirmed deliveries; real records, when they exist, replace it on the plan's own day).
    responsive: bool = False


def load_facilities(root: Path) -> dict[str, list[dict[str, str]]]:
    """Mapped facilities (OSM, D9) inside each section's approximate area."""
    out: dict[str, list[dict[str, str]]] = defaultdict(list)
    for r in _rows(root, SECTION_FACILITIES):
        out[r["section"]].append(r)
    return dict(out)


def commercial_shares(root: Path, sections: Mapping[str, SectionInfo]) -> dict[str, float]:
    """Share of each section's bookings labelled commercial: its commercial connections (billing
    category C) weighed so that the city's share equals the real 2022 share of commercial tanker
    trips (RTI). DERIVED from REAL billing, calibrated to a REAL (2022) city share."""
    domestic = {"D", "DS", "DM", "DP", "M0", "M1", "M2", "M3", "M4", "MB"}
    dom: dict[str, list[float]] = defaultdict(list)
    com: dict[str, list[float]] = defaultdict(list)
    for month in range(1, 13):
        path = root / BILLING / f"{PLAN_YEAR}-{month:02}.csv"
        if not path.exists():
            continue
        d: dict[str, float] = defaultdict(float)
        c: dict[str, float] = defaultdict(float)
        with path.open(encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                n = float(row["noofcans"] or 0)
                if row["category"] in domestic:
                    d[row["section"].strip()] += n
                elif row["category"] == "C":
                    c[row["section"].strip()] += n
        for name in set(d) | set(c):
            dom[name].append(d.get(name, 0.0))
            com[name].append(c.get(name, 0.0))
    mean = lambda xs: sum(xs) / len(xs) if xs else 0.0  # noqa: E731
    dm = {n: mean(dom[n]) for n in sections}
    cm = {n: mean(com[n]) for n in sections}
    weight = {
        n: sum(month_totals(root, PLAN_YEAR, m).get(n, 0) for m in range(1, 13)) for n in sections
    }
    total = sum(weight.values()) or 1.0

    def city_share(r: float) -> float:
        return (
            sum(
                weight[n] * (r * cm[n] / (dm[n] + r * cm[n]) if dm[n] + r * cm[n] else 0.0)
                for n in sections
            )
            / total
        )

    low, high = 0.0, 1000.0
    for _ in range(60):
        mid = (low + high) / 2
        low, high = (mid, high) if city_share(mid) < CFG.commercial_trip_share else (low, mid)
    r = (low + high) / 2
    return {n: (r * cm[n] / (dm[n] + r * cm[n]) if dm[n] + r * cm[n] else 0.0) for n in sections}


def make_bookings(
    sections: Mapping[str, SectionInfo],
    totals: Mapping[str, int],
    day: date,
    options: SectionOptions | None = None,
    facilities: Mapping[str, list[dict[str, str]]] | None = None,
    commercial: Mapping[str, float] | None = None,
) -> tuple[list[fair_queue.QueueBooking], list[tuple[str, int]]]:
    """The day's bookings from month totals, and the sections left out (no section row).

    With `options.priority`, the first bookings of a section are tier 0 (one per mapped hospital or
    care home, at most all of them), the next share `wad` of the rest are tier 1; the others are
    tier 2. A share of the last tier-2 bookings of each section is labelled commercial."""
    options = options or SectionOptions()
    facilities = facilities or {}
    commercial = commercial or {}
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
        info = sections[name]
        n0 = n1 = 0
        if options.priority:
            critical = sum(
                1 for f in facilities.get(name, ()) if f["category"] in CFG.tier0_categories
            )
            n0 = min(n, math.floor(critical * CFG.tier0_bookings_per_facility))
            n1 = min(n - n0, round(info.wad * (n - n0)))
        n_commercial = round(commercial.get(name, 0.0) * (n - n0 - n1))
        for k in range(n):
            tier = 0 if k < n0 else 1 if k < n0 + n1 else 2
            out.append(
                fair_queue.QueueBooking(
                    booking_id=f"{name}|{day.isoformat()}|{k + 1}",
                    group=SECTION_PREFIX + name,
                    arrived_at=midnight + timedelta(seconds=int(86400 * (k + 0.5) / n)),
                    tier=tier,
                    consumer_id=f"{name}|{day.isoformat()}|{k + 1}",
                    category="commercial" if k >= n - n_commercial else "domestic",
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


IST = timezone(timedelta(hours=5, minutes=30))


class _NullLedger:
    """A LedgerPort for the days replayed before the plan's own day: their events are not kept."""

    def append(self, entry_type: str, payload: Mapping[str, object], actor: str) -> None:
        return None


@dataclass(frozen=True)
class _Static:
    sections: dict[str, SectionInfo]
    facilities: dict[str, list[dict[str, str]]]
    commercial: dict[str, float]
    capacity: dict[str, int]
    pairs: dict[tuple[str, str], float]


@lru_cache(maxsize=4)
def _static(root: str, scenario: str) -> _Static:
    path = Path(root)
    sections = load_sections(path)
    return _Static(
        sections,
        load_facilities(path),
        commercial_shares(path, sections),
        station_capacity(path, sections, scenario),
        station_pairs(path),
    )


def scheduled_for(
    sections: Mapping[str, SectionInfo], mode: str, weights: NeedWeights
) -> tuple[list[ScheduledWard], ServicePointRegistry]:
    """F9: the F4-flagged sections as scheduled-supply candidates, each with a stop at its
    estimated centre (an officer replaces it by registering a real standpipe)."""
    if mode == "none":
        return [], ServicePointRegistry()
    if mode not in CFG.scheduled_modes:
        raise ValueError(f"scheduled must be one of {CFG.scheduled_modes}")
    wards, points = [], []
    for info in sections.values():
        if not info.f4_flagged:
            continue
        wards.append(ScheduledWard(info.group, info.people * info.wad, info.need_weight(weights)))
        if info.lat is not None and info.lng is not None:
            points.append(
                ServicePoint(
                    point_id=f"centre:{info.section}",
                    ward_id=info.group,
                    name=f"{info.section} (estimated centre)",
                    lat=info.lat,
                    lng=info.lng,
                    registered_by="system",
                    reason="estimated centre of the section; replace with a real standpipe",
                )
            )
    return wards, ServicePointRegistry(tuple(points))


def outages_from(
    options: SectionOptions,
    sections: Mapping[str, SectionInfo],
    facilities: Mapping[str, list[dict[str, str]]],
) -> tuple[list[outage.OutageEvent], list[outage.CriticalStop], dict[str, tuple[float, float]]]:
    """F10: outage notices on the day as outage events by section, and the mapped critical
    facilities of the cut sections as stops to serve first."""
    events: list[outage.OutageEvent] = []
    stops: list[outage.CriticalStop] = []
    where: dict[str, tuple[float, float]] = {}
    for o in options.outages:
        areas = {n: float(p) for n, p in dict(o["areas"]).items() if n in sections}  # type: ignore[arg-type]
        if not areas:
            continue
        start = datetime.fromisoformat(str(o["start"]))
        end = datetime.fromisoformat(str(o["end"])) if o.get("end") else None
        events.append(
            outage.OutageEvent(
                outage_id=str(o["outage_id"]),
                ward_ids=tuple(SECTION_PREFIX + n for n in sorted(areas)),
                start=start,
                end=end,
                source=str(o.get("source", "notice")),
                reason=str(o.get("reason", "")),
                created_by=str(o.get("created_by", "notice")),
                people_affected=sum(areas.values()),
                planned_hours=(end - start).total_seconds() / 3600 if end else None,
            )
        )
        for name in sorted(areas):
            for f in facilities.get(name, ()):
                if f["category"] in CFG.outage_critical_categories and f["osm_ref"] not in where:
                    stops.append(
                        outage.CriticalStop(
                            f["osm_ref"], f["name"] or f["category"],
                            SECTION_PREFIX + name, CFG.critical_stop_litres,
                        )
                    )  # fmt: skip
                    where[f["osm_ref"]] = (float(f["lat"]), float(f["lon"]))
    return events, stops, where


_STEPS: dict[tuple, tuple[list[planner.PlannerBooking], dict[str, fair_queue.QueueState]]] = {}
_STEPS_LOCK = threading.Lock()


def rebalanced(
    base: Mapping[str, int], pending: Iterable[planner.PlannerBooking]
) -> dict[str, int]:
    """B: the same total trips shared over the stations by the bookings waiting at each today,
    each station kept between CFG.rebalance_min_share and CFG.rebalance_max_share of its usual
    trips (largest remainder). Tankers are taken to be movable between stations each morning:
    ASSUMED (HMWSSB does not publish how it moves tankers)."""
    total = sum(base.values())
    want: Counter[str] = Counter(p.station for p in pending)
    grand = sum(want[s] for s in base) or 1
    exact = {
        s: min(
            CFG.rebalance_max_share * base[s],
            max(CFG.rebalance_min_share * base[s], total * want[s] / grand),
        )
        for s in base
    }
    out = {s: max(1 if base[s] else 0, math.floor(v)) for s, v in exact.items()}
    spare = total - sum(out.values())
    order = sorted(base, key=lambda s: (-(exact[s] - math.floor(exact[s])), -want[s], s))
    i = 0
    while spare > 0 and order:  # give the rest where the bounds allow, most wanted first
        s = order[i % len(order)]
        if out[s] < CFG.rebalance_max_share * base[s] or i >= 3 * len(order):
            out[s] += 1
            spare -= 1
        i += 1
    while spare < 0:  # rounding up to 1 trip went over: take back from the largest
        s = max(out, key=lambda k: (out[k] - CFG.rebalance_min_share * base[k], k))
        out[s] -= 1
        spare += 1
    return out


def _day_inputs(
    root: Path,
    st: _Static,
    day: date,
    weights: NeedWeights,
    options: SectionOptions,
    plan_id: str,
    pending: list[planner.PlannerBooking],
    states: Mapping[str, fair_queue.QueueState],
    debts: Iterable[DebtAccount],
    final: bool,
    service: Mapping[str, float] | None = None,
) -> tuple[planner.PlanInputs, list[tuple[str, int]], list[planner.PlannerBooking]]:
    totals = month_totals(root, estimate_year(day), day.month)
    fresh, left_out = make_bookings(st.sections, totals, day, options, st.facilities, st.commercial)
    if final and options.live:
        # A section with real bookings is planned from them alone: its estimated bookings of the
        # day and the estimated ones carried over from the days before are left out.
        real = [live_booking(b) for b in options.live]
        groups = {b.group for b in real if b.group.removeprefix(SECTION_PREFIX) in st.sections}
        fresh = [b for b in fresh if b.group not in groups] + [b for b in real if b.group in groups]
        pending = [p for p in pending if p.booking.group not in groups]
    expiry = SANDBOX_CONFIG.booking_expiry_days
    kept = [p for p in pending if (day - p.booking.arrived_at.astimezone(IST).date()).days < expiry]
    new = [planner.PlannerBooking(b, st.sections[b.group.removeprefix(SECTION_PREFIX)].station)
           for b in fresh]  # fmt: skip
    scheduled, registry = scheduled_for(st.sections, options.scheduled, weights)
    events, stops, where = (
        outages_from(options, st.sections, st.facilities) if final else ([], [], {})
    )
    pending_all = kept + new
    service = service or {}
    inputs = planner.PlanInputs(
        plan_id=plan_id,
        day=day,
        capacity=rebalanced(st.capacity, pending_all) if options.rebalance else st.capacity,
        pending=pending_all,
        entitlement={
            s.group: s.entitlement(weights) * service.get(s.group, 1.0)
            for s in st.sections.values()
        },
        queue_states=dict(states),
        debts={a.account_id: a for a in debts} if final else {},
        scheduled=scheduled,
        outages=events,
        critical_stops=stops,
        station_km=st.pairs,
        critical_locations=where,
        registry=registry,
    )
    return inputs, left_out, kept


def plan_inputs(
    root: Path,
    day: date,
    weights: NeedWeights,
    plan_id: str,
    debts: Iterable[DebtAccount] = (),
    scenario: str = "fleet",
    options: SectionOptions | None = None,
    plan_now: Callable[[date], datetime] | None = None,
) -> tuple[planner.PlanInputs, dict[str, SectionInfo], list[tuple[str, int]], dict[str, int]]:
    """Inputs for the plan of `day`. With carry-over the days before it (back `carry_days`, inside
    2025) are planned first, so the bookings and fair-queue credits left over arrive with it."""
    options = options or SectionOptions()
    if day < date(PLAN_YEAR, 1, 1):
        raise SectionPlanUnavailable(
            f"Section plans use the {PLAN_YEAR} section names; choose a day from {PLAN_YEAR} on"
        )
    st = _static(str(root), scenario)
    now_of = plan_now or (lambda d: datetime(d.year, d.month, d.day, 5, 0, tzinfo=IST))
    back = max(CFG.carry_days, WEEKLY.window_days if options.responsive else 0)
    start = max(date(PLAN_YEAR, 1, 1), day - timedelta(days=back)) if options.carry_over else day
    pending: list[planner.PlannerBooking] = []
    states: dict[str, fair_queue.QueueState] = {}
    gate = SectionGate(st.sections)
    key_base = (
        str(root), scenario, weights, options.priority, options.scheduled, start,
        options.rebalance, options.responsive,
    )  # fmt: skip
    history: list[dict[str, tuple[int, int]]] = []  # per replayed day: group -> (booked, served)
    d = start
    while d < day:
        key = (*key_base, d)
        with _STEPS_LOCK:
            hit = _STEPS.get(key)
        if hit is None:
            factors = service_factors(history) if options.responsive else None
            inputs, _, _ = _day_inputs(
                root, st, d, weights, options, f"carry-{d.isoformat()}", pending, states, (),
                False, factors,
            )  # fmt: skip
            plan = planner.build_plan(inputs, gate, _NullLedger(), now_of(d))
            served = {b.booking_id for sp in plan.stations.values() for b in sp.served}
            before = {p.booking.booking_id for p in pending}
            record: dict[str, list[int]] = defaultdict(lambda: [0, 0])
            for p in inputs.pending:
                if p.booking.booking_id not in before:
                    record[p.booking.group][0] += 1
                if p.booking.booking_id in served:
                    record[p.booking.group][1] += 1
            hit = (
                [p for p in inputs.pending if p.booking.booking_id not in served],
                dict(plan.queue_states),
                {g: (b, s) for g, (b, s) in record.items()},
            )
            with _STEPS_LOCK:
                _STEPS[key] = hit
                while len(_STEPS) > 64:
                    _STEPS.pop(next(iter(_STEPS)))
        pending, states = list(hit[0]), dict(hit[1])
        history.append(dict(hit[2]))
        d += timedelta(days=1)
    final_factors = service_factors(history) if options.responsive else None
    inputs, left_out, carried = _day_inputs(
        root, st, day, weights, options, plan_id, pending, states, debts, True, final_factors
    )
    tiers = Counter(p.booking.tier for p in inputs.pending)
    notes = {
        "carried_bookings": len(carried),
        "live_bookings": sum(1 for p in inputs.pending if not _estimated(p.booking.booking_id)),
        "live_sections": len(
            {p.booking.group for p in inputs.pending if not _estimated(p.booking.booking_id)}
        ),
        "tier0": tiers[0],
        "tier1": tiers[1],
        "tier2": tiers[2],
        "commercial": sum(1 for p in inputs.pending if p.booking.category == "commercial"),
        "scheduled_sections": len(inputs.scheduled),
        "outage_events": len(inputs.outages),
        "critical_stops": len(inputs.critical_stops),
    }
    return inputs, st.sections, left_out, notes


def supplied_inputs(
    root,
    day,
    weights,
    plan_id,
    debts=(),
    scenario="fleet",
    options=None,
    plan_now=None,
    *,
    bookings,
):
    """Current section bookings; no synthetic arrivals or implicit historical carry-over."""
    st = _static(str(root), scenario)
    options = options or SectionOptions()
    pending = []
    for row in bookings:
        booking = fair_queue.QueueBooking(
            booking_id=row["booking_id"],
            group=SECTION_PREFIX + row["section"],
            arrived_at=datetime.fromisoformat(row["arrived_at"]),
            tier=row["tier"],
            consumer_id=row["consumer_id"],
            category=row["category"],
        )
        if (
            day - booking.arrived_at.astimezone(IST).date()
        ).days >= SANDBOX_CONFIG.booking_expiry_days:
            raise SectionPlanUnavailable(
                "Supplied waiting booking has expired under the queue policy"
            )
        pending.append(planner.PlannerBooking(booking, st.sections[row["section"]].station))
    scheduled, registry = scheduled_for(st.sections, options.scheduled, weights)
    events, stops, where = outages_from(options, st.sections, st.facilities)
    inputs = planner.PlanInputs(
        plan_id=plan_id,
        day=day,
        capacity=st.capacity,
        pending=pending,
        entitlement={s.group: s.entitlement(weights) for s in st.sections.values()},
        debts={a.account_id: a for a in debts},
        scheduled=scheduled,
        registry=registry,
        outages=events,
        critical_stops=stops,
        critical_locations=where,
        station_km=st.pairs,
    )
    tiers = Counter(p.booking.tier for p in pending)
    notes = {
        "carried_bookings": 0,
        "tier0": tiers[0],
        "tier1": tiers[1],
        "tier2": tiers[2],
        "commercial": sum(p.booking.category == "commercial" for p in pending),
        "scheduled_sections": len(scheduled),
        "outage_events": len(events),
        "critical_stops": len(stops),
    }
    return inputs, st.sections, [], notes


def trips_per_day() -> int:
    return int(SANDBOX_CONFIG.fleet_tankers * SANDBOX_CONFIG.trips_per_tanker_day)


WEIGHTS_REVIEWED = "data/derived/crosswalk/section_ward_building_weights_reviewed.csv"
WEIGHTS = "data/derived/crosswalk/section_ward_building_weights.csv"
_WARD_WEIGHTS: dict[str, tuple[float, dict[str, dict[str, float]]]] = {}


def ward_weights(root: Path) -> dict[str, dict[str, float]]:
    """Share of each section's buildings in each ward (the reviewed build when present)."""
    path = root / (WEIGHTS_REVIEWED if (root / WEIGHTS_REVIEWED).exists() else WEIGHTS)
    mtime = path.stat().st_mtime
    cached = _WARD_WEIGHTS.get(str(path))
    if cached is None or cached[0] != mtime:
        table: dict[str, dict[str, float]] = defaultdict(dict)
        with path.open(encoding="utf-8", newline="") as handle:
            for r in csv.DictReader(handle):
                table[r["section"]][r["ward_id"]] = float(r["weight"])
        _WARD_WEIGHTS[str(path)] = (mtime, dict(table))
    return _WARD_WEIGHTS[str(path)][1]


def ward_totals(
    root: Path, group_totals: Mapping[str, Mapping[str, int]]
) -> tuple[dict[str, dict[str, float]], dict[str, float]]:
    """Served and waiting bookings of the sections, shared over wards by building share (an
    estimate, DERIVED_APPROXIMATE), and what could not be placed on any ward."""
    weights = ward_weights(root)
    wards: dict[str, dict[str, float]] = {}
    unplaced = {"served": 0.0, "waiting": 0.0}
    for group, t in group_totals.items():
        shares = weights.get(group.removeprefix(SECTION_PREFIX))
        if not shares:
            unplaced["served"] += t["served"]
            unplaced["waiting"] += t["waiting"]
            continue
        for ward, w in shares.items():
            row = wards.setdefault(ward, {"served": 0.0, "waiting": 0.0})
            row["served"] += t["served"] * w
            row["waiting"] += t["waiting"] * w
    rounded = {w: {k: round(v, 1) for k, v in r.items()} for w, r in wards.items()}
    return rounded, {k: round(v, 1) for k, v in unplaced.items()}


def outages_from_notices(
    root: Path, notices: Iterable[Mapping[str, object]], day: date
) -> list[dict[str, object]]:
    """Supply notices (F15, each naming wards) that overlap `day` as outages by section: a section
    is cut when at least `outage_min_building_share` of its buildings are in the notice's wards;
    its people affected are its estimated people times that share. Stored in the plan's recipe."""
    sections = _static(str(root), "fleet").sections
    shares = ward_weights(root)
    day_start = datetime.combine(day, time(0, 0), tzinfo=IST)
    day_end = day_start + timedelta(days=1)
    out: list[dict[str, object]] = []
    for n in sorted(notices, key=lambda n: str(n["id"])):
        start, end = n["start"], n["end"]
        assert isinstance(start, datetime) and isinstance(end, datetime)
        if end <= day_start or start >= day_end:
            continue
        wards = set(n["ward_ids"])  # type: ignore[call-overload]
        areas: dict[str, int] = {}
        for name, by_ward in sorted(shares.items()):
            if name not in sections:
                continue
            share = sum(w for ward, w in by_ward.items() if ward in wards)
            if share >= CFG.outage_min_building_share:
                areas[name] = round(sections[name].people * share)
        if areas:
            out.append(
                {
                    "outage_id": f"notice-{n['id']}",
                    "areas": areas,
                    "start": start.isoformat(),
                    "end": end.isoformat(),
                    "source": "notice",
                    "reason": "supply notice (F15)",
                    "created_by": "notice",
                }
            )
    return out


CELLS = "data/derived/crosswalk/section_cells.geojson"


@lru_cache(maxsize=2)
def _cells(root: str) -> list[tuple[str, object]]:
    from shapely.geometry import shape

    data = json.loads((Path(root) / CELLS).read_text(encoding="utf-8"))
    return [(f["properties"]["section"], shape(f["geometry"])) for f in data["features"]]


def section_of_point(root: Path, lat: float, lng: float) -> str | None:
    """The section whose approximate area holds the point (a delivery stop), as its group id."""
    from shapely.geometry import Point

    point = Point(lng, lat)
    for name, cell in _cells(str(root)):
        if cell.contains(point):  # type: ignore[attr-defined]
            return SECTION_PREFIX + name
    return None


def booked_on(inputs: planner.PlanInputs, day: date) -> dict[str, int]:
    """Bookings of a plan that arrived on `day` (Hyderabad time), per section group: the day's
    estimates from monthly totals, or the real bookings of a section that has them. What a
    section is owed when the day is closed (F11); carried-over bookings were owed before."""
    out: dict[str, int] = defaultdict(int)
    for p in inputs.pending:
        if p.booking.arrived_at.astimezone(IST).date() == day:
            out[p.booking.group] += 1
    return dict(out)


def static_sections(root: Path) -> dict[str, SectionInfo]:
    """The section table (cached), for callers outside this module."""
    return _static(str(root), "fleet").sections
