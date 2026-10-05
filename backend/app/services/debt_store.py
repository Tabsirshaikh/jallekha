"""Water debt accounts and closed days in the database (A6 on stored plans, F20).

`save` writes a closed day and its settled accounts in one transaction; a day is closed once
(DebtDayConflict otherwise). Accounts load back equal to what was saved.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError

from app.db import make_session_factory
from app.models import DebtDay, WaterDebtAccount
from app.services import water_debt
from app.services.day_close import ClosedDay
from app.services.water_debt import DebtAccount


class DebtDayConflict(Exception):
    """That day was already closed, or is not the next day to close (days close in order)."""


def _utc(moment: datetime) -> datetime:
    return moment if moment.tzinfo else moment.replace(tzinfo=UTC)


class DebtStore:
    def __init__(self, engine: Engine) -> None:
        self._sessions = make_session_factory(engine)

    def accounts(self) -> dict[str, DebtAccount]:
        with self._sessions() as session:
            rows = session.scalars(select(WaterDebtAccount).order_by(WaterDebtAccount.account_id))
            return {r.account_id: self._account(r) for r in rows}

    def account(self, account_id: str) -> DebtAccount | None:
        with self._sessions() as session:
            row = session.scalar(
                select(WaterDebtAccount).where(WaterDebtAccount.account_id == account_id)
            )
            return self._account(row) if row else None

    @staticmethod
    def _account(row: WaterDebtAccount) -> DebtAccount:
        return water_debt.account_from_dict(
            {
                "account_id": row.account_id,
                "daily_entitlement_litres": row.daily_entitlement_litres,
                "debt_litres": row.debt_litres,
                "in_debt_since": row.in_debt_since,
                "alert_raised": row.alert_raised,
                "settled_through": row.settled_through,
            }
        )

    def save(self, closed: ClosedDay, closed_by: str, reason: str) -> None:
        summary = {
            w.ward_id: {k: v for k, v in asdict(w).items() if k != "ward_id"} for w in closed.wards
        }
        try:
            with self._sessions.begin() as session:
                # Days are closed one after another: refuse a gap or a step back, even when
                # another process closed a day since this close was checked.
                last = session.scalar(select(DebtDay.day).order_by(DebtDay.day.desc()).limit(1))
                expected = (date.fromisoformat(last) + timedelta(days=1)) if last else None
                if expected is not None and closed.day != expected:
                    raise DebtDayConflict(
                        "Days are closed one after another: the next day to close is "
                        f"{expected.isoformat()}, not {closed.day.isoformat()}"
                    )
                session.add(
                    DebtDay(
                        day=closed.day.isoformat(),
                        plan_id=closed.plan_id,
                        plan_digest=closed.plan_digest,
                        closed_by=closed_by,
                        reason=reason.strip(),
                        summary_json=json.dumps(summary, sort_keys=True),
                    )
                )
                session.flush()  # the unique day first: a second close stops here
                for account in closed.accounts:
                    data = water_debt.account_as_dict(account)
                    row = session.scalar(
                        select(WaterDebtAccount).where(
                            WaterDebtAccount.account_id == account.account_id
                        )
                    )
                    if row is None:
                        row = WaterDebtAccount(account_id=account.account_id)
                        session.add(row)
                    row.daily_entitlement_litres = data["daily_entitlement_litres"]
                    row.debt_litres = data["debt_litres"]
                    row.in_debt_since = data["in_debt_since"]
                    row.alert_raised = data["alert_raised"]
                    row.settled_through = data["settled_through"]
        except IntegrityError as exc:
            raise DebtDayConflict(f"{closed.day.isoformat()} is already closed") from exc

    def closed_days(self) -> list[dict[str, Any]]:
        """Every closed day, oldest first."""
        with self._sessions() as session:
            rows = session.scalars(select(DebtDay).order_by(DebtDay.day)).all()
            return [self._day(r) for r in rows]

    @staticmethod
    def _day(row: DebtDay) -> dict[str, Any]:
        return {
            "day": row.day,
            "plan_id": row.plan_id,
            "plan_digest": row.plan_digest,
            "closed_by": row.closed_by,
            "reason": row.reason,
            "closed_at": _utc(row.created_at).isoformat(),
            "wards": json.loads(row.summary_json),
        }

    def last_closed_day(self) -> date | None:
        with self._sessions() as session:
            day = session.scalar(select(DebtDay.day).order_by(DebtDay.day.desc()).limit(1))
            return date.fromisoformat(day) if day else None

    def ward_last_day(self, ward_id: str) -> dict[str, Any] | None:
        """The ward's line of the latest closed day that settled it (no officer reason)."""
        for day in reversed(self.closed_days()):
            if ward_id in day["wards"]:
                return {"day": day["day"], "plan_id": day["plan_id"], **day["wards"][ward_id]}
        return None
