"""Shared helpers for the thin T10 routers: file reading, typing, paging, error responses.

Shapes follow docs/api_shapes.md (agreed with P4 on 2026-10-03). No business logic here.
"""

from __future__ import annotations

import csv
import json
from datetime import UTC, datetime
from functools import lru_cache
from typing import Any

from fastapi import HTTPException
from fastapi.responses import JSONResponse

from app.config.env import REPO_ROOT
from app.errors import error_response

UNAVAILABLE = "UNAVAILABLE"


def get_now() -> datetime:
    """The current time (UTC); a dependency so tests can fix it."""
    return datetime.now(UTC)


def typed(row: dict[str, str]) -> dict[str, Any]:
    """CSV text -> JSON types (docs/api_shapes.md): empty -> null, True / False -> boolean,
    integer text -> integer, decimal text -> number, anything else stays text."""
    out: dict[str, Any] = {}
    for key, value in row.items():
        if value == "":
            out[key] = None
        elif value in ("True", "False"):
            out[key] = value == "True"
        else:
            try:
                out[key] = int(value)
            except ValueError:
                try:
                    out[key] = float(value)
                except ValueError:
                    out[key] = value
    return out


@lru_cache(maxsize=32)
def _csv_text(path: str, mtime: float) -> tuple[dict[str, str], ...]:
    with (REPO_ROOT / path).open(encoding="utf-8-sig", newline="") as handle:
        return tuple(csv.DictReader(handle))


def csv_rows(path: str) -> list[dict[str, str]]:
    """Rows of a committed data file (as text), cached until the file changes."""
    return [dict(r) for r in _csv_text(path, (REPO_ROOT / path).stat().st_mtime)]


@lru_cache(maxsize=32)
def _json(path: str, mtime: float) -> Any:
    return json.loads((REPO_ROOT / path).read_text(encoding="utf-8"))


def json_file(path: str) -> Any:
    return _json(path, (REPO_ROOT / path).stat().st_mtime)


def page(items: list[Any], offset: int, limit: int) -> dict[str, Any]:
    return {
        "total": len(items),
        "offset": offset,
        "limit": limit,
        "items": items[offset : offset + limit],
    }


def not_found(what: str) -> HTTPException:
    return HTTPException(404, f"{what} not found")


def invalid(message: str | None) -> JSONResponse:
    """A malformed or invalid single-item request: 422 in the shared error shape."""
    return error_response(422, "validation_error", message or "Request is not valid")


def unavailable(reason: str) -> dict[str, Any]:
    return {"value": None, "basis": UNAVAILABLE, "reason": reason}
