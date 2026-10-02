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
    if len(result["rows"]) != 145:
        raise SystemExit("E5 must report every one of the 145 wards")
    if summary["eligible_count"] + len(result["data_review_queue"]) != 145:
        raise SystemExit("E5 eligible and review counts do not add up")
    candidates = [r for r in result["rows"] if r["field_check_candidate"]]
    if len(candidates) != summary["field_check_count"] or any(
        "APPROXIMATE_BOOKING_TRANSFER" not in r["input_notes"] for r in candidates
    ):
        raise SystemExit("E5 field-check candidates are inconsistent or unlabelled")
    if any(r["field_check_candidate"] is not None for r in result["data_review_queue"]):
        raise SystemExit("A ward in data review cannot be a field-check candidate")
    print(
        f"P1:E5 verified: inputs, output hashes, {summary['eligible_count']} screened wards, "
        f"{summary['field_check_count']} labelled field-check candidates"
    )
