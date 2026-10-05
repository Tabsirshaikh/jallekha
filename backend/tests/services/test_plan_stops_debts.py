"""Supplied plans that give scheduled water to registered delivery stops and carry water debt.

A registered stop in a scheduled-supply ward is that ward's service point (F9 = F12 stop): the
plan splits the ward's scheduled litres across its stops (A4) and lists each stop's loads. Debt
accounts (A6) saved by closing earlier days raise their groups' turns (A7). Both are part of the
recipe, so the plan rebuilds exactly. All data here is SYNTHETIC.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from app.services import plan_builder, water_debt
from app.services.water_debt import DebtAccount

DAY = date(2026, 10, 3)
SCHEDULED_WARD = "relation/7848824"  # Ward 105 Gachibowli, an A2 scheduled-supply ward
OTHER_WARD = "relation/7857838"  # Ward 150 Monda Market, not scheduled
STOPS = [
    {"stop_id": "stop-g1", "ward_id": SCHEDULED_WARD, "lat": 17.44437, "lon": 78.31387},
    {"stop_id": "stop-g2", "ward_id": SCHEDULED_WARD, "lat": 17.44500, "lon": 78.31400},
    {"stop_id": "stop-m1", "ward_id": OTHER_WARD, "lat": 17.44000, "lon": 78.49830},
]
DEBT = DebtAccount(
    account_id=f"ward:{SCHEDULED_WARD}",
    daily_entitlement_litres=50_000.0,
    debt_litres=200_000.0,
    in_debt_since=date(2026, 10, 1),
    settled_through=date(2026, 10, 2),
)


def _bookings(count: int = 24) -> list[dict[str, Any]]:
    setup = plan_builder._setup()
    sections = [s for s in sorted(setup.ctx.network.home) if s in setup.ctx.mapping][:3]
    return [
        {
            "booking_id": f"B-{i:04d}",
            "section": sections[i % 3],
            "arrived_at": f"2026-10-03T03:{i % 60:02d}:00+05:30",
        }
        for i in range(count)
    ]


def test_scheduled_water_goes_to_the_stops_of_a_scheduled_ward() -> None:
    built = plan_builder.build_supplied_plan(DAY, _bookings(), stops=STOPS)
    litres = plan_builder.stop_litres(built.plan, [s["stop_id"] for s in STOPS])
    assert litres["stop-g1"] > 0 and litres["stop-g1"] == litres["stop-g2"]
    assert litres["stop-m1"] == 0  # its ward has no scheduled supply
    share = built.plan.scheduled[SCHEDULED_WARD].litres
    load = 5000
    assert abs(litres["stop-g1"] + litres["stop-g2"] - share) <= 2 * load  # whole loads
    assert built.recipe["stops"] == sorted(STOPS, key=lambda s: s["stop_id"])


def test_without_stops_the_plan_and_its_id_are_unchanged() -> None:
    rows = _bookings()
    plain = plan_builder.build_supplied_plan(DAY, rows)
    assert "stops" not in plain.recipe and "debts" not in plain.recipe
    assert plain.plan.plan_id == plan_builder.supplied_plan_id(DAY, rows)
    assert plan_builder.stop_litres(plain.plan, ["stop-g1"]) == {"stop-g1": 0.0}


def test_stops_and_debts_change_the_plan_id() -> None:
    rows = _bookings()
    plain = plan_builder.supplied_plan_id(DAY, rows)
    with_stops = plan_builder.supplied_plan_id(DAY, rows, stops=STOPS)
    with_debt = plan_builder.supplied_plan_id(DAY, rows, stops=STOPS, debts=[DEBT])
    assert len({plain, with_stops, with_debt}) == 3
    built = plan_builder.build_supplied_plan(DAY, rows, stops=STOPS, debts=[DEBT])
    assert built.plan.plan_id == with_debt
    # the order the stops are given in does not matter
    assert plan_builder.supplied_plan_id(DAY, rows, stops=STOPS[::-1]) == with_stops


def test_a_ward_in_debt_gets_a_larger_share_of_turns() -> None:
    rows = _bookings()
    group = f"ward:{SCHEDULED_WARD}"
    plain = plan_builder.build_supplied_plan(DAY, rows).plan
    owed = plan_builder.build_supplied_plan(DAY, rows, debts=[DEBT]).plan
    assert owed.effective_entitlement[group] > plain.effective_entitlement[group]
    others = [g for g in plain.effective_entitlement if g != group]
    assert all(owed.effective_entitlement[g] == plain.effective_entitlement[g] for g in others)


def test_a_plan_with_stops_and_debts_rebuilds_to_the_same_digest() -> None:
    built = plan_builder.build_supplied_plan(DAY, _bookings(), stops=STOPS, debts=[DEBT])
    again = plan_builder.rebuild(built.recipe)
    assert again.plan.digest == built.plan.digest
    assert built.recipe["debts"] == [water_debt.account_as_dict(DEBT)]


def test_accounts_with_no_debt_do_not_change_the_plan_or_its_id() -> None:
    rows = _bookings()
    paid = DebtAccount(f"ward:{OTHER_WARD}", 5000.0, settled_through=date(2026, 10, 2))
    assert plan_builder.supplied_plan_id(DAY, rows, debts=[paid]) == plan_builder.supplied_plan_id(
        DAY, rows
    )
    assert "debts" not in plan_builder.build_supplied_plan(DAY, rows, debts=[paid]).recipe


def test_debt_accounts_round_trip_through_a_dict() -> None:
    assert water_debt.account_from_dict(water_debt.account_as_dict(DEBT)) == DEBT
    fresh = DebtAccount("ward:x", 5000.0)
    assert water_debt.account_from_dict(water_debt.account_as_dict(fresh)) == fresh
