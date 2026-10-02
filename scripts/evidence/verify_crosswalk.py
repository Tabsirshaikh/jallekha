"""Verify E1 crosswalk artifacts against all data contracts and acceptance criteria.

Checks:
  - census_to_ghmc_2016.csv exists, valid CSV, basis == 'DERIVED'
  - crosswalk_summary.json and crosswalk_checks.json exist and match
  - Target geo version strictly equals GHMC_2016_150 (300-ward claim blocked)
  - Acceptance criterion: wards 104 and 107 are NEVER matched
  - Acceptance criterion: known missing polygons (3, 4, 11, 13, 31, 113) are never false-matched
  - Acceptance criterion: coverage is reported (> 85% for GHMC wards)
  - HH-14 gotcha: headers asserted and 0-based column indexing validated

Run: python scripts/evidence/verify_crosswalk.py
"""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CROSSWALK_CSV = ROOT / "data" / "derived" / "crosswalk" / "census_to_ghmc_2016.csv"
SUMMARY_JSON = ROOT / "data" / "derived" / "crosswalk" / "crosswalk_summary.json"
CHECKS_JSON = ROOT / "data" / "verification" / "crosswalk_checks.json"

TARGET_GEO_VERSION = "GHMC_2016_150"
KNOWN_MISSING_POLYGON_WARDS = frozenset([3, 4, 11, 13, 31, 113])
NEVER_MATCHED_WARDS = frozenset([104, 107])


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def verify_hh14_headers() -> None:
    """Assert HH-14 headers and 0-based column indexing per features.csv technical note."""
    import openpyxl

    for rel_path in (
        "data/raw/census/hyderabad/hh14.xlsx",
        "data/raw/census/rangareddy/hh14.xlsx",
    ):
        fpath = ROOT / rel_path
        require(fpath.is_file(), f"Missing HH-14 file: {rel_path}")

        wb = openpyxl.load_workbook(fpath, read_only=True, data_only=True)
        ws = wb.active
        rows = list(ws.iter_rows(values_only=True, max_row=8))
        wb.close()

        require(len(rows) >= 7, f"HH-14 file {rel_path} has fewer than 7 header rows")

        # Row 3 (0-indexed) contains primary field names
        hdr_row = rows[3]
        require(hdr_row[0] == "State Code", f"{rel_path}: index 0 must be 'State Code'")
        require(hdr_row[2] == "District Code", f"{rel_path}: index 2 must be 'District Code'")
        require(hdr_row[7] == "Ward No", f"{rel_path}: index 7 must be 'Ward No'")
        require(hdr_row[8] == "Area Name", f"{rel_path}: index 8 must be 'Area Name'")

        # Row 6 (0-indexed) contains 1-based printed table indices [1, 2, 3, 4, 5, 6, 7, 8, ...]
        indices_row = rows[6]
        require(indices_row[0] == 1, f"{rel_path}: row 6 column 0 must be printed index 1")
        require(
            indices_row[7] == 8,
            f"{rel_path}: row 6 column 7 ('Ward No') must be printed index 8",
        )

        # Verify first data row (row 7) has state code '28'
        data_row = rows[7]
        require(data_row[0] == "28", f"{rel_path}: row 7 state code must be '28'")


def main() -> int:
    print("Verifying E1 crosswalk artifacts...")

    require(CROSSWALK_CSV.is_file(), f"Missing {CROSSWALK_CSV}")
    require(SUMMARY_JSON.is_file(), f"Missing {SUMMARY_JSON}")
    require(CHECKS_JSON.is_file(), f"Missing {CHECKS_JSON}")

    with SUMMARY_JSON.open(encoding="utf-8") as fh:
        summary = json.load(fh)

    with CHECKS_JSON.open(encoding="utf-8") as fh:
        checks = json.load(fh)

    with CROSSWALK_CSV.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        rows = list(reader)

    # 1. Total rows check
    require(len(rows) == 162, f"Expected 162 Census source rows, got {len(rows)}")
    require(summary["total_census_source_rows"] == 162, "Summary source row count mismatch")

    # 2. Target geo version frozen at GHMC_2016_150
    require(
        summary["target_geo_version"] == TARGET_GEO_VERSION,
        f"Target geo version must be {TARGET_GEO_VERSION}",
    )
    require(
        checks["target_geo_version"] == TARGET_GEO_VERSION,
        f"Checks geo version must be {TARGET_GEO_VERSION}",
    )
    require(
        all(r["target_geo_version"] == TARGET_GEO_VERSION for r in rows),
        "Every crosswalk row must specify target_geo_version == GHMC_2016_150",
    )
    require(checks["current_ward_claim_blocked"] is True, "300-ward current claim must be blocked")

    # 3. All rows have basis == 'DERIVED'
    require(all(r["basis"] == "DERIVED" for r in rows), "Every row must have basis == 'DERIVED'")

    # 4. Acceptance criterion: Wards 104 and 107 are NEVER matched
    w104_107_rows = [r for r in rows if r["source_ward_num"] in ("104", "107")]
    require(len(w104_107_rows) == 2, f"Expected 2 rows for wards 104/107, got {len(w104_107_rows)}")
    for r in w104_107_rows:
        wn = r["source_ward_num"]
        tid = r["target_ward_id"]
        require(
            tid == "",
            f"Ward {wn} must NEVER be matched to target polygon, got {tid}",
        )
        require(
            r["never_matched"] == "true",
            f"Ward {r['source_ward_num']} must have never_matched == 'true'",
        )
        require(
            r["mapping_method"] == "unmatched_never_matched",
            f"Ward {r['source_ward_num']} mapping method must be 'unmatched_never_matched'",
        )

    # Verify no target polygon with ward 104 or 107 was assigned
    for r in rows:
        require(
            r["target_ward_num"] not in ("104", "107"),
            f"Target ward {r['target_ward_num']} must never be assigned",
        )
    require(
        summary["wards_104_107_never_matched"] is True,
        "Summary must confirm 104/107 never matched",
    )
    require(
        checks["wards_104_107_never_matched"] is True,
        "Checks must confirm 104/107 never matched",
    )

    # 5. Acceptance criterion: Known missing polygons are never matched
    missing_polygon_rows = [
        r
        for r in rows
        if r["source_ward_num"] and int(r["source_ward_num"]) in KNOWN_MISSING_POLYGON_WARDS
    ]
    require(
        len(missing_polygon_rows) >= 6,
        "Expected at least 6 rows for known missing polygon wards",
    )
    for r in missing_polygon_rows:
        require(
            r["target_ward_id"] == "",
            f"Known missing ward {r['source_ward_num']} must never be matched to target polygon",
        )
        require(
            r["is_known_missing_target"] == "true",
            f"Ward {r['source_ward_num']} must have is_known_missing_target == 'true'",
        )

    # 6. Acceptance criterion: Coverage reported
    require("total_coverage_pct" in summary, "Summary must report total_coverage_pct")
    require("ghmc_coverage_pct" in summary, "Summary must report ghmc_coverage_pct")
    ghmc_cov = summary["ghmc_coverage_pct"]
    require(ghmc_cov >= 85.0, f"GHMC coverage {ghmc_cov}% is below 85%")
    require(checks["coverage_reported"] is True, "Checks must assert coverage_reported is True")

    # 7. Check SHA-256 hashes
    for filename, expected_hash in checks["output_sha256"].items():
        target_path = ROOT / "data" / "derived" / "crosswalk" / filename
        if not target_path.is_file():
            target_path = ROOT / "data" / "verification" / filename
        require(target_path.is_file(), f"Hashed file missing: {target_path}")
        actual_hash = hashlib.sha256(target_path.read_bytes()).hexdigest()
        require(
            actual_hash == expected_hash,
            f"Hash mismatch for {filename}: expected {expected_hash}, got {actual_hash}",
        )

    # 8. Verify HH-14 headers and 0-based column indexing
    verify_hh14_headers()

    print("All E1 verification checks passed successfully!")
    print(f"  GHMC Ward coverage:   {summary['ghmc_coverage_pct']}%")
    print(f"  Total matched rows:   {summary['exact_ward_number_matches']}")
    print("  Wards 104/107 never matched: verified (0 assignments)")
    print("  Known missing wards:  verified (0 false matches)")
    print("  HH-14 headers:        asserted with 0-based indices")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
