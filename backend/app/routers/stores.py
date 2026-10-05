"""Stores the API serves plans and deliveries from, both kept in the database.

Plans: `POST /plans` builds a replay plan (services/plan_builder.py) and the app's `PlanStore`
keeps it in `plan_record`, so plans survive a restart. Deliveries and their stops live in
`services/delivery_store.py`. Until a plan is built or a stop registered the routes answer 404
rather than invent data. The stores compute nothing themselves: they hold what the existing
services (A7 `build_plan`, T3 `start_delivery`) made.
"""

from __future__ import annotations

import json
from collections import OrderedDict
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config.plans import PLAN_STORE_CONFIG
from app.db import create_all, make_engine, make_session_factory
from app.models import StoredPlan
from app.services import plan_builder, planner
from app.services.debt_store import DebtStore
from app.services.delivery_store import DeliveryStore
from app.services.delivery_store import Stop as Stop  # re-exported for the routers and tests


class PlanConflict(Exception):
    """The plan was changed by someone else since it was read: reload it and try again."""


@dataclass
class PlanRecord:
    inputs: planner.PlanInputs
    plan: planner.DailyPlan
    basis: dict[str, str]
    recipe: dict[str, Any] | None = None  # how to rebuild it (plan_builder); None: not storable
    version: int = 0  # times saved when it was read (optimistic lock, see PlanStore.save)


class PlanStore:
    """Plans by id (Wave 1). With an engine, plans persist in `plan_record` as a rebuild recipe
    plus the officer's checks and approval (no pickling): a read rebuilds the plan with
    `rebuild` (deterministic), refuses it if the digest differs from the stored one
    (PlanRebuildError), then puts the stored checks and approval back on it with
    `dataclasses.replace` (mark_checked / approve_plan are not called again, so the ledger gets
    no duplicate entries). Rebuilt plans are cached per store. Without an engine the store
    holds records in memory (tests and synthetic plans; nothing persists)."""

    def __init__(
        self,
        engine: Engine | None = None,
        rebuild: Callable[[Mapping[str, Any]], plan_builder.BuiltPlan] = plan_builder.rebuild,
        cache_size: int = PLAN_STORE_CONFIG.built_cache_size,
    ) -> None:
        self.plans: dict[str, PlanRecord] = {}  # in-memory records (no engine)
        self._created: dict[str, datetime] = {}
        self._engine = engine
        self._sessions = make_session_factory(engine) if engine is not None else None
        self._rebuild = rebuild
        self._cache_size = cache_size
        self._built: OrderedDict[str, plan_builder.BuiltPlan] = OrderedDict()

    def _row(self, session: Session, plan_id: str) -> StoredPlan | None:
        return session.scalars(select(StoredPlan).filter_by(plan_id=plan_id)).first()

    def get(self, plan_id: str) -> PlanRecord | None:
        if self._sessions is None:
            return self.plans.get(plan_id)
        with self._sessions() as session:
            row = self._row(session, plan_id)
        return None if row is None else self._load(row)

    def _load(self, row: StoredPlan) -> PlanRecord:
        built = self._built.get(row.plan_id)
        if built is None or built.plan.digest != row.digest:
            built = self._rebuild(json.loads(row.recipe_json))
            if built.plan.digest != row.digest:
                raise plan_builder.PlanRebuildError(
                    f"Plan {row.plan_id} rebuilt with digest {built.plan.digest[:12]}, stored "
                    f"digest {row.digest[:12]}: its inputs or gate changed since it was stored"
                )
            self._built[row.plan_id] = built
            while len(self._built) > self._cache_size:
                self._built.popitem(last=False)
        self._built.move_to_end(row.plan_id)
        checked = {c["group"]: c["reason"] for c in json.loads(row.checked_json)}
        plan = replace(
            built.plan,
            status=row.status,
            checked=checked,
            approved_by=row.approved_by,
            approval_reason=row.approval_reason,
        )
        return PlanRecord(
            built.inputs,
            plan,
            json.loads(row.basis_json),
            dict(built.recipe),
            row.version,
        )

    def put(self, record: PlanRecord) -> bool:
        """Store a new plan; False (and nothing changed) if its plan id is already stored."""
        plan = record.plan
        if self._sessions is None:
            if plan.plan_id in self.plans:
                return False
            self.plans[plan.plan_id] = record
            self._created[plan.plan_id] = datetime.now(UTC)
            return True
        if record.recipe is None:
            raise ValueError(f"Plan {plan.plan_id} has no recipe and cannot be persisted")
        row = StoredPlan(
            plan_id=plan.plan_id,
            day=plan.day.isoformat(),
            recipe_json=json.dumps(record.recipe, sort_keys=True),
            digest=plan.digest,
            status=plan.status,
            flags_total=len(plan.flags),
            checked_json=_checked_json(plan),
            approved_by=plan.approved_by,
            approval_reason=plan.approval_reason,
            basis_json=json.dumps(record.basis, sort_keys=True),
        )
        try:
            with self._sessions() as session, session.begin():
                session.add(row)
        except IntegrityError:
            return False
        return True

    def save(self, record: PlanRecord) -> None:
        """Store the officer's checks and approval on a plan already stored."""
        plan = record.plan
        if self._sessions is None:
            self.plans[plan.plan_id] = record
            return
        with self._sessions() as session, session.begin():
            row = self._row(session, plan.plan_id)
            if row is None or row.digest != plan.digest:
                raise ValueError(f"Plan {plan.plan_id} with this digest is not stored")
            # Compare and swap: only if nobody saved since `record` was read.
            saved = session.execute(
                update(StoredPlan)
                .where(StoredPlan.id == row.id, StoredPlan.version == record.version)
                .values(
                    status=plan.status,
                    checked_json=_checked_json(plan),
                    approved_by=plan.approved_by,
                    approval_reason=plan.approval_reason,
                    version=record.version + 1,
                )
            )
            if saved.rowcount == 0:
                raise PlanConflict(f"Plan {plan.plan_id} was changed by someone else; reload it")
        record.version += 1

    def records(self) -> Iterator[PlanRecord]:
        """Every plan, by day (a persisted plan is rebuilt when it is not cached)."""
        if self._sessions is None:
            yield from sorted(self.plans.values(), key=lambda r: (r.plan.day, r.plan.plan_id))
            return
        with self._sessions() as session:
            rows = list(session.scalars(select(StoredPlan).order_by(StoredPlan.day)))
        for row in rows:
            yield self._load(row)

    def summaries(self) -> list[dict[str, Any]]:
        """One line per plan, by day, without rebuilding any plan."""
        if self._sessions is None:
            return [
                {
                    "plan_id": r.plan.plan_id,
                    "day": r.plan.day.isoformat(),
                    "status": r.plan.status,
                    "basis": r.basis,
                    "flags_total": len(r.plan.flags),
                    "weights": (r.recipe or {}).get("weights"),
                    "source": (r.recipe or {}).get("source", "planner_replay"),
                    "checked_total": len(r.plan.checked),
                    "created_at": self._created[r.plan.plan_id].isoformat(),
                }
                for r in self.records()
            ]
        with self._sessions() as session:
            rows = list(
                session.scalars(select(StoredPlan).order_by(StoredPlan.day, StoredPlan.plan_id))
            )
        return [
            {
                "plan_id": row.plan_id,
                "day": row.day,
                "status": row.status,
                "basis": json.loads(row.basis_json),
                "flags_total": row.flags_total,
                "weights": json.loads(row.recipe_json).get("weights"),
                "source": json.loads(row.recipe_json).get("source", "planner_replay"),
                "checked_total": len(json.loads(row.checked_json)),
                "created_at": _utc(row.created_at).isoformat(),
            }
            for row in rows
        ]


def _checked_json(plan: planner.DailyPlan) -> str:
    return json.dumps([{"group": g, "reason": r} for g, r in plan.checked.items()])


def _utc(moment: datetime) -> datetime:
    """SQLite returns naive datetimes; they were written as UTC."""
    return moment if moment.tzinfo else moment.replace(tzinfo=UTC)


_PLANS: PlanStore | None = None


def get_plan_store() -> PlanStore:
    """The app's plan store on DATABASE_URL (created on first use; overridden in tests)."""
    global _PLANS
    if _PLANS is None:
        engine = make_engine()
        create_all(engine)
        _PLANS = PlanStore(engine)
    return _PLANS


# Stops and deliveries live in the database (services/delivery_store.py); re-exported here.
_DELIVERIES: DeliveryStore | None = None


def get_delivery_store() -> DeliveryStore:
    global _DELIVERIES
    if _DELIVERIES is None:
        engine = make_engine()
        create_all(engine)
        _DELIVERIES = DeliveryStore(engine)
    return _DELIVERIES


# Water debt accounts and closed days (services/debt_store.py).
_DEBTS: DebtStore | None = None


def get_debt_store() -> DebtStore:
    global _DEBTS
    if _DEBTS is None:
        engine = make_engine()
        create_all(engine)
        _DEBTS = DebtStore(engine)
    return _DEBTS
