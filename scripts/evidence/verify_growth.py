"""Offline E3 integrity and deterministic output verifier."""

import hashlib
import json

from build_growth import OUT, ROOT, aggregate

if __name__ == "__main__":
    expected = aggregate()
    checks = json.loads(expected["data/verification/growth_checks.json"])
    checks["output_sha256"] = {
        path: hashlib.sha256(value).hexdigest()
        for path, value in expected.items()
        if path.startswith(OUT)
    }
    expected["data/verification/growth_checks.json"] = (
        json.dumps(checks, indent=2, sort_keys=True) + "\n"
    ).encode()
    for path, data in expected.items():
        target = ROOT / path
        if not target.is_file() or target.read_bytes() != data:
            raise SystemExit(f"E3 output differs: {path}; rebuild and review")
    print("P1:E3 verified: cached source checksums, coverage gates, formulas and outputs")
