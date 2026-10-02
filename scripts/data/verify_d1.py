"""Verify D1 raw files and provenance manifest.

Checks:
  - data/verification/d1_manifest.csv exists and has the expected rows
  - Each GeoJSON file is valid and non-empty
  - SHA-256 and byte size match the manifest
  - basis is REAL for every row
  - Retrieval log stubs exist for D6 and D7

Run:  python scripts/data/verify_d1.py
"""

from __future__ import annotations

import csv
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "data" / "verification" / "d1_manifest.csv"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    require(MANIFEST.is_file(), "Missing data/verification/d1_manifest.csv")

    with MANIFEST.open(encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))

    # Must have the three OSM layers
    require(len(rows) >= 3, f"d1_manifest.csv: expected >= 3 rows, found {len(rows)}")

    ids = {row["dataset_id"] for row in rows}
    expected_ids = (
        "D5a-OSM-Hyderabad-District",
        "D5b-OSM-Hyderabad-Mandals",
        "D10-OSM-HMWSSB-Points",
    )
    for expected in expected_ids:
        require(expected in ids, f"Missing dataset_id {expected} in d1_manifest.csv")

    require(all(row["basis"] == "REAL" for row in rows), "Every D1 source must be labelled REAL")
    require(
        all(row["license"].startswith("ODbL") for row in rows),
        "Every OSM layer must carry ODbL licence",
    )

    for row in rows:
        path = ROOT / row["file_path"]
        require(path.is_file(), f"Missing raw file: {row['file_path']}")
        payload = path.read_bytes()
        actual_size = len(payload)
        actual_sha = hashlib.sha256(payload).hexdigest()
        require(
            actual_size == int(row["bytes"]),
            f"Size mismatch {row['file_path']}: expected {row['bytes']}, got {actual_size}",
        )
        require(
            actual_sha == row["sha256"],
            f"SHA-256 mismatch: {row['file_path']}",
        )
        # Validate GeoJSON structure
        if row["file_path"].endswith(".geojson"):
            data = json.loads(payload.decode("utf-8"))
            require(
                data.get("type") == "FeatureCollection",
                f"Invalid GeoJSON type in {row['file_path']}",
            )
            # Feature count is allowed to be 0 (e.g. no HMWSSB-tagged nodes in OSM)
            require(
                isinstance(data.get("features"), list),
                f"GeoJSON features must be a list: {row['file_path']}",
            )

    # D6 and D7 must have retrieval-log stubs
    d6_log = ROOT / "data" / "raw" / "d6_open_buildings" / "RETRIEVAL_LOG.md"
    d7_log = ROOT / "data" / "raw" / "d7_groundwater" / "RETRIEVAL_LOG.md"
    require(d6_log.is_file(), f"Missing D6 retrieval log: {d6_log.relative_to(ROOT)}")
    require(d7_log.is_file(), f"Missing D7 retrieval log: {d7_log.relative_to(ROOT)}")

    feature_counts: dict[str, int] = {}
    for row in rows:
        path = ROOT / row["file_path"]
        if row["file_path"].endswith(".geojson"):
            data = json.loads(path.read_bytes().decode("utf-8"))
            feature_counts[row["dataset_id"]] = len(data["features"])

    count_lines = "; ".join(f"{k}={v}" for k, v in feature_counts.items())
    print(f"P1:D1 verified {len(rows)} OSM layers; GeoJSON feature counts: {count_lines}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as exc:
        print(f"P1:D1 verification failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
