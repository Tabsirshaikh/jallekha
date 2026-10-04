"""T10: export the API's OpenAPI document to docs/openapi.json.

Usage:
    python scripts/api/export_openapi.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.main import app  # noqa: E402

OUT = ROOT / "docs/openapi.json"


def main() -> int:
    OUT.write_text(json.dumps(app.openapi(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"OpenAPI -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
