"""Plans for the API (Wave 1): A7's daily planner on P2's committed replay, gated by T9 (F17).

A plan is built for one day of the replay main_2025 (Mar-Jul 2025, tight, seed 0; monthly
totals REAL, daily arrivals SYNTHETIC), so every plan is SIMULATION. The day's inputs (pending
bookings carried over, queue states) come from `scripts/sandbox/build_planner_replay.py`
`replay()`, unchanged: it still scores with A7's ProvisionalGate so its committed outputs do not
move. The gate only sets `flags` (served and waiting do not depend on it), so the day's inputs
are the same under any gate; this module re-runs `build_plan` on them with `T9Gate`.

An officer may try other need weights for one plan (`weights` in the recipe). A weighted plan is
its own replay run, because the weights change who is served each day and so what carries over
to the next; it has its own id and digest and is rebuilt like any other plan.

The planner is deterministic, so a plan is stored as its `recipe` (no pickling) and rebuilt on
read; the caller compares the rebuilt digest with the stored one. Building writes no ledger
entry: build_plan's `plan_created` event is returned in `events` for the caller to write once,
after the plan is stored (a rebuild never writes it again).
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import sys
import threading
from collections import Counter, OrderedDict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime, timedelta, timezone
from functools import lru_cache
from types import ModuleType
from typing import Any

from app.config.allocation import ALLOCATION_CONFIG
from app.config.confidence import CONFIDENCE_CONFIG
from app.config.env import REPO_ROOT
from app.config.plans import PLAN_STORE_CONFIG
from app.services import (
    booking_groups,
    confidence,
    fair_queue,
    planner,
    section_plan,
    service_models,
    water_debt,
)
from app.services.scheduled_supply import ServicePoint, ServicePointRegistry
from app.services.service_models import NeedWeights

SOURCE = "planner_replay"
SUPPLIED = "supplied_bookings"
SECTION = "section_month"  # a day planned by section from one month's real totals divided by days
SECTION_GATE = "SECTION"
IST = timezone(timedelta(hours=5, minutes=30))
GATE = "T9"
_MODULE = "jallekha_planner_replay"  # private name: tests load the script under its own name


class ReplayDayUnavailable(LookupError):
    """The day is outside the replay window: there is no data to plan it from."""


class InvalidBookings(ValueError):
    """The supplied bookings cannot be planned; the message lists what is wrong."""


class PlanRebuildError(RuntimeError):
    """A stored plan cannot be rebuilt as it was (unknown recipe or a different digest)."""


@dataclass(frozen=True)
class BuiltPlan:
    inputs: planner.PlanInputs
    plan: planner.DailyPlan
    basis: dict[str, str]
    recipe: dict[str, Any]
    events: tuple[tuple[str, dict[str, Any], str], ...]  # (entry type, payload, actor)


class _Events:
    """A LedgerPort that keeps build_plan's events instead of writing them."""

    def __init__(self) -> None:
        self.events: list[tuple[str, dict[str, Any], str]] = []

    def append(self, entry_type: str, payload: Mapping[str, Any], actor: str) -> Any:
        self.events.append((entry_type, dict(payload), actor))
        return None


def _script() -> ModuleType:
    module = sys.modules.get(_MODULE)
    if module is None:
        path = REPO_ROOT / PLAN_STORE_CONFIG.replay_script
        spec = importlib.util.spec_from_file_location(_MODULE, path)
        assert spec and spec.loader, path
        module = importlib.util.module_from_spec(spec)
        sys.modules[_MODULE] = module  # dataclasses in the script look their module up here
        spec.loader.exec_module(module)
    return module


def replay_window() -> tuple[date, date]:
    """First and last day of the replay (read from the script's constants; no data loaded)."""
    script = _script()
    months = script.build_sandbox.REPLAYS[script.REPLAY]
    first = date(*months[0], 1)
    return first, first + timedelta(days=script.build_sandbox._days_in(months) - 1)


_SETUP_LOCK = threading.Lock()
_SETUP: Any = None


def _setup() -> Any:
    """The replay set-up, loaded once (about 12 s) and shared by every cursor."""
    global _SETUP
    with _SETUP_LOCK:
        if _SETUP is None:
            _SETUP = _script().load(REPO_ROOT)
        return _SETUP


def _entitlement(weights: NeedWeights | None) -> dict[str, float] | None:
    """Entitlement per group under other weights; None means the replay's own (default)."""
    if weights is None:
        return None
    needs = service_models.build_ward_needs(service_models.load_evidence(REPO_ROOT), [], weights)
    entitlement, _fallback = booking_groups.group_entitlements(needs, _setup().ctx.mapping)
    return entitlement


class _Replay:
    """A cursor over the replay days for one set of weights. Asking for an earlier day than the
    cursor restarts the replay (about 0.2 s a day)."""

    def __init__(self, weights: NeedWeights | None) -> None:
        self._lock = threading.Lock()
        self._weights = weights
        self._entitlement: dict[str, float] | None = None
        self._days: Any = None
        self._last: Any = None

    def inputs(self, day: date) -> planner.PlanInputs:
        with self._lock:
            script, setup = _script(), _setup()
            if self._last is None or day < self._last.day:
                if self._entitlement is None:
                    self._entitlement = _entitlement(self._weights)
                self._days = script.replay(setup, entitlement=self._entitlement)
                self._last = None
            while self._last is None or self._last.day < day:
                self._last = next(self._days)
            return self._last.inputs


_REPLAYS: OrderedDict[NeedWeights | None, _Replay] = OrderedDict()
_REPLAYS_LOCK = threading.Lock()


def _replay_for(weights: NeedWeights | None) -> _Replay:
    """The cursor for these weights; the three most recently used are kept."""
    with _REPLAYS_LOCK:
        replay = _REPLAYS.get(weights)
        if replay is None:
            replay = _REPLAYS[weights] = _Replay(weights)
        _REPLAYS.move_to_end(weights)
        while len(_REPLAYS) > PLAN_STORE_CONFIG.weighted_replays_kept:
            _REPLAYS.popitem(last=False)
        return replay


@lru_cache(maxsize=1)
def _tables(mtimes: tuple[float, ...]) -> confidence.SignalTables:
    return confidence.SignalTables.from_files(REPO_ROOT)


def t9_gate(threshold: float) -> confidence.T9Gate:
    paths = (CONFIDENCE_CONFIG.evidence_path, CONFIDENCE_CONFIG.sections_path)
    tables = _tables(tuple((REPO_ROOT / p).stat().st_mtime for p in paths))
    return confidence.T9Gate(tables, threshold=threshold)


def _basis(
    threshold: float, weights: NeedWeights | None = None, supplied: int | None = None
) -> dict[str, str]:
    script = _script()
    chosen = weights or NeedWeights.default()
    return {
        "plan": (
            f"Plan from {supplied} bookings supplied for the day, not the replay: bookings as "
            "supplied (not verified here); capacity ASSUMED (A8 fleet scenario "
            f"{script.REPLAY}, {script.SCENARIO}); need DERIVED from Census 2011"
        )
        if supplied is not None
        else (
            f"SIMULATION (A7 replay {script.REPLAY}, {script.SCENARIO}, seed {script.SEED}; "
            "daily arrivals SYNTHETIC, monthly totals REAL)"
        ),
        "effective_entitlement": "DERIVED (A2 Census 2011 need; A3 fallback median where flagged)",
        "weights": (
            "ASSUMED policy weights"
            + (" chosen by an officer for this plan" if weights else " (configured defaults)")
            + f": need weight = 1 + {chosen.wad:g} x water-access deficit"
            + f" + {chosen.cad:g} x no-phone share + {chosen.hardship:g} x hardship"
        ),
        "flags": (
            f"DERIVED (T9 gate: min of available signals; threshold {threshold:.2f} "
            f"{CONFIDENCE_CONFIG.threshold_basis})"
        ),
    }


def _weight_suffix(weights: NeedWeights) -> str:
    return f"-w{weights.wad:g}-{weights.cad:g}-{weights.hardship:g}"


def _weighted_id(day: date, weights: NeedWeights) -> str:
    return f"replay-{day.isoformat()}{_weight_suffix(weights)}"


def plan_id_for(day: date, weights: NeedWeights | None = None) -> str:
    """The id of the plan for a day and weights (the default plan when they are the defaults)."""
    weights = weights.validated() if weights is not None else None
    if weights is None or weights == NeedWeights.default():
        return f"replay-{day.isoformat()}"
    return _weighted_id(day, weights)


def _recipe_weights(recipe: Mapping[str, Any]) -> NeedWeights | None:
    """The weights in a recipe, or None for the defaults (a recipe never stores the defaults)."""
    raw = recipe.get("weights")
    if raw is None:
        return None
    return NeedWeights(float(raw["wad"]), float(raw["cad"]), float(raw["hardship"])).validated()


def _build(recipe: dict[str, Any]) -> BuiltPlan:
    if recipe.get("source") == SUPPLIED:
        return _build_supplied(recipe)
    if recipe.get("source") == SECTION:
        return _build_section(recipe)
    day = date.fromisoformat(recipe["day"])
    first, last = replay_window()
    if not first <= day <= last:
        raise ReplayDayUnavailable(
            f"No replay data for {day.isoformat()}: the replay covers {first} to {last}"
        )
    threshold = float(recipe["threshold"])
    weights = _recipe_weights(recipe)
    inputs = _replay_for(weights).inputs(day)
    if weights is not None:
        inputs = replace(inputs, plan_id=_weighted_id(day, weights))
    events = _Events()
    plan = planner.build_plan(inputs, t9_gate(threshold), events, _script().planner_now(day))
    return BuiltPlan(inputs, plan, _basis(threshold, weights), recipe, tuple(events.events))


def build_replay_plan(
    day: date, threshold: float | None = None, weights: NeedWeights | None = None
) -> BuiltPlan:
    """The DRAFT plan for a replay day, gated by T9 (default: the configured threshold).

    `weights` other than the configured defaults make a separate, weighted plan; weights equal to
    the defaults make the default plan."""
    script = _script()
    recipe = {
        "source": SOURCE,
        "replay": script.REPLAY,
        "scenario": script.SCENARIO,
        "seed": script.SEED,
        "day": day.isoformat(),
        "gate": GATE,
        "threshold": CONFIDENCE_CONFIG.threshold if threshold is None else threshold,
    }
    if weights is not None:
        weights = weights.validated()
        if weights != NeedWeights.default():
            recipe["weights"] = weights.as_dict()
    return _build(recipe)


def rebuild(recipe: Mapping[str, Any]) -> BuiltPlan:
    """Rebuild a stored plan from its recipe. Only recipes this module wrote can be rebuilt."""
    if recipe.get("source") == SECTION:
        return _rebuild_section(recipe)
    script = _script()
    supplied = recipe.get("source") == SUPPLIED
    expected = {
        "source": SUPPLIED if supplied else SOURCE,
        "replay": script.REPLAY,
        "scenario": script.SCENARIO,
        "gate": GATE,
    }
    if not supplied:
        expected["seed"] = script.SEED
    differs = sorted(k for k, v in expected.items() if recipe.get(k) != v)
    try:
        _recipe_weights(recipe)
    except (KeyError, TypeError, ValueError) as exc:
        raise PlanRebuildError(f"Plan recipe has unusable weights: {exc}") from exc
    if differs or "day" not in recipe or "threshold" not in recipe:
        raise PlanRebuildError(
            f"Plan recipe cannot be rebuilt here (fields {differs or ['day', 'threshold']}); "
            f"this build makes {expected}"
        )
    try:
        return _build(dict(recipe))
    except InvalidBookings as exc:
        raise PlanRebuildError(f"Stored bookings can no longer be planned: {exc}") from exc


def _served(plan: planner.DailyPlan) -> Counter[str]:
    return Counter(b.group for station in plan.stations.values() for b in station.served)


_NAMES: dict[str, Any] = {"mtime": None, "names": {}}


def _ward_names() -> dict[str, str]:
    path = REPO_ROOT / service_models.EVIDENCE
    mtime = path.stat().st_mtime
    if _NAMES["mtime"] != mtime:
        rows = service_models.load_evidence(REPO_ROOT)
        _NAMES.update(mtime=mtime, names={r["ward_id"]: r["ward_name"] for r in rows})
    return _NAMES["names"]


def group_names(groups: Sequence[str]) -> dict[str, str | None]:
    """A readable name per booking group: the ward name (Census-linked evidence file) or the
    HMWSSB section name. A ward without a name stays None, never invented."""
    wards = _ward_names()
    out: dict[str, str | None] = {}
    for group in groups:
        if group.startswith(booking_groups.WARD_PREFIX):
            out[group] = wards.get(group.removeprefix(booking_groups.WARD_PREFIX))
        elif group.startswith("section:"):
            out[group] = group.removeprefix("section:")
        else:
            out[group] = None
    return out


def compare_to_default(built: BuiltPlan, top: int = 10) -> dict[str, Any]:
    """Who gains and who loses booked trips under this plan's weights, against the default plan
    for the same day. Same trips, redistributed, so the changes sum to zero."""
    if _recipe_weights(built.recipe) is None:
        raise ValueError("This plan uses the default weights: there is nothing to compare")
    default = _build({k: v for k, v in built.recipe.items() if k != "weights"})
    before, after = _served(default.plan), _served(built.plan)
    names = group_names(sorted(set(before) | set(after)))
    rows = [
        {
            "group": group,
            "name": names[group],
            "served_default": before[group],
            "served_weighted": after[group],
            "change": after[group] - before[group],
        }
        for group in sorted(set(before) | set(after))
        if after[group] != before[group]
    ]
    return {
        "against": default.plan.plan_id,
        "day": built.recipe["day"],
        "weights": dict(built.recipe["weights"]),
        "default_weights": NeedWeights.default().as_dict(),
        "gainers": sorted((r for r in rows if r["change"] > 0), key=lambda r: -r["change"])[:top],
        "losers": sorted((r for r in rows if r["change"] < 0), key=lambda r: r["change"])[:top],
        "all_changes": rows,
        "basis": (
            "DERIVED (same day, same trips; only the need weights differ)"
            if built.recipe.get("source") == SECTION
            else "SIMULATION (same replay day, same trips; only the need weights differ)"
        ),
    }


# --- plans from supplied bookings -------------------------------------------------------------

_BOOKING_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 _.:/()#-]{0,79}$")
_FIELDS = {"booking_id", "section", "arrived_at", "consumer_id", "category", "tier"}
_SHOWN_PROBLEMS = 10
_ISO_HINT = "arrived_at must be an ISO date and time, for example 2026-10-03T05:30:00+05:30"


def normalise_bookings(day: date, raw: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Check supplied bookings and put them in one canonical order, so the same bookings in any
    order are the same plan. Raises InvalidBookings listing what is wrong (up to 10 problems)."""
    top = PLAN_STORE_CONFIG.max_supplied_bookings
    if not isinstance(raw, Sequence) or isinstance(raw, str | bytes) or len(raw) == 0:
        raise InvalidBookings("Supply at least one booking")
    if len(raw) > top:
        raise InvalidBookings(f"Supply at most {top} bookings for one plan (got {len(raw)})")
    setup = _setup()
    home, mapping, entitlement = setup.ctx.network.home, setup.ctx.mapping, setup.ctx.entitlement
    categories = sorted(ALLOCATION_CONFIG.booking_caps)
    problems: list[str] = []
    seen: set[str] = set()
    rows: list[tuple[datetime, str, dict[str, Any]]] = []
    for number, item in enumerate(raw, 1):
        found: list[str] = []
        if not isinstance(item, Mapping):
            problems.append(f"booking {number}: not an object")
            continue
        extra = sorted(set(item) - _FIELDS)
        if extra:
            found.append(f"unknown field {', '.join(extra)}")
        booking_id = item.get("booking_id")
        if not isinstance(booking_id, str) or not _BOOKING_ID.match(booking_id):
            found.append("booking_id must be 1 to 80 letters, digits, spaces or _ . : / ( ) # -")
        elif booking_id in seen:
            found.append(f"booking_id {booking_id} appears twice")
        else:
            seen.add(booking_id)
        section = item.get("section")
        if (
            not isinstance(section, str)
            or section not in home
            or booking_groups.group_for(section, mapping) not in entitlement
        ):
            found.append("section is not an HMWSSB section with a station and need data")
        arrived_at = item.get("arrived_at")
        moment: datetime | None = None
        if not isinstance(arrived_at, str):
            found.append(_ISO_HINT)
        else:
            try:
                moment = datetime.fromisoformat(arrived_at.replace("Z", "+00:00"))
            except ValueError:
                found.append(_ISO_HINT)
            else:
                if moment.tzinfo is None:
                    found.append("arrived_at needs a time zone, for example +05:30")
                    moment = None
                elif moment.astimezone(IST).date() > day:
                    found.append(f"arrived_at is after the plan day {day.isoformat()}")
        consumer = item.get("consumer_id", booking_id)
        if not isinstance(consumer, str) or not 1 <= len(consumer) <= 64:
            found.append("consumer_id must be 1 to 64 characters")
        category = item.get("category", "domestic")
        if category not in ALLOCATION_CONFIG.booking_caps:
            found.append(f"category must be one of {', '.join(categories)}")
        tier = item.get("tier", 2)
        if isinstance(tier, bool) or tier not in (0, 1, 2):
            found.append("tier must be 0 (critical facility), 1 (no water on premises) or 2")
        if found:
            problems.append(f"booking {number}: " + "; ".join(found))
        elif moment is not None:
            rows.append(
                (
                    moment.astimezone(UTC),
                    booking_id,
                    {
                        "booking_id": booking_id,
                        "section": section,
                        "arrived_at": moment.isoformat(),
                        "consumer_id": consumer,
                        "category": category,
                        "tier": tier,
                    },
                )
            )
    if problems:
        more = len(problems) - _SHOWN_PROBLEMS
        shown = problems[:_SHOWN_PROBLEMS]
        if more > 0:
            shown.append(f"and {more} more bookings with problems")
        raise InvalidBookings(" | ".join(shown))
    rows.sort(key=lambda r: (r[0], r[1]))
    return [r[2] for r in rows]


def normalise_stops(stops: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Registered delivery stops with a ward, as a plan keeps them: by stop id, four fields."""
    rows = [
        {
            "stop_id": str(s["stop_id"]),
            "ward_id": str(s["ward_id"]),
            "lat": float(s["lat"]),
            "lon": float(s["lon"]),
        }
        for s in stops
        if s.get("ward_id")
    ]
    return sorted(rows, key=lambda s: s["stop_id"])


def normalise_debts(debts: Sequence[water_debt.DebtAccount]) -> list[dict[str, Any]]:
    """Accounts that still owe water, by id (an account at 0 changes no turns, so it is left
    out and does not change the plan id)."""
    debts = [a for a in debts if a.debt_litres > 0]
    return [water_debt.account_as_dict(a) for a in sorted(debts, key=lambda a: a.account_id)]


def supplied_plan_id(
    day: date,
    bookings: Sequence[Mapping[str, Any]],
    weights: NeedWeights | None = None,
    stops: Sequence[Mapping[str, Any]] = (),
    debts: Sequence[water_debt.DebtAccount] = (),
) -> str:
    """`plan-<day>-<8 hex of the bookings>`, plus the weights when they are not the defaults.

    Registered stops and debt accounts change the plan, so when there are any they are hashed
    with the bookings (a plan without them keeps the id it always had)."""
    rows = normalise_bookings(day, bookings)
    extras = {"stops": normalise_stops(stops), "debts": normalise_debts(debts)}
    content: Any = {"bookings": rows, **extras} if any(extras.values()) else rows
    blob = json.dumps(content, sort_keys=True, separators=(",", ":")).encode()
    plan_id = f"plan-{day.isoformat()}-{hashlib.sha256(blob).hexdigest()[:8]}"
    weights = weights.validated() if weights is not None else None
    if weights is not None and weights != NeedWeights.default():
        plan_id += _weight_suffix(weights)
    return plan_id


def build_supplied_plan(
    day: date,
    bookings: Sequence[Mapping[str, Any]],
    threshold: float | None = None,
    weights: NeedWeights | None = None,
    stops: Sequence[Mapping[str, Any]] = (),
    debts: Sequence[water_debt.DebtAccount] = (),
) -> BuiltPlan:
    """The DRAFT plan for the bookings an officer supplies for a day, gated by T9.

    Capacity is the same ASSUMED fleet scenario as the replay (there is no live capacity feed)
    and need is Census 2011. Registered delivery stops with a ward are the service points of
    scheduled supply (A4 splits each scheduled ward's litres across its stops), and debt
    accounts saved by closing earlier days raise their groups' turns (A6/A7)."""
    script = _script()
    recipe: dict[str, Any] = {
        "source": SUPPLIED,
        "replay": script.REPLAY,
        "scenario": script.SCENARIO,
        "day": day.isoformat(),
        "gate": GATE,
        "threshold": CONFIDENCE_CONFIG.threshold if threshold is None else threshold,
        "bookings": normalise_bookings(day, bookings),
    }
    if stops_kept := normalise_stops(stops):
        recipe["stops"] = stops_kept
    if debts_kept := normalise_debts(debts):
        recipe["debts"] = debts_kept
    if weights is not None:
        weights = weights.validated()
        if weights != NeedWeights.default():
            recipe["weights"] = weights.as_dict()
    return _build_supplied(recipe)


def _build_supplied(recipe: dict[str, Any]) -> BuiltPlan:
    day = date.fromisoformat(recipe["day"])
    threshold = float(recipe["threshold"])
    weights = _recipe_weights(recipe)
    rows = normalise_bookings(day, recipe["bookings"])
    setup = _setup()
    ctx = setup.ctx
    pending = [
        planner.PlannerBooking(
            fair_queue.QueueBooking(
                booking_id=row["booking_id"],
                group=booking_groups.group_for(row["section"], ctx.mapping),
                arrived_at=datetime.fromisoformat(row["arrived_at"]),
                tier=row["tier"],
                consumer_id=row["consumer_id"],
                category=row["category"],
            ),
            ctx.network.home[row["section"]],
        )
        for row in rows
    ]
    stops = recipe.get("stops", [])
    debts = [water_debt.account_from_dict(d) for d in recipe.get("debts", [])]
    inputs = planner.PlanInputs(
        plan_id=supplied_plan_id(day, rows, weights, stops, debts),
        day=day,
        capacity=setup.capacity,
        pending=pending,
        entitlement=_entitlement(weights) or ctx.entitlement,
        queue_states={},
        debts={a.account_id: a for a in debts},
        scheduled=ctx.scheduled,
        station_km=ctx.network.station_km,
        registry=ServicePointRegistry(
            tuple(
                ServicePoint(
                    point_id=s["stop_id"],
                    ward_id=s["ward_id"],
                    name=s["stop_id"],
                    lat=s["lat"],
                    lng=s["lon"],
                    registered_by="officer",
                    reason="registered delivery stop (F12)",
                )
                for s in stops
            )
        ),
    )
    events = _Events()
    plan = planner.build_plan(inputs, t9_gate(threshold), events, _script().planner_now(day))
    stored = {**recipe, "bookings": rows}
    basis = _basis(threshold, weights, len(rows))
    if stops:
        basis["stops"] = (
            f"{len(stops)} registered delivery stops with a ward (officer-registered; ward "
            "OFFICER or DERIVED from the 2016 ward map); scheduled litres split across a "
            "ward's stops in whole loads (A4); not routed (no fleet given)"
        )
    if debts:
        basis["debts"] = (
            f"{len(debts)} water debt accounts saved by closing earlier days (A6: planned "
            "litres at the ward's stops minus Confirmed deliveries)"
        )
    return BuiltPlan(inputs, plan, basis, stored, tuple(events.events))


def stop_litres(plan: planner.DailyPlan, stop_ids: Sequence[str]) -> dict[str, float]:
    """Scheduled-supply litres the plan gives each of these stops (routed or not)."""
    wanted = set(stop_ids)
    litres = dict.fromkeys(stop_ids, 0.0)
    for stop in plan.special_stops:
        if stop.kind == "scheduled" and stop.place_id in wanted:
            litres[stop.place_id] += stop.litres
    for need in plan.unrouted:
        if need.kind == "scheduled" and need.place_id in wanted:
            litres[need.place_id] += need.litres
    return litres


# --- plans by section from one month's real totals ---------------------------------------------


def section_plan_id(day: date, capacity: str = "fleet", weights: NeedWeights | None = None) -> str:
    """`section-<day>-<capacity>`, plus the weights when they are not the defaults."""
    plan_id = f"section-{day.isoformat()}-{capacity}"
    weights = weights.validated() if weights is not None else None
    if weights is not None and weights != NeedWeights.default():
        plan_id += _weight_suffix(weights)
    return plan_id


def build_section_plan(
    day: date,
    capacity: str = "fleet",
    weights: NeedWeights | None = None,
    debts: Sequence[water_debt.DebtAccount] = (),
) -> BuiltPlan:
    """The DRAFT plan by section for a day of 2025: the month's real booking total of each section
    divided by the days of the month, need = connections x Census-2011 need carried onto the
    section (estimates flagged for an officer's check), trips = the fleet or the `tight`
    scenario (section_plan.py). Nothing is random; the plan is rebuilt from its recipe."""
    if capacity not in section_plan.CAPACITY_SCENARIOS:
        raise InvalidBookings(
            f"capacity must be one of {', '.join(section_plan.CAPACITY_SCENARIOS)}"
        )
    if day.year != section_plan.PLAN_YEAR:
        raise ReplayDayUnavailable(
            f"Section plans are made for days of {section_plan.PLAN_YEAR} (the section names of "
            "the tables); choose a day in that year"
        )
    recipe: dict[str, Any] = {
        "source": SECTION,
        "unit": "section",
        "capacity": capacity,
        "day": day.isoformat(),
        "gate": SECTION_GATE,
    }
    if kept := normalise_debts([d for d in debts if d.account_id.startswith("section:")]):
        recipe["debts"] = kept
    if weights is not None:
        weights = weights.validated()
        if weights != NeedWeights.default():
            recipe["weights"] = weights.as_dict()
    return _build_section(recipe)


def _build_section(recipe: dict[str, Any]) -> BuiltPlan:
    day = date.fromisoformat(recipe["day"])
    weights = _recipe_weights(recipe)
    capacity = recipe["capacity"]
    debts = [water_debt.account_from_dict(d) for d in recipe.get("debts", [])]
    try:
        inputs, sections, left_out = section_plan.plan_inputs(
            REPO_ROOT,
            day,
            weights or NeedWeights.default(),
            section_plan_id(day, capacity, weights),
            debts,
            capacity,
        )
    except section_plan.SectionPlanUnavailable as exc:
        raise ReplayDayUnavailable(str(exc)) from exc
    events = _Events()
    now = datetime(day.year, day.month, day.day, tzinfo=IST).astimezone(UTC) + timedelta(minutes=30)
    plan = planner.build_plan(inputs, section_plan.SectionGate(sections), events, now)
    basis = _basis_section(day, capacity, weights, len(inputs.pending), left_out, sections)
    return BuiltPlan(inputs, plan, basis, recipe, tuple(events.events))


def _basis_section(
    day: date,
    capacity: str,
    weights: NeedWeights | None,
    bookings: int,
    left_out: Sequence[tuple[str, int]],
    sections: Mapping[str, section_plan.SectionInfo],
) -> dict[str, str]:
    chosen = weights or NeedWeights.default()
    estimated = sum(1 for s in sections.values() if s.estimated)
    trips = section_plan.total_trips(REPO_ROOT, capacity)
    capacity_text = (
        "the fleet, 1,150 tankers x 9 trips (ASSUMED, from news)"
        if capacity == "fleet"
        else "the tight scenario: the replay's trips calibrated to the REAL Jun-Aug 2026 delivered "
        "share (DERIVED)"
    )
    return {
        "plan": (
            f"{bookings} bookings for {day.isoformat()}: the real {day.strftime('%B %Y')} total of "
            "each section (REAL, HMWSSB) divided by the days of the month, all tier 2 and domestic "
            f"(HMWSSB publishes neither). {trips} trips a day = {capacity_text}, shared over the "
            "90 ASSUMED stand-in stations by the year's bookings. Not a forecast of that day."
        ),
        "effective_entitlement": (
            "DERIVED (domestic connections from HMWSSB billing x need weight; Census 2011 need "
            f"carried onto the section by building share). {estimated} sections have an ESTIMATED "
            "need or connection count (division or city median) and need an officer's check"
        ),
        "weights": (
            "ASSUMED policy weights"
            + (" chosen by an officer for this plan" if weights else " (configured defaults)")
            + f": need weight = 1 + {chosen.wad:g} x water-access deficit"
            + f" + {chosen.cad:g} x no-phone share + {chosen.hardship:g} x hardship"
        ),
        "flags": "DERIVED (a section whose need or connections are an estimate is flagged)",
    }


def _rebuild_section(recipe: Mapping[str, Any]) -> BuiltPlan:
    expected = {
        "source": SECTION,
        "unit": "section",
        "gate": SECTION_GATE,
    }
    differs = sorted(k for k, v in expected.items() if recipe.get(k) != v)
    if (
        differs
        or recipe.get("capacity") not in section_plan.CAPACITY_SCENARIOS
        or "day" not in recipe
    ):
        raise PlanRebuildError(
            f"Section plan recipe cannot be rebuilt here (fields {differs or ['capacity', 'day']})"
        )
    try:
        _recipe_weights(recipe)
        return _build_section(dict(recipe))
    except (KeyError, TypeError, ValueError) as exc:
        raise PlanRebuildError(f"Section plan recipe is unusable: {exc}") from exc
