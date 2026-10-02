"""Verify the E5 screen is deterministic and its provenance hashes match."""

from __future__ import annotations

import hashlib
import json

from build_underserved import CHECKS, ROOT, ROWS, SUMMARY, build

if __name__ == "__main__":
    expected = build()
    checks = json.loads(expected[CHECKS])
    checks["outputs_sha256"] = {
        path: hashlib.sha256(content).hexdigest()
        for path, content in expected.items()
        if path in (ROWS, SUMMARY)
    }
    expected[CHECKS] = (json.dumps(checks, indent=2, sort_keys=True) + "\n").encode()
    for relative, content in expected.items():
        target = ROOT / relative
        if not target.is_file() or target.read_bytes() != content:
            raise SystemExit(f"E5 output differs: {relative}; rebuild and review")
    result = json.loads(expected[ROWS])
    summary = json.loads(expected[SUMMARY])
    if len(result["data_review_queue"]) != 145 or result["field_check_list"]:
        raise SystemExit("E5 fail-closed checks differ from the current E1/E2 evidence state")
    if summary["eligible_count"] != 0 or summary["field_check_count"] != 0:
        raise SystemExit("E5 unexpectedly screened unvalidated real-world inputs")
    print("P1:E5 verified: inputs, output hashes, 145 review rows, zero unsupported field flags")
