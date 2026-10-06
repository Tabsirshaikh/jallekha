"""Wrapper for D16 supply timings verifier in data/verification/."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "data"))

from verify_supply_timings import main

if __name__ == "__main__":
    sys.exit(main())
