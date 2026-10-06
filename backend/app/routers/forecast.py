"""Forecast endpoints (T10): T2's forecast table and backtest, and T8's shortage list.

Shapes as in docs/api_shapes.md sections 6 and 7.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Query

from app.auth import require_roles
from app.config.api import ApiConfig
from app.config.env import REPO_ROOT
from app.routers.common import UNAVAILABLE, csv_rows, typed

router = APIRouter(tags=["forecast"])

TABLE = "data/derived/forecast_table.csv"
BACKTEST = "data/derived/forecast_backtest.csv"
SHORTAGE = "data/derived/shortage_risk.csv"
HISTORY = "data/derived/forecast_history.csv"
ACCURACY = "data/derived/forecast_accuracy.csv"

Officer = Depends(require_roles("officer"))
Offset = Annotated[int, Query(ge=0)]
Limit = Annotated[int, Query(ge=1, le=ApiConfig.max_limit)]


@router.get("/forecast", dependencies=[Officer])
def forecast(
    level: Literal["city", "section"] | None = None,
    section: str | None = None,
    month: Annotated[str | None, Query(pattern=r"^\d{4}-\d{2}$")] = None,
    offset: Offset = 0,
    limit: Limit = ApiConfig.default_limit,
) -> dict[str, Any]:
    rows = [
        typed(r)
        for r in csv_rows(TABLE)
        if (level is None or r["level"] == level)
        and (section is None or r["section"] == section)
        and (month is None or r["month"] == month)
    ]
    return {"items": rows[offset : offset + limit], "total": len(rows)}


@router.get("/forecast/backtest", dependencies=[Officer])
def backtest(offset: Offset = 0, limit: Limit = ApiConfig.default_limit) -> dict[str, Any]:
    rows = [typed(r) for r in csv_rows(BACKTEST)]
    return {"items": rows[offset : offset + limit], "total": len(rows)}


def _filtered_rows(path: str, level: str | None, section: str | None, offset: int, limit: int):
    rows = [
        typed(r)
        for r in csv_rows(path)
        if (level is None or r["level"] == level) and (section is None or r["section"] == section)
    ]
    return {"items": rows[offset : offset + limit], "total": len(rows)}


@router.get("/forecast/history", dependencies=[Officer])
def history(
    level: Literal["city", "section"] | None = None,
    section: str | None = None,
    offset: Offset = 0,
    limit: Limit = ApiConfig.default_limit,
) -> dict[str, Any]:
    """Last twelve available actual months; historical section identity can be approximate."""
    return _filtered_rows(HISTORY, level, section, offset, limit)


@router.get("/forecast/accuracy", dependencies=[Officer])
def accuracy(
    level: Literal["city", "section"] | None = None,
    section: str | None = None,
    offset: Offset = 0,
    limit: Limit = ApiConfig.default_limit,
) -> dict[str, Any]:
    """Past rolling-origin estimates, explicitly distinct from previously issued forecasts."""
    return _filtered_rows(ACCURACY, level, section, offset, limit)


@router.get("/shortage", dependencies=[Officer])
def shortage(offset: Offset = 0, limit: Limit = ApiConfig.default_limit) -> dict[str, Any]:
    """T8's risk list; an empty, UNAVAILABLE answer only if its file is missing."""
    if not (REPO_ROOT / SHORTAGE).exists():
        return {
            "items": [],
            "total": 0,
            "basis": UNAVAILABLE,
            "reason": "T8 shortage warning is not merged",
        }
    rows = [typed(r) for r in csv_rows(SHORTAGE)]
    return {"items": rows[offset : offset + limit], "total": len(rows), "basis": "DERIVED"}
