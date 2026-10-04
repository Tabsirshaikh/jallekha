"""Plans for the API (Wave 1): A7's daily planner on P2's committed replay, gated by T9 (F17).

A plan is built for one day of the replay main_2025 (Mar-Jul 2025, tight, seed 0; monthly
totals REAL, daily arrivals SYNTHETIC), so every plan is SIMULATION. The day's inputs (pending
bookings carried over, queue states) come from `scripts/sandbox/build_planner_replay.py`
`replay()`, unchanged: it still scores with A7's ProvisionalGate so its committed outputs do not
move. The gate only sets `flags` (served and waiting do not depend on it), so the day's inputs
are the same under any gate; this module re-runs `build_plan` on them with `T9Gate`.

The planner is deterministic, so a plan is stored as its `recipe` (no pickling) and rebuilt on
read; the caller compares the rebuilt digest with the stored one. Building writes no ledger
entry: build_plan's `plan_created` event is returned in `events` for the caller to write once,
after the plan is stored (a rebuild never writes it again).
"""

from __future__ import annotations

import importlib.util
import sys
import threading
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, timedelta
from functools import lru_cache
from types import ModuleType
from typing import Any

from app.config.confidence import CONFIDENCE_CONFIG
from app.config.env import REPO_ROOT
from app.config.plans import PLAN_STORE_CONFIG
from app.services import confidence, planner

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


class _Replay:
    """The replay set-up (loaded once, about 12 s) and a cursor over its days. Asking for an
    earlier day than the cursor restarts the replay (about 0.2 s a day)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._setup: Any = None
        self._days: Any = None
        self._last: Any = None

    def inputs(self, day: date) -> planner.PlanInputs:
        with self._lock:
            script = _script()
            if self._setup is None:
                self._setup = script.load(REPO_ROOT)
            if self._last is None or day < self._last.day:
                self._days, self._last = script.replay(self._setup), None
            while self._last is None or self._last.day < day:
                self._last = next(self._days)
            return self._last.inputs


_REPLAY = _Replay()


@lru_cache(maxsize=1)
def _tables(mtimes: tuple[float, ...]) -> confidence.SignalTables:
    return confidence.SignalTables.from_files(REPO_ROOT)


def t9_gate(threshold: float) -> confidence.T9Gate:
    paths = (CONFIDENCE_CONFIG.evidence_path, CONFIDENCE_CONFIG.sections_path)
    tables = _tables(tuple((REPO_ROOT / p).stat().st_mtime for p in paths))
    return confidence.T9Gate(tables, threshold=threshold)


def _basis(threshold: float) -> dict[str, str]:
    script = _script()
    return {
        "plan": (
            f"SIMULATION (A7 replay {script.REPLAY}, {script.SCENARIO}, seed {script.SEED}; "
            "daily arrivals SYNTHETIC, monthly totals REAL)"
        ),
        "effective_entitlement": "DERIVED (A2 Census 2011 need; A3 fallback median where flagged)",
        "flags": (
            f"DERIVED (T9 gate: min of available signals; threshold {threshold:.2f} "
            f"{CONFIDENCE_CONFIG.threshold_basis})"
        ),
    }


def _build(recipe: dict[str, Any]) -> BuiltPlan:
    day = date.fromisoformat(recipe["day"])
    first, last = replay_window()
    if not first <= day <= last:
        raise ReplayDayUnavailable(
            f"No replay data for {day.isoformat()}: the replay covers {first} to {last}"
        )
    threshold = float(recipe["threshold"])
    inputs = _REPLAY.inputs(day)
    events = _Events()
    plan = planner.build_plan(inputs, t9_gate(threshold), events, _script().planner_now(day))
    return BuiltPlan(inputs, plan, _basis(threshold), recipe, tuple(events.events))


def build_replay_plan(day: date, threshold: float | None = None) -> BuiltPlan:
    """The DRAFT plan for a replay day, gated by T9 (default: the configured threshold)."""
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
    if differs or "day" not in recipe or "threshold" not in recipe:
        raise PlanRebuildError(
            f"Plan recipe cannot be rebuilt here (fields {differs or ['day', 'threshold']}); "
            f"this build makes {expected}"
        )
    return _build(dict(recipe))
