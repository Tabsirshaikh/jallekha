from __future__ import annotations

from sqlalchemy import Boolean, Float, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, IdTimestampMixin


class WaterDebtAccount(IdTimestampMixin, Base):
    """One A6 water debt account (F11), saved by closing a day (services/day_close.py).

    `account_id` is the plan group it raises (`ward:<ward id>`). Dates are YYYY-MM-DD Hyderabad
    days; `settled_through` is the last closed day that settled it. Every change is also a
    `water_debt_changed` ledger entry.
    """

    __tablename__ = "water_debt_account"

    account_id: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    daily_entitlement_litres: Mapped[float] = mapped_column(Float)
    debt_litres: Mapped[float] = mapped_column(Float, default=0.0)
    in_debt_since: Mapped[str | None] = mapped_column(String(10))
    alert_raised: Mapped[bool] = mapped_column(Boolean, default=False)
    settled_through: Mapped[str | None] = mapped_column(String(10))
