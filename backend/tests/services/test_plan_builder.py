"""Plans built for the API from P2's committed A7 replay (SIMULATION), gated by T9 (F17).

Uses the real replay files; the replay set-up is loaded once per test session (about 12 s).
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.config.confidence import CONFIDENCE_CONFIG
from app.services import plan_builder

FIRST = date(2025, 3, 1)  # first day of the replay main_2025 (Mar-Jul 2025)


def test_replay_window_is_the_committed_replay() -> None:
    first, last = plan_builder.replay_window()
    assert first == FIRST
    assert last == date(2025, 7, 31)


def test_a_day_outside_the_window_is_refused_without_building() -> None:
    first, last = plan_builder.replay_window()
    for day in (first - timedelta(days=1), last + timedelta(days=1)):
        with pytest.raises(plan_builder.ReplayDayUnavailable):
            plan_builder.build_replay_plan(day)


def test_replay_plan_uses_the_t9_gate_and_is_labelled_simulation() -> None:
    built = plan_builder.build_replay_plan(FIRST)
    assert built.plan.plan_id == "replay-2025-03-01" and built.plan.day == FIRST
    assert built.plan.status == "DRAFT" and not built.plan.checked
    assert built.plan.flags, "the replay has unplaced sections: T9 must flag some groups"
    for flag in built.plan.flags.values():
        # T9's Assessment, not A7's ProvisionalGate ("PROVISIONAL" / "NO_CENSUS_NEED_DATA").
        assert flag.basis.startswith("DERIVED; min of available signals")
        assert flag.reason.startswith("weakest ")
        assert flag.confidence < CONFIDENCE_CONFIG.threshold
    assert built.basis["plan"].startswith("SIMULATION")
    assert "T9" in built.basis["flags"]
    assert CONFIDENCE_CONFIG.threshold_basis in built.basis["flags"]
    assert built.recipe == {
        "source": "planner_replay",
        "replay": "main_2025",
        "scenario": "tight",
        "seed": 0,
        "day": "2025-03-01",
        "gate": "T9",
        "threshold": CONFIDENCE_CONFIG.threshold,
    }


def test_build_writes_no_ledger_entry_and_returns_the_event_to_write_once() -> None:
    built = plan_builder.build_replay_plan(FIRST)
    assert [e[0] for e in built.events] == ["plan_created"]
    event_type, payload, actor = built.events[0]
    assert payload["entity_id"] == "replay-2025-03-01"
    assert payload["digest"] == built.plan.digest and actor == "system"
    assert payload["flagged_groups"] == sorted(built.plan.flags)


def test_rebuild_from_the_recipe_is_the_same_plan() -> None:
    built = plan_builder.build_replay_plan(FIRST + timedelta(days=1))
    again = plan_builder.rebuild(built.recipe)
    assert again.plan.digest == built.plan.digest
    assert again.recipe == built.recipe and again.basis == built.basis
    # Going back to an earlier day restarts the replay and still gives the same plan.
    first = plan_builder.rebuild({**built.recipe, "day": FIRST.isoformat()})
    assert first.plan.digest == plan_builder.build_replay_plan(FIRST).plan.digest


def test_rebuild_refuses_a_recipe_it_cannot_reproduce() -> None:
    recipe = plan_builder.build_replay_plan(FIRST).recipe
    for change in ({"source": "other"}, {"seed": 1}, {"scenario": "loose"}, {"gate": "A7"}):
        with pytest.raises(plan_builder.PlanRebuildError):
            plan_builder.rebuild({**recipe, **change})
