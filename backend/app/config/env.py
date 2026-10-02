"""Read settings from environment variables; see .env.example for the full list."""

from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]


def env_str(name: str, default: str | None = None) -> str | None:
    """Return the variable's value, or `default` when it is unset or blank."""
    value = os.environ.get(name, "").strip()
    return value or default
