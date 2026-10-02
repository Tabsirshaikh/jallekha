"""A6: water debt in litres (F11). D' = max(0, D + entitled - confirmed delivered), capped;
only Confirmed deliveries (F12) count; outage water never counts; long debt raises an alert;
every change is a ledger entry."""

from __future__ import annotations

import dataclasses
from datetime import UTC, date, datetime, timedelta

import pytest

from app.config.allocation import ALLOCATION_CONFIG
from app.config.trust import TRUST_CONFIG
from app.services import delivery, water_debt
from app.services.ledger_port import InMemoryLedger
from app.services.water_debt import DebtAccount, DeliveryCredit

CFG = ALLOCATION_CONFIG
T0 = datetime(2026, 5, 10, 22, 0, tzinfo=UTC)
DAY = date(2026, 5, 10)
DAILY = 2500.0  # HMWSSB domestic: one 5,000 l tanker in two days


@pytest.fixture
def chain() -> InMemoryLedger:
    return InMemoryLedger(key="test-ledger-key", clock=lambda: T0)


def account(debt: float = 0.0, **kw) -> DebtAccount:
    return DebtAccount(account_id="G1", daily_entitlement_litres=DAILY, debt_litres=debt, **kw)


def settle(acc, chain, entitled=DAILY, deliveries=(), day=DAY):
    return water_debt.settle_day(acc, day, entitled, deliveries, chain, T0)


def confirmed(delivery_id: str = "D1", litres: float = 5000.0, **kw) -> DeliveryCredit:
    return DeliveryCredit(delivery_id, litres, "Confirmed", **kw)


def debt_entries(chain):
    return [e for e in chain.entries if e.event_type == "water_debt_changed"]


def test_unmet_entitlement_becomes_debt_and_confirmed_water_pays_it(chain) -> None:
    first = settle(account(), chain)
    assert first.account.debt_litres == DAILY
    second = settle(first.account, chain, deliveries=[confirmed()], day=DAY + timedelta(days=1))
    assert second.account.debt_litres == 0.0  # 2500 + 2500 - 5000


def test_debt_never_goes_negative(chain) -> None:
    """Extra water does not bank credit against future entitlement."""
    result = settle(account(), chain, deliveries=[confirmed(litres=20000)])
    assert result.account.debt_litres == 0.0


@pytest.mark.parametrize("outcome", ["Disputed", "Unconfirmed", "Failed"])
def test_only_confirmed_deliveries_reduce_debt(chain, outcome) -> None:
    result = settle(account(5000), chain, deliveries=[DeliveryCredit("D1", 5000, outcome)])
    assert result.credited_litres == 0.0
    assert result.account.debt_litres == 5000 + DAILY
    payload = debt_entries(chain)[0].payload
    assert payload["counted_delivery_ids"] == []
    assert payload["not_counted"] == [["D1", outcome]]


def test_counting_rule_is_t3s(chain) -> None:
    for outcome in ("Confirmed", "Disputed", "Unconfirmed", "Failed"):
        assert water_debt.counts_toward_debt(outcome) == delivery.counts_toward_debt(outcome)


def test_unresolved_flag_lets_unconfirmed_count_but_never_disputed(chain, monkeypatch) -> None:
    """trust.unresolved_delivery_changes_shortfall (decided here): True would let an Unconfirmed
    delivery reduce debt. Default False, as F11 says only Confirmed counts."""
    assert TRUST_CONFIG.unresolved_delivery_changes_shortfall is False
    flipped = dataclasses.replace(TRUST_CONFIG, unresolved_delivery_changes_shortfall=True)
    monkeypatch.setattr(water_debt, "TRUST_CONFIG", flipped)
    assert water_debt.counts_toward_debt("Unconfirmed")
    assert not water_debt.counts_toward_debt("Disputed")
    assert not water_debt.counts_toward_debt("Failed")


def test_outage_water_never_counts_toward_debt(chain) -> None:
    result = settle(account(5000), chain, deliveries=[confirmed(purpose="outage")])
    assert result.credited_litres == 0.0
    assert result.account.debt_litres == 5000 + DAILY
    assert debt_entries(chain)[0].payload["not_counted"] == [["D1", "outage"]]


def test_debt_is_capped_and_the_cut_is_logged(chain) -> None:
    cap = CFG.water_debt_cap_days * DAILY
    result = settle(account(cap - 1000), chain, entitled=4000)
    assert result.capped
    assert result.uncapped_litres == cap + 3000
    assert result.account.debt_litres == cap
    payload = debt_entries(chain)[0].payload
    assert payload["capped"] is True
    assert payload["cap_litres"] == cap
    assert payload["uncapped_litres"] == cap + 3000


def test_long_debt_raises_one_alert_per_run(chain) -> None:
    acc, alerts = account(), []
    for offset in range(CFG.water_debt_alert_days + 2):
        result = settle(acc, chain, day=DAY + timedelta(days=offset))
        acc = result.account
        alerts.append(result.alert)
    # in debt from day 1; alert on day N only
    assert alerts == [False] * (CFG.water_debt_alert_days - 1) + [True, False, False]
    assert acc.alert_raised
    # paid off: the run ends and a new run can alert again
    paid = settle(
        acc,
        chain,
        entitled=0,
        deliveries=[confirmed(litres=acc.debt_litres)],
        day=DAY + timedelta(days=10),
    )
    assert paid.account.debt_litres == 0.0
    assert paid.account.in_debt_since is None and not paid.account.alert_raised
    alert_payloads = [e.payload for e in debt_entries(chain) if e.payload["alert"]]
    assert len(alert_payloads) == 1
    assert alert_payloads[0]["days_in_debt"] == CFG.water_debt_alert_days


def test_every_change_is_one_ledger_entry_and_no_change_writes_nothing(chain) -> None:
    result = settle(account(), chain, deliveries=[confirmed("D7", litres=1000)])
    entries = debt_entries(chain)
    assert len(entries) == 1
    entry = entries[0]
    assert (entry.entity_type, entry.entity_id) == ("water_debt_account", "G1")
    payload = entry.payload
    assert payload["day"] == DAY.isoformat()
    assert payload["debt_before"] == 0.0
    assert payload["debt_after"] == result.account.debt_litres == 1500.0
    assert payload["entitled_litres"] == DAILY
    assert payload["credited_litres"] == 1000.0
    assert payload["counted_delivery_ids"] == ["D7"]
    # entitlement exactly met: debt stays 0, nothing to log
    settle(
        result.account,
        chain,
        deliveries=[confirmed("D8", litres=4000)],
        day=DAY + timedelta(days=1),
    )
    assert debt_entries(chain)[-1].payload["debt_after"] == 0.0
    before = len(chain.entries)
    settle(
        water_debt.settle_day(account(), DAY, 0, (), chain, T0).account,
        chain,
        entitled=0,
        day=DAY + timedelta(days=1),
    )
    assert len(chain.entries) == before


def test_a_day_is_settled_once_and_in_order(chain) -> None:
    result = settle(account(), chain)
    assert result.account.settled_through == DAY
    with pytest.raises(ValueError, match="already settled"):
        settle(result.account, chain)
    with pytest.raises(ValueError, match="already settled"):
        settle(result.account, chain, day=DAY - timedelta(days=1))


@pytest.mark.parametrize(
    ("entitled", "deliveries", "message"),
    [
        (-1, (), "entitled"),
        (DAILY, [DeliveryCredit("D1", -5, "Confirmed")], "litres"),
        (DAILY, [DeliveryCredit("D1", 5000, "Maybe")], "outcome"),
        (DAILY, [confirmed(purpose="gift")], "purpose"),
        (DAILY, [confirmed("D1"), confirmed("D1")], "twice"),
    ],
)
def test_bad_input_is_rejected(chain, entitled, deliveries, message) -> None:
    with pytest.raises(ValueError, match=message):
        settle(account(), chain, entitled=entitled, deliveries=deliveries)
    assert debt_entries(chain) == []


def test_account_needs_a_positive_daily_entitlement(chain) -> None:
    with pytest.raises(ValueError, match="daily_entitlement"):
        settle(DebtAccount("G1", daily_entitlement_litres=0), chain)


def test_credit_from_a_closed_t3_delivery() -> None:
    decision = delivery.compute_outcome(True, 2, 0, window_closed=True, all_replied=True)
    state = delivery.DeliveryState(
        delivery_id="D9",
        stop_id="S1",
        stop_lat=17.4,
        stop_lon=78.5,
        driver_id="DR1",
        representatives=(),
        started_at=T0,
        outcome=decision,
    )
    credit = water_debt.credit_from_delivery(state, litres=5000)
    assert credit == DeliveryCredit("D9", 5000, "Confirmed", "entitled")
    with pytest.raises(ValueError, match="no outcome"):
        water_debt.credit_from_delivery(dataclasses.replace(state, outcome=None), litres=5000)
