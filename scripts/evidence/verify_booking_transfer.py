"""Verify reproducible weights, all input digests and mass normalization."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/evidence"))
from build_booking_transfer import build  # noqa: E402

if __name__ == "__main__":
    for name, content in build().items():
        if (ROOT / name).read_bytes() != content:
            raise SystemExit(f"Building transfer differs: {name}")
    print("Building transfer inputs, geometry and weights verified")
