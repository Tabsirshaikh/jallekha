"""DB-backed plan store (Wave 1): plans persist as rebuild recipes, never pickled objects.

Plans are real replay plans (SIMULATION) gated by T9; see tests/services/test_plan_builder.py.
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from sqlalchemy import select, update
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.db import create_all, make_engine
from app.models import StoredPlan
from app.routers.plans import plan_view
from app.routers.stores import PlanRecord, PlanStore
from app.services import plan_builder, planner
from app.services.ledger_port import InMemoryLedger

DAY = date(2025, 3, 1)
NOW = datetime(2026, 10, 4, 5, 0, tzinfo=UTC)


@pytest.fixture
def db(tmp_path: Path) -> Engine:
    engine = make_engine(f"sqlite:///{(tmp_path / 'plans.db').as_posix()}")
    create_all(engine)
    yield engine
    engine.dispose()


def _record(day: date = DAY) -> PlanRecord:
    built = plan_builder.build_replay_plan(day)
    return PlanRecord(built.inputs, built.plan, built.basis, built.recipe)


def _reopen(db: Engine) -> PlanStore:
    """A new store on the same database file, as after an app restart."""
    return PlanStore(make_engine(str(db.url)))


def test_round_trip_keeps_the_view_digest_checks_and_approval(db: Engine) -> None:
    store = PlanStore(db)
    record = _record()
    assert store.put(record) is True
    view = plan_view(record)

    fresh = _reopen(db).get(record.plan.plan_id)
    assert fresh is not None and plan_view(fresh) == view
    assert fresh.recipe == record.recipe and fresh.inputs.day == DAY

    ledger = InMemoryLedger(key="test-key")
    group = sorted(record.plan.flags)[0]
    fresh.plan = planner.mark_checked(fresh.plan, group, "officer-7", "Seen on site", ledger, NOW)
    store_b = _reopen(db)
    store_b.save(fresh)

    reloaded = _reopen(db).get(record.plan.plan_id)
    assert reloaded is not None
    assert reloaded.plan.checked == {group: "Seen on site"}
    assert reloaded.plan.digest == record.plan.digest and reloaded.plan.status == "DRAFT"

    for flagged in sorted(set(record.plan.flags) - {group}):
        reloaded.plan = planner.mark_checked(reloaded.plan, flagged, "o-7", "ok", ledger, NOW)
    reloaded.plan = planner.approve_plan(reloaded.plan, "officer-7", "All checked", ledger, NOW)
    _reopen(db).save(reloaded)

    approved = _reopen(db).get(record.plan.plan_id)
    assert approved is not None
    assert approved.plan.status == "APPROVED"
    assert approved.plan.approved_by == "officer-7"
    assert approved.plan.approval_reason == "All checked"
    assert list(approved.plan.checked) == list(reloaded.plan.checked)  # check order kept
    assert plan_view(approved) == plan_view(reloaded)


def test_rows_hold_a_recipe_and_plain_json_not_a_pickle(db: Engine) -> None:
    record = _record()
    PlanStore(db).put(record)
    with Session(db) as session:
        row = session.scalars(select(StoredPlan)).one()
    assert json.loads(row.recipe_json) == record.recipe
    assert json.loads(row.basis_json) == record.basis
    assert json.loads(row.checked_json) == []
    assert row.plan_id == record.plan.plan_id and row.day == "2025-03-01"
    assert row.digest == record.plan.digest and row.status == "DRAFT"
    assert row.flags_total == len(record.plan.flags)


def test_reload_writes_no_ledger_entry(db: Engine, monkeypatch: pytest.MonkeyPatch) -> None:
    record = _record()
    PlanStore(db).put(record)
    calls: list[str] = []
    monkeypatch.setattr(planner, "mark_checked", lambda *a, **k: calls.append("check"))
    monkeypatch.setattr(planner, "approve_plan", lambda *a, **k: calls.append("approve"))
    store = _reopen(db)
    loaded = store.get(record.plan.plan_id)
    assert loaded is not None and calls == []


def test_a_changed_digest_is_refused_with_a_clear_error(db: Engine) -> None:
    record = _record()
    PlanStore(db).put(record)
    with Session(db) as session, session.begin():
        session.execute(update(StoredPlan).values(digest="0" * 64))
    with pytest.raises(plan_builder.PlanRebuildError, match="digest"):
        _reopen(db).get(record.plan.plan_id)


def test_put_is_idempotent_by_plan_id(db: Engine) -> None:
    store = PlanStore(db)
    record = _record()
    assert store.put(record) is True
    assert _reopen(db).put(record) is False
    assert [s["plan_id"] for s in _reopen(db).summaries()] == [record.plan.plan_id]


def test_summaries_come_from_the_rows(db: Engine) -> None:
    store = PlanStore(db)
    second, first = _record(date(2025, 3, 2)), _record(DAY)
    store.put(second)
    store.put(first)
    rows = _reopen(db).summaries()
    assert [r["plan_id"] for r in rows] == ["replay-2025-03-01", "replay-2025-03-02"]
    assert set(rows[0]) == {
        "plan_id", "day", "status", "basis", "flags_total", "checked_total", "created_at"
    }  # fmt: skip
    assert rows[0]["flags_total"] == len(first.plan.flags) and rows[0]["checked_total"] == 0


def test_a_plan_without_a_recipe_cannot_be_persisted(db: Engine) -> None:
    record = _record()
    with pytest.raises(ValueError, match="recipe"):
        PlanStore(db).put(PlanRecord(record.inputs, record.plan, record.basis))


def test_in_memory_store_still_holds_synthetic_plans() -> None:
    record = _record()
    store = PlanStore()
    store.put(PlanRecord(record.inputs, record.plan, record.basis))
    assert store.get(record.plan.plan_id) is not None
    assert store.get("nope") is None
    assert [s["plan_id"] for s in store.summaries()] == [record.plan.plan_id]
