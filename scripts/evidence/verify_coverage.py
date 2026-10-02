"""Verify deterministic E6 layers and their fail-closed evidence semantics."""

from __future__ import annotations

import json

from build_coverage import CHECKS, MANIFEST, ROOT, build

if __name__ == "__main__":
    expected = build()
    for relative, content in expected.items():
        target = ROOT / relative
        if not target.is_file() or target.read_bytes() != content:
            raise SystemExit(f"E6 output differs: {relative}; rebuild and review")
    manifest = json.loads(expected[MANIFEST])
    if len(manifest["layers"]) != 3 or manifest["feature_count"] != 145:
        raise SystemExit("E6 must contain exactly three 145-feature layers")
    if {item["non_null_value_count"] for item in manifest["layers"]} != {0, 134}:
        raise SystemExit("E6 null/value coverage differs from reviewed E2/E4/E5 state")
    excluded = {item["layer_id"] for item in manifest["excluded_layers"]}
    if "people_within_500m_public_tap" not in excluded:
        raise SystemExit("E6 must explicitly record why the unsupported tap layer is excluded")
    checks = json.loads(expected[CHECKS])
    if set(checks["outputs_sha256"]) != {
        item["file"].join(["data/derived/coverage/", ""]) for item in manifest["layers"]
    } | {MANIFEST}:
        raise SystemExit("E6 output hash register is incomplete")
    print("P1:E6 verified: three layers, 145 wards, nulls preserved, 500 m layer excluded")
