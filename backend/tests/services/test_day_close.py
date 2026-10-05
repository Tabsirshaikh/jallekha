"""Closing a day: water debt (A6) from an approved supplied plan and the day's delivery outcomes.

For each ward, the litres the approved plan gave the ward's registered stops are owed that day;
only Confirmed deliveries at those stops (one tanker load each) pay it back. Debt accounts and
the closed day are saved, every change is a ledger entry. All data here is SYNTHETIC.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from app.config.allocation import ALLOCATION_CONFIG
from app.db import create_all, make_engine
from app.services import day_close, plan_builder, planner
from app.services import delivery as dl
from app.services.debt_store import DebtDayConflict, DebtStore
from app.services.ledger_port import InMemoryLedger
from app.services.water_debt import DebtAccount

DAY = date(2026, 10, 3)
NOW = datetime(2026, 10, 4, 6, 0, tzinfo=UTC)
WARD = "relation/7848824"  # Ward 105 Gachibowli, scheduled supply
GROUP = f"ward:{WARD}"
LOAD = ALLOCATION_CONFIG.tanker_load_litres
STOPS = [
    {"stop_id": "stop-g1", "ward_id": WARD, "lat": 17.44437, "lon": 78.31387},
    {"stop_id": "stop-g2", "ward_id": WARD, "lat": 17.44500, "lon": 78.31400},
]
# Registered stops now and the ward each serves (deliveries count for this ward).
WARD_OF = {s["stop_id"]: s["ward_id"] for s in STOPS}
# 09:00 IST on DAY
MORNING = datetime(2026, 10, 3, 3, 30, tzinfo=UTC)


def _bookings() -> list[dict[str, Any]]:
    setup = plan_builder._setup()
    sections = [s for s in sorted(setup.ctx.network.home) if s in setup.ctx.mapping][:3]
    return [
        {
            "booking_id": f"B-{i:04d}",
            "section": sections[i % 3],
            "arrived_at": f"2026-10-03T03:{i:02d}:00+05:30",
        }
        for i in range(12)
    ]


@pytest.fixture(scope="module")
def built() -> plan_builder.BuiltPlan:
    return plan_builder.build_supplied_plan(DAY, _bookings(), stops=STOPS)


def _approved(built: plan_builder.BuiltPlan, chain: InMemoryLedger) -> planner.DailyPlan:
    plan = built.plan
    for group in plan.flags:
        plan = planner.mark_checked(plan, group, "off-1", "checked on the ground", chain, NOW)
    return planner.approve_plan(plan, "off-1", "approved for the day", chain, NOW)


def _delivery(
    delivery_id: str,
    stop_id: str,
    outcome: str | None,
    chain: InMemoryLedger,
    at: datetime = MORNING,
) -> dl.DeliveryState:
    reps = tuple(
        dl.Representative(f"{stop_id}-r{i}", stop_id, f"+91900000000{i}", "te") for i in (1, 2)
    )
    state = dl.start_delivery(delivery_id, stop_id, 17.44, 78.31, "drv-1", reps, chain, at)
    if outcome is None:
        return state
    return replace(
        state, outcome=dl.OutcomeDecision(outcome, "majority", True, 3, 0, 0, "SYNTHETIC")
    )  # type: ignore[arg-type]


@pytest.fixture
def chain() -> InMemoryLedger:
    return InMemoryLedger(key="test-ledger-key", clock=lambda: NOW)


def _close(
    built: plan_builder.BuiltPlan,
    chain: InMemoryLedger,
    deliveries: list[dl.DeliveryState],
    accounts: dict[str, DebtAccount] | None = None,
    plan: planner.DailyPlan | None = None,
) -> day_close.ClosedDay:
    return day_close.close_day(
        DAY,
        plan or _approved(built, chain),
        built.recipe["stops"],
        WARD_OF,
        deliveries,
        accounts or {},
        chain,
        NOW,
        "off-1",
        "all deliveries closed",
    )


def test_planned_water_not_confirmed_becomes_debt(
    built: plan_builder.BuiltPlan, chain: InMemoryLedger
) -> None:
    planned = sum(plan_builder.stop_litres(built.plan, ["stop-g1", "stop-g2"]).values())
    assert planned > 2 * LOAD
    deliveries = [
        _delivery("d1", "stop-g1", "Confirmed", chain),
        _delivery("d2", "stop-g2", "Disputed", chain),
        _delivery("d3", "stop-g2", "Unconfirmed", chain),
    ]
    closed = _close(built, chain, deliveries)
    (ward,) = closed.wards
    assert ward.ward_id == WARD
    assert ward.planned_litres == planned
    assert ward.credited_litres == LOAD  # only the Confirmed one counts
    assert ward.deliveries == {"Confirmed": 1, "Disputed": 1, "Unconfirmed": 1}
    assert ward.debt_before == 0 and ward.debt_after == planned - LOAD
    (account,) = closed.accounts
    assert account.account_id == GROUP and account.debt_litres == planned - LOAD
    assert account.settled_through == DAY and account.in_debt_since == DAY
    types = [e.event_type for e in chain.entries]
    assert types.count("water_debt_changed") == 1 and types[-1] == "debt_day_closed"
    payload = chain.entries[-1].payload
    assert payload["day"] == "2026-10-03" and payload["plan_id"] == built.plan.plan_id
    assert "all deliveries closed" not in str(payload) and "reason_sha256" in payload


def test_debt_carries_over_and_is_paid_back_by_confirmed_loads(
    built: plan_builder.BuiltPlan, chain: InMemoryLedger
) -> None:
    planned = sum(plan_builder.stop_litres(built.plan, ["stop-g1", "stop-g2"]).values())
    earlier = DebtAccount(
        GROUP,
        planned,
        debt_litres=3 * LOAD,
        in_debt_since=DAY - timedelta(days=2),
        settled_through=DAY - timedelta(days=1),
    )
    confirmed = int(planned // LOAD) + 3  # everything planned plus the old debt
    deliveries = [_delivery(f"c{i}", "stop-g1", "Confirmed", chain) for i in range(confirmed)]
    closed = _close(built, chain, deliveries, {GROUP: earlier})
    (ward,) = closed.wards
    assert ward.debt_before == 3 * LOAD and ward.debt_after == 0
    assert closed.accounts[0].in_debt_since is None


def test_a_ward_with_an_account_but_nothing_planned_is_still_settled(
    built: plan_builder.BuiltPlan, chain: InMemoryLedger
) -> None:
    other = DebtAccount(
        "ward:relation/7857838",
        10_000.0,
        debt_litres=LOAD,
        in_debt_since=DAY - timedelta(days=1),
        settled_through=DAY - timedelta(days=1),
    )
    closed = _close(built, chain, [], {other.account_id: other})
    by_ward = {w.ward_id: w for w in closed.wards}
    assert by_ward["relation/7857838"].planned_litres == 0
    assert by_ward["relation/7857838"].debt_after == LOAD  # nothing delivered, nothing added
    assert {a.account_id for a in closed.accounts} == {GROUP, other.account_id}


@pytest.mark.parametrize(
    "case, expected",
    [
        ("draft", "approved"),
        ("open", "still open"),
        ("other_day", "2026-10-03"),
        ("wrong_day", "is for 2026-10-03"),
        ("already", "already settled"),
        ("no_reason", "reason"),
    ],
)
def test_a_day_is_closed_only_when_it_can_be(
    built: plan_builder.BuiltPlan, chain: InMemoryLedger, case: str, expected: str
) -> None:
    deliveries: list[dl.DeliveryState] = []
    accounts: dict[str, DebtAccount] = {}
    plan = None
    day, reason = DAY, "all deliveries closed"
    if case == "draft":
        plan = built.plan
    elif case == "open":
        deliveries = [_delivery("o1", "stop-g1", None, chain)]
    elif case == "other_day":
        deliveries = [_delivery("o2", "stop-g1", "Confirmed", chain, MORNING + timedelta(days=1))]
    elif case == "wrong_day":
        day = DAY + timedelta(days=1)
    elif case == "already":
        accounts = {GROUP: DebtAccount(GROUP, 5000.0, settled_through=DAY)}
    elif case == "no_reason":
        reason = " "
    plan = plan or _approved(built, chain)
    before = len(chain.entries)
    with pytest.raises(day_close.DayCloseRefused, match=expected):
        day_close.close_day(
            day,
            plan,
            built.recipe["stops"],
            WARD_OF,
            deliveries,
            accounts,
            chain,
            NOW,
            "off-1",
            reason,
        )
    assert len(chain.entries) == before  # a refused close writes nothing


def test_a_day_without_a_plan_settles_existing_accounts_with_nothing_owed(
    built: plan_builder.BuiltPlan, chain: InMemoryLedger
) -> None:
    owed = DebtAccount(
        GROUP, 50_000.0, debt_litres=3 * LOAD, in_debt_since=DAY - timedelta(days=1),
        settled_through=DAY - timedelta(days=1),
    )  # fmt: skip
    closed = day_close.close_day(
        DAY, None, [], WARD_OF, [_delivery("c1", "stop-g1", "Confirmed", chain)],
        {GROUP: owed}, chain, NOW, "off-1", "no tankers were planned",
    )  # fmt: skip
    (ward,) = closed.wards
    assert ward.planned_litres == 0 and ward.credited_litres == LOAD
    assert ward.debt_after == 2 * LOAD
    assert closed.plan_id is None and closed.plan_digest is None
    assert chain.entries[-1].payload["plan_id"] is None


def test_a_delivery_counts_for_its_stops_ward_even_at_a_stop_the_plan_did_not_know(
    built: plan_builder.BuiltPlan, chain: InMemoryLedger
) -> None:
    planned = sum(plan_builder.stop_litres(built.plan, ["stop-g1", "stop-g2"]).values())
    newer = {**WARD_OF, "stop-new": WARD}  # registered after the plan was built
    closed = day_close.close_day(
        DAY, _approved(built, chain), built.recipe["stops"], newer,
        [_delivery("n1", "stop-new", "Confirmed", chain)], {}, chain, NOW, "off-1", "closed",
    )  # fmt: skip
    assert closed.wards[0].credited_litres == LOAD
    assert closed.wards[0].debt_after == planned - LOAD


@pytest.mark.parametrize(
    "utc, expected",
    [
        (datetime(2026, 10, 3, 18, 20, tzinfo=UTC), date(2026, 10, 3)),  # 23:50 IST
        (datetime(2026, 10, 2, 18, 40, tzinfo=UTC), date(2026, 10, 3)),  # 00:10 IST
        (datetime(2026, 10, 3, 18, 40, tzinfo=UTC), date(2026, 10, 4)),  # 00:10 IST next day
    ],
)
def test_a_delivery_belongs_to_its_hyderabad_day(utc: datetime, expected: date) -> None:
    assert day_close.service_day(utc) == expected


def test_day_bounds_are_hyderabad_midnights() -> None:
    start, end = day_close.day_bounds(DAY)
    assert start == datetime(2026, 10, 2, 18, 30, tzinfo=UTC)
    assert end == datetime(2026, 10, 3, 18, 30, tzinfo=UTC)


# --- the store --------------------------------------------------------------------------------

StoreFactory = Callable[[], DebtStore]


@pytest.fixture
def new_store(tmp_path: Path) -> Iterator[StoreFactory]:
    url = f"sqlite:///{(tmp_path / 'debt.db').as_posix()}"
    engines = []

    def make() -> DebtStore:
        engine = make_engine(url)
        create_all(engine)
        engines.append(engine)
        return DebtStore(engine)

    yield make
    for engine in engines:
        engine.dispose()


def test_a_closed_day_and_its_accounts_survive_a_restart(
    built: plan_builder.BuiltPlan, chain: InMemoryLedger, new_store: StoreFactory
) -> None:
    closed = _close(built, chain, [_delivery("d1", "stop-g1", "Confirmed", chain)])
    new_store().save(closed, "off-1", "all deliveries closed")
    store = new_store()
    assert store.accounts() == {GROUP: closed.accounts[0]}
    assert store.last_closed_day() == DAY
    (saved,) = store.closed_days()
    assert saved["day"] == "2026-10-03" and saved["plan_id"] == built.plan.plan_id
    assert saved["closed_by"] == "off-1" and saved["wards"][WARD]["credited_litres"] == LOAD
    assert store.ward_last_day(WARD)["day"] == "2026-10-03"
    assert store.ward_last_day("relation/0") is None


def test_a_day_cannot_be_saved_twice(
    built: plan_builder.BuiltPlan, chain: InMemoryLedger, new_store: StoreFactory
) -> None:
    closed = _close(built, chain, [])
    new_store().save(closed, "off-1", "first")
    with pytest.raises(DebtDayConflict):
        new_store().save(closed, "off-2", "second")
    assert new_store().closed_days()[0]["closed_by"] == "off-1"


def test_days_are_saved_one_after_another(
    built: plan_builder.BuiltPlan, chain: InMemoryLedger, new_store: StoreFactory
) -> None:
    first = _close(built, chain, [])
    new_store().save(first, "off-1", "first")
    with pytest.raises(DebtDayConflict, match="2026-10-04"):
        new_store().save(replace(first, day=DAY + timedelta(days=2)), "off-1", "skips a day")
    with pytest.raises(DebtDayConflict):
        new_store().save(replace(first, day=DAY - timedelta(days=1)), "off-1", "goes back")
    assert [d["day"] for d in new_store().closed_days()] == ["2026-10-03"]


def test_saving_updates_existing_accounts(
    built: plan_builder.BuiltPlan, chain: InMemoryLedger, new_store: StoreFactory
) -> None:
    first = _close(built, chain, [])
    new_store().save(first, "off-1", "first")
    later = replace(
        first, day=DAY + timedelta(days=1), accounts=(replace(first.accounts[0], debt_litres=1.0),)
    )
    new_store().save(later, "off-1", "second")
    assert new_store().accounts()[GROUP].debt_litres == 1.0
    assert new_store().last_closed_day() == DAY + timedelta(days=1)
