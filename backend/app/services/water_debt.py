"""Water debt in litres (A6, F11).

An account is whatever unit carries an entitlement (a booking group or a scheduled-supply
ward; A2/A3/A4). Once a day it is settled:

    D' = min(cap, max(0, D + entitled - confirmed delivered))

- Only deliveries whose F12 outcome counts (T3's counts_toward_debt: Confirmed) reduce debt.
  Disputed, Unconfirmed and Failed leave it; trust.unresolved_delivery_changes_shortfall can
  let Unconfirmed count, never the others.
- Outage water (A5) is relief, not entitled service, and never reduces debt.
- Extra water does not bank credit: debt stops at 0.
- The cap is water_debt_cap_days x the account's daily entitlement; the cut is logged.
- Debt outstanding water_debt_alert_days days in a row raises one alert per debt run.
- Every change (and every alert) is one "water_debt_changed" ledger entry; a day that changes
  nothing writes nothing. A day is settled once, in order.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, replace
from datetime import date, datetime
from typing import Any, get_args

from app.config.allocation import ALLOCATION_CONFIG
from app.config.trust import TRUST_CONFIG
from app.services import delivery
from app.services.ledger_port import LedgerPort

SYSTEM = "system"
PURPOSES = ("entitled", "outage")
OUTCOMES = get_args(delivery.Outcome)


@dataclass(frozen=True)
class DebtAccount:
    account_id: str
    daily_entitlement_litres: float  # reference for the cap
    debt_litres: float = 0.0
    in_debt_since: date | None = None  # first day of the current debt run
    alert_raised: bool = False  # alert already raised in the current run
    settled_through: date | None = None


@dataclass(frozen=True)
class DeliveryCredit:
    delivery_id: str
    litres: float
    outcome: str  # F12 outcome from T3
    purpose: str = "entitled"  # "entitled" (booked/scheduled service) or "outage" (A5 relief)


@dataclass(frozen=True)
class DebtChange:
    account: DebtAccount
    debt_before: float
    entitled_litres: float
    credited_litres: float
    uncapped_litres: float
    cap_litres: float
    capped: bool
    days_in_debt: int
    alert: bool  # alert raised by this settlement


def account_as_dict(account: DebtAccount) -> dict[str, Any]:
    """A JSON-safe copy (stored plans and the debt store keep accounts this way)."""
    return {
        "account_id": account.account_id,
        "daily_entitlement_litres": account.daily_entitlement_litres,
        "debt_litres": account.debt_litres,
        "in_debt_since": account.in_debt_since.isoformat() if account.in_debt_since else None,
        "alert_raised": account.alert_raised,
        "settled_through": account.settled_through.isoformat() if account.settled_through else None,
    }


def account_from_dict(data: Mapping[str, Any]) -> DebtAccount:
    def day(value: Any) -> date | None:
        return date.fromisoformat(value) if value else None

    return DebtAccount(
        account_id=str(data["account_id"]),
        daily_entitlement_litres=float(data["daily_entitlement_litres"]),
        debt_litres=float(data["debt_litres"]),
        in_debt_since=day(data.get("in_debt_since")),
        alert_raised=bool(data.get("alert_raised", False)),
        settled_through=day(data.get("settled_through")),
    )


def counts_toward_debt(outcome: str) -> bool:
    """T3's rule (only Confirmed), plus Unconfirmed if the trust flag allows it."""
    return delivery.counts_toward_debt(outcome) or (
        TRUST_CONFIG.unresolved_delivery_changes_shortfall and outcome == "Unconfirmed"
    )


def credit_from_delivery(
    state: delivery.DeliveryState, litres: float, purpose: str = "entitled"
) -> DeliveryCredit:
    """A closed T3 delivery as a debt credit."""
    if state.outcome is None:
        raise ValueError(f"Delivery {state.delivery_id} has no outcome yet")
    return DeliveryCredit(state.delivery_id, litres, state.outcome.outcome, purpose)


def cap_litres(account: DebtAccount) -> float:
    return ALLOCATION_CONFIG.water_debt_cap_days * account.daily_entitlement_litres


def _validate(
    account: DebtAccount, day: date, entitled: float, credits: list[DeliveryCredit]
) -> None:
    if account.daily_entitlement_litres <= 0:
        raise ValueError(f"Account {account.account_id} needs a positive daily_entitlement")
    if account.settled_through is not None and day <= account.settled_through:
        raise ValueError(f"{day} is already settled for account {account.account_id}")
    if entitled < 0:
        raise ValueError("entitled litres cannot be negative")
    seen: set[str] = set()
    for credit in credits:
        if credit.litres < 0:
            raise ValueError(f"Delivery {credit.delivery_id}: litres cannot be negative")
        if credit.outcome not in OUTCOMES:
            raise ValueError(f"Delivery {credit.delivery_id}: unknown outcome {credit.outcome}")
        if credit.purpose not in PURPOSES:
            raise ValueError(f"Delivery {credit.delivery_id}: unknown purpose {credit.purpose}")
        if credit.delivery_id in seen:
            raise ValueError(f"Delivery {credit.delivery_id} is listed twice")
        seen.add(credit.delivery_id)


def settle_day(
    account: DebtAccount,
    day: date,
    entitled_litres: float,
    deliveries: Iterable[DeliveryCredit],
    ledger: LedgerPort,
    now: datetime,
    actor: str = SYSTEM,
) -> DebtChange:
    """Settle one day: add the entitlement, subtract counted water, cap, alert, log."""
    credits = list(deliveries)
    _validate(account, day, entitled_litres, credits)
    counted = [c for c in credits if c.purpose == "entitled" and counts_toward_debt(c.outcome)]
    not_counted = [
        [c.delivery_id, "outage" if c.purpose == "outage" else c.outcome]
        for c in credits
        if c not in counted
    ]
    credited = sum(c.litres for c in counted)
    uncapped = max(0.0, account.debt_litres + entitled_litres - credited)
    cap = cap_litres(account)
    debt = min(uncapped, cap)

    if debt > 0:
        since = account.in_debt_since or day
        days_in_debt = (day - since).days + 1
        alert = not account.alert_raised and days_in_debt >= ALLOCATION_CONFIG.water_debt_alert_days
        updated = replace(
            account,
            debt_litres=debt,
            in_debt_since=since,
            alert_raised=account.alert_raised or alert,
            settled_through=day,
        )
    else:
        days_in_debt, alert = 0, False
        updated = replace(
            account, debt_litres=0.0, in_debt_since=None, alert_raised=False, settled_through=day
        )

    if debt != account.debt_litres or alert:
        ledger.append(
            "water_debt_changed",
            {
                "entity_type": "water_debt_account",
                "entity_id": account.account_id,
                "day": day.isoformat(),
                "at": now.isoformat(),
                "debt_before": round(account.debt_litres, 3),
                "debt_after": round(debt, 3),
                "entitled_litres": round(entitled_litres, 3),
                "credited_litres": round(credited, 3),
                "counted_delivery_ids": [c.delivery_id for c in counted],
                "not_counted": not_counted,
                "uncapped_litres": round(uncapped, 3),
                "cap_litres": round(cap, 3),
                "capped": uncapped > cap,
                "days_in_debt": days_in_debt,
                "alert": alert,
            },
            actor,
        )
    return DebtChange(
        account=updated,
        debt_before=account.debt_litres,
        entitled_litres=entitled_litres,
        credited_litres=credited,
        uncapped_litres=uncapped,
        cap_litres=cap,
        capped=uncapped > cap,
        days_in_debt=days_in_debt,
        alert=alert,
    )
