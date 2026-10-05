"""Fetch D13: Chicago 311 water complaints 2022-2023 with the duplicate flag (REAL, another city).

The solution document's F13 calibration used 31,098 rows / 4,994 duplicates; that extract was
never found (data/verification/SOURCES.md). The Chicago dataset (v6vf-nfxy) is refreshed several
times a day, so it cannot be re-pulled byte for byte. This pulls the closest match: the four
Department of Water Management types about water supply (No Water, Low Water Pressure, Check
for Leak, Water Quality Concern), created 2022-01-01 to 2023-12-31, and registers the file in
data/verification/source_manifest.csv (dataset D13-CHICAGO-311) so calibrate_dedup.py accepts it.

    python scripts/data/fetch_d13_chicago.py
"""

from __future__ import annotations

import csv
import hashlib
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "data/raw/d13_chicago_311"
OUT = OUT_DIR / "chicago_311_water_2022_2023.csv"
MANIFEST = ROOT / "data/verification/source_manifest.csv"
DATASET_ID = "D13-CHICAGO-311"
API = "https://data.cityofchicago.org/resource/v6vf-nfxy.csv"
TYPES = (
    "No Water Complaint",
    "Low Water Pressure Complaint",
    "Check for Leak",
    "Water Quality Concern",
)
FIELDS = (
    "sr_number",
    "sr_type",
    "created_date",
    "latitude",
    "longitude",
    "duplicate",
    "parent_sr_number",
)


def url() -> str:
    types = ",".join(f"'{t}'" for t in TYPES)
    query = {
        "$select": ",".join(FIELDS),
        "$where": (
            "created_date between '2022-01-01T00:00:00' and '2023-12-31T23:59:59' "
            f"and sr_type in({types})"
        ),
        "$order": "sr_number",
        "$limit": "100000",
    }
    return f"{API}?{urllib.parse.urlencode(query)}"


def register(sha256: str, size: int, rows: int, duplicates: int, retrieved: str) -> None:
    with MANIFEST.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = reader.fieldnames or []
        entries = [r for r in reader if r["dataset_id"] != DATASET_ID]
    entries.append(
        {
            "dataset_id": DATASET_ID,
            "file_path": OUT.relative_to(ROOT).as_posix(),
            "source_url": url(),
            "retrieved_at_utc": retrieved,
            "source_modified": "refreshed several times a day (Chicago Data Portal)",
            "license": "City of Chicago Data Portal terms of use",
            "geography": "City of Chicago",
            "granularity": "one row per 311 service request",
            "basis": "REAL",
            "sha256": sha256,
            "bytes": str(size),
            "notes": (
                f"{rows} rows, {duplicates} duplicates; the four water-supply types, 2022-2023. "
                "Closest match to the lost 31,098-row extract (another city; F13 calibration)."
            ),
        }
    )
    with MANIFEST.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(entries)


def main() -> None:
    with urllib.request.urlopen(url(), timeout=300) as response:
        body = response.read()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT.write_bytes(body)
    with OUT.open(encoding="utf-8", newline="") as handle:
        records = list(csv.DictReader(handle))
    duplicates = sum(r["duplicate"].lower() == "true" for r in records)
    sha256 = hashlib.sha256(body).hexdigest()
    retrieved = datetime.now(UTC).replace(microsecond=0).isoformat()
    register(sha256, len(body), len(records), duplicates, retrieved)
    print(f"Wrote {OUT} ({len(records)} rows, {duplicates} duplicates, sha256 {sha256[:12]})")


if __name__ == "__main__":
    main()
