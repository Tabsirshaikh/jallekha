"""In-memory holders for plans and deliveries the API can serve.

There is no plan store and no delivery store on `main` (OPEN, P2 / P3; docs/api_shapes.md). These
holders are empty in a running app until the job that builds a plan or registers a stop puts
records in them, so the routes answer 404 rather than invent data. They hold objects made by the
existing services (A7 `build_plan`, T3 `start_delivery`); they compute nothing themselves.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.services import delivery, planner


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


@dataclass(frozen=True)
class Stop:
    stop_id: str
    lat: float
    lon: float
    representatives: tuple[delivery.Representative, ...]
    residents: tuple[delivery.Resident, ...]


@dataclass
class DeliveryStore:
    stops: dict[str, Stop] = field(default_factory=dict)
    deliveries: dict[str, delivery.DeliveryState] = field(default_factory=dict)


_PLANS = PlanStore()
_DELIVERIES = DeliveryStore()


def get_plan_store() -> PlanStore:
    return _PLANS


def get_delivery_store() -> DeliveryStore:
    return _DELIVERIES
