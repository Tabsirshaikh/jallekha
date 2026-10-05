"""The live blocks of a ward report card (F20): deliveries, water debt and schedule.

Each block is {value, basis, reason}: a value with its basis, or no value and the reason, so a
resident never sees a made-up number. All data here is SYNTHETIC.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime, timedelta

from app.config.allocation import ALLOCATION_CONFIG
from app.services import delivery as dl
from app.services import plan_builder, report_card
from app.services.delivery_store import Stop
from app.services.ledger_port import InMemoryLedger
from app.services.water_debt import DebtAccount

NOW = datetime(2026, 10, 5, 6, 0, tzinfo=UTC)
WARD = "relation/7848824"
LOAD = ALLOCATION_CONFIG.tanker_load_litres
CHAIN = InMemoryLedger(key="test-ledger-key", clock=lambda: NOW)


def _stop(stop_id: str, basis: str = "SYNTHETIC") -> Stop:
    return Stop(stop_id, 17.44437, 78.31387, (), (), basis, WARD, "DERIVED")


def _delivery(
    delivery_id: str, stop_id: str, outcome: str | None, at: datetime
) -> dl.DeliveryState:
    reps = tuple(
        dl.Representative(f"{stop_id}-r{i}", stop_id, f"+91900000000{i}", "te") for i in (1, 2)
    )
    state = dl.start_delivery(delivery_id, stop_id, 17.44, 78.31, "drv-1", reps, CHAIN, at)
    if outcome is None:
        return state
    return replace(
        state, outcome=dl.OutcomeDecision(outcome, "majority", True, 3, 0, 0, "SYNTHETIC")
    )  # type: ignore[arg-type]


def test_deliveries_count_the_wards_stops_over_the_window() -> None:
    stops = [_stop("s1"), _stop("s2")]
    deliveries = [
        _delivery("d1", "s1", "Confirmed", NOW - timedelta(days=1)),
        _delivery("d2", "s2", "Disputed", NOW - timedelta(days=2)),
        _delivery("d3", "s2", None, NOW - timedelta(hours=1)),
    ]
    block = report_card.deliveries_block(stops, deliveries, NOW)
    value = block["value"]
    assert block["basis"] == "SYNTHETIC" and block["reason"] is None
    assert value["window_days"] == 30 and value["started"] == 3
    assert value["by_outcome"] == {
        "Confirmed": 1, "Disputed": 1, "Unconfirmed": 0, "Failed": 0, "open": 1,
    }  # fmt: skip
    assert value["confirmed_litres"] == LOAD
    assert [s["stop_id"] for s in value["stops"]] == ["s1", "s2"]
    assert value["from"] == (NOW - timedelta(days=30)).isoformat()


def test_real_and_synthetic_stops_make_a_mixed_basis() -> None:
    block = report_card.deliveries_block([_stop("s1", "REAL"), _stop("s2")], [], NOW)
    assert block["basis"] == "MIXED (REAL and SYNTHETIC stops)"
    assert block["value"]["started"] == 0


def test_a_ward_without_stops_says_so() -> None:
    block = report_card.deliveries_block([], [], NOW)
    assert block["value"] is None and block["basis"] == "UNAVAILABLE"
    assert "no delivery stop" in block["reason"]


def test_debt_shows_the_balance_and_the_last_closed_day() -> None:
    account = DebtAccount(
        f"ward:{WARD}", 20_000.0, debt_litres=12_000.0, in_debt_since=date(2026, 10, 2),
        alert_raised=True, settled_through=date(2026, 10, 4),
    )  # fmt: skip
    last = {"day": "2026-10-04", "plan_id": "plan-x", "planned_litres": 20_000.0}
    block = report_card.debt_block(account, last)
    value = block["value"]
    assert value["debt_litres"] == 12_000.0 and value["debt_loads"] == 3  # 2.4 loads, rounded up
    assert value["days_in_debt"] == 3 and value["alert_raised"] is True
    assert value["cap_litres"] == 7 * 20_000.0
    assert value["settled_through"] == "2026-10-04" and value["last_day"] == last
    assert block["basis"].startswith("DERIVED")


def test_no_debt_account_says_why() -> None:
    block = report_card.debt_block(None, None)
    assert block["value"] is None and "no closed day" in block["reason"]


def test_schedule_lists_the_wards_booked_trips_and_stop_loads() -> None:
    setup = plan_builder._setup()
    section = next(
        s for s, link in sorted(setup.ctx.mapping.items())
        if link.ward_id == WARD and s in setup.ctx.network.home
    )  # fmt: skip
    rows = [
        {"booking_id": f"B-{i}", "section": section, "arrived_at": f"2026-10-03T03:0{i}:00+05:30"}
        for i in range(4)
    ]
    stops = [{"stop_id": "s1", "ward_id": WARD, "lat": 17.44437, "lon": 78.31387}]
    built = plan_builder.build_supplied_plan(date(2026, 10, 3), rows, stops=stops)
    block = report_card.schedule_block(built.plan, built.recipe, built.inputs, built.basis, WARD)
    value = block["value"]
    assert value["plan_id"] == built.plan.plan_id and value["status"] == "DRAFT"
    assert value["source"] == "supplied_bookings"
    assert value["booked"]["served"] + value["booked"]["waiting"] == 4
    assert value["scheduled"]["litres"] == built.plan.scheduled[WARD].litres
    (stop,) = value["stops"]
    assert stop["stop_id"] == "s1" and stop["litres"] > 0 and stop["loads"] == stop["litres"] / LOAD
    assert "supplied" in block["basis"].lower()


def test_no_plan_says_why() -> None:
    block = report_card.schedule_block(None, None, None, None, WARD)
    assert block["value"] is None and "no plan" in block["reason"]
