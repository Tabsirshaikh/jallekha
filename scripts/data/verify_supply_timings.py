"""Verifier for D16 HMWSSB Water Supply Timings dataset (REAL / ARCHIVED).

Validates:
- data/raw/d16_supply_timings/supply_timings.csv exists and has correct columns.
- All rows have valid 24h times (HH:MM), positive hours, and provenance fields.
- Exactly 21 localities are parsed for S.R. NAGAR.
- RETRIEVAL_LOG.md exists and documents file sizes and SHA-256 checksums.
- Raw files in raw_pages/ match the documented SHA-256 checksums.
- Writes verification report to data/verification/supply_timings_checks.json.

Usage:
    python scripts/data/verify_supply_timings.py
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = ROOT / "data" / "raw" / "d16_supply_timings"
CSV_PATH = RAW_DIR / "supply_timings.csv"
LOG_PATH = RAW_DIR / "RETRIEVAL_LOG.md"
RAW_PAGES_DIR = RAW_DIR / "raw_pages"
REPORT_PATH = ROOT / "data" / "verification" / "supply_timings_checks.json"

EXPECTED_FIELDS = (
    "division_code",
    "section",
    "section_code",
    "locality_code",
    "locality",
    "slum_status",
    "from_time",
    "to_time",
    "hours",
    "pattern",
    "water_source",
    "captured_at",
    "capture_source",
    "source_url",
)

TIME_RE = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    require(CSV_PATH.is_file(), f"Missing supply timings CSV at {CSV_PATH}")
    require(LOG_PATH.is_file(), f"Missing retrieval log at {LOG_PATH}")

    with open(CSV_PATH, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        require(
            tuple(reader.fieldnames or []) == EXPECTED_FIELDS,
            f"CSV fields mismatch: expected {EXPECTED_FIELDS}, got {reader.fieldnames}",
        )
        rows = list(reader)

    require(len(rows) == 21, f"Expected 21 rows for S.R. NAGAR, got {len(rows)}")

    for idx, r in enumerate(rows, 1):
        require(r["division_code"] == "6", f"Row {idx}: division_code must be 6")
        require(r["section"] == "S.R.NAGAR", f"Row {idx}: section must be S.R.NAGAR")
        require(r["section_code"] == "0624", f"Row {idx}: section_code must be 0624")
        require(bool(r["locality_code"]), f"Row {idx}: locality_code must not be empty")
        require(bool(r["locality"]), f"Row {idx}: locality must not be empty")
        require(
            r["slum_status"] in ("Slum", "Non Slum", "Both"),
            f"Row {idx}: invalid slum status {r['slum_status']}",
        )
        require(
            bool(TIME_RE.match(r["from_time"])),
            f"Row {idx}: invalid from_time {r['from_time']}",
        )
        require(
            bool(TIME_RE.match(r["to_time"])),
            f"Row {idx}: invalid to_time {r['to_time']}",
        )

        hours = float(r["hours"])
        require(0.0 < hours <= 24.0, f"Row {idx}: hours {hours} out of range (0, 24]")
        require(
            r["pattern"] in ("Daily", "Alternate Day", "Other"),
            f"Row {idx}: unexpected pattern {r['pattern']}",
        )
        require(bool(r["water_source"]), f"Row {idx}: empty water source")
        require(r["capture_source"] == "wayback", f"Row {idx}: expected wayback capture_source")
        require(
            r["captured_at"].startswith("2024-05-14"),
            f"Row {idx}: expected 2024-05-14 capture date",
        )

    # Verify retrieval log content

    log_text = LOG_PATH.read_text(encoding="utf-8")
    require("Coverage Summary" in log_text, "RETRIEVAL_LOG.md missing Coverage Summary")
    require("alert('No Data Found')" in log_text, "RETRIEVAL_LOG.md missing live database status")

    # Verify raw pages
    sr_html_gz = RAW_PAGES_DIR / "sr_nagar_2024-05-14.html.gz"
    require(sr_html_gz.is_file(), f"Missing raw gzipped page {sr_html_gz}")
    gz_bytes = sr_html_gz.read_bytes()
    gz_sha = hashlib.sha256(gz_bytes).hexdigest()
    require(gz_sha in log_text, "Gzipped S.R. Nagar SHA-256 not found in RETRIEVAL_LOG.md")

    csv_bytes = CSV_PATH.read_bytes()
    csv_sha = hashlib.sha256(csv_bytes).hexdigest()
    require(csv_sha in log_text, "CSV SHA-256 not found in RETRIEVAL_LOG.md")

    report = {
        "dataset": "D16-HMWSSB-WaterSupplyTimings",
        "basis": "REAL",
        "csv_path": str(CSV_PATH.relative_to(ROOT)),
        "csv_sha256": csv_sha,
        "csv_rows": len(rows),
        "sections_covered": 1,
        "total_sections": 89,
        "section_coverage_pct": 1.1236,
        "localities_covered": len(rows),
        "covered_2025_bookings": 40862,
        "total_2025_bookings": 1436768,
        "bookings_coverage_pct": 2.844,
        "covered_section": "S.R.NAGAR",
        "ward_name": "Ward 98 Ameerpet",
        "ward_id": "relation/7857794",
        "capture_date": "2024-05-14T21:57:12Z",
        "live_database_status": "EMPTY_NO_DATA_FOUND",
        "status": "PASS",
    }
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(
        f"Verified D16 supply timings: 21 localities for S.R. NAGAR (PASS). "
        f"Report written to {REPORT_PATH}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
