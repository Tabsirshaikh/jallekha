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

import importlib.util
import sys
import threading
from collections import Counter, OrderedDict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import date, timedelta
from functools import lru_cache
from types import ModuleType
from typing import Any

from app.config.confidence import CONFIDENCE_CONFIG
from app.config.env import REPO_ROOT
from app.config.plans import PLAN_STORE_CONFIG
from app.services import booking_groups, confidence, planner, service_models
from app.services.service_models import NeedWeights

SOURCE = "planner_replay"
GATE = "T9"
_MODULE = "jallekha_planner_replay"  # private name: tests load the script under its own name


class ReplayDayUnavailable(LookupError):
    """The day is outside the replay window: there is no data to plan it from."""


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


def _basis(threshold: float, weights: NeedWeights | None = None) -> dict[str, str]:
    script = _script()
    chosen = weights or NeedWeights.default()
    return {
        "plan": (
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


def _weighted_id(day: date, weights: NeedWeights) -> str:
    return f"replay-{day.isoformat()}-w{weights.wad:g}-{weights.cad:g}-{weights.hardship:g}"


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
    script = _script()
    expected = {
        "source": SOURCE,
        "replay": script.REPLAY,
        "scenario": script.SCENARIO,
        "seed": script.SEED,
        "gate": GATE,
    }
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
    return _build(dict(recipe))


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
    default = build_replay_plan(date.fromisoformat(built.recipe["day"]), built.recipe["threshold"])
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
        "basis": "SIMULATION (same replay day, same trips; only the need weights differ)",
    }
