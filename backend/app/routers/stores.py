"""In-memory holders for plans and deliveries the API can serve.

There is no plan store and no delivery store on `main` (OPEN, P2 / P3; docs/api_shapes.md). These
holders are empty in a running app until the job that builds a plan or registers a stop puts
records in them, so the routes answer 404 rather than invent data. They hold objects made by the
existing services (A7 `build_plan`, T3 `start_delivery`); they compute nothing themselves.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.db import create_all, make_engine
from app.services import planner
from app.services.delivery_store import DeliveryStore
from app.services.delivery_store import Stop as Stop  # re-exported for the routers and tests


@dataclass
class PlanRecord:
    inputs: planner.PlanInputs
    plan: planner.DailyPlan
    basis: dict[str, str]


@dataclass
class PlanStore:
    plans: dict[str, PlanRecord] = field(default_factory=dict)

    def put(self, record: PlanRecord) -> None:
        self.plans[record.plan.plan_id] = record


_PLANS = PlanStore()


def get_plan_store() -> PlanStore:
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
