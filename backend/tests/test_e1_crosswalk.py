"""Unit and integration tests for Task E1: Census 2011 to GHMC_2016_150 Crosswalk."""

from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

import openpyxl

ROOT = Path(__file__).resolve().parents[2]
CROSSWALK_CSV = ROOT / "data" / "derived" / "crosswalk" / "census_to_ghmc_2016.csv"
SUMMARY_JSON = ROOT / "data" / "derived" / "crosswalk" / "crosswalk_summary.json"
CHECKS_JSON = ROOT / "data" / "verification" / "crosswalk_checks.json"


def test_crosswalk_files_exist() -> None:
    assert CROSSWALK_CSV.is_file(), f"Missing {CROSSWALK_CSV}"
    assert SUMMARY_JSON.is_file(), f"Missing {SUMMARY_JSON}"
    assert CHECKS_JSON.is_file(), f"Missing {CHECKS_JSON}"


def test_crosswalk_geo_version_and_basis() -> None:
    with SUMMARY_JSON.open(encoding="utf-8") as fh:
        summary = json.load(fh)
    with CHECKS_JSON.open(encoding="utf-8") as fh:
        checks = json.load(fh)

    assert summary["target_geo_version"] == "GHMC_2016_150"
    assert checks["target_geo_version"] == "GHMC_2016_150"
    assert checks["current_ward_claim_blocked"] is True

    with CROSSWALK_CSV.open(encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))

    assert len(rows) == 162
    for r in rows:
        assert r["target_geo_version"] == "GHMC_2016_150"
        assert r["basis"] == "DERIVED"
        assert r["source_geo_version"] in ("Census2011_Hyderabad", "Census2011_Rangareddy")


def test_wards_104_107_never_matched() -> None:
    """Acceptance criterion: Wards 104 and 107 must NEVER be matched to target polygons."""
    with SUMMARY_JSON.open(encoding="utf-8") as fh:
        summary = json.load(fh)
    with CHECKS_JSON.open(encoding="utf-8") as fh:
        checks = json.load(fh)

    assert summary["wards_104_107_never_matched"] is True
    assert checks["wards_104_107_never_matched"] is True

    with CROSSWALK_CSV.open(encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))

    w104_107 = [r for r in rows if r["source_ward_num"] in ("104", "107")]
    assert len(w104_107) == 2, f"Expected 2 rows for wards 104 and 107, got {len(w104_107)}"

    for r in w104_107:
        assert r["target_ward_id"] == "", (
            f"Ward {r['source_ward_num']} matched {r['target_ward_id']}"
        )
        assert r["target_ward_name"] == ""
        assert r["never_matched"] == "true"
        assert r["mapping_method"] == "unmatched_never_matched"
        assert float(r["one_to_many_weight"]) == 0.0

    # Ensure no target polygon 104 or 107 was assigned
    for r in rows:
        assert r["target_ward_num"] not in ("104", "107")


def test_known_missing_polygons_never_matched() -> None:
    """Missing DataMeet polygons (3, 4, 11, 13, 31, 113) must not be matched."""
    missing_nums = {"3", "4", "11", "13", "31", "113"}
    with CROSSWALK_CSV.open(encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))

    missing_rows = [r for r in rows if r["source_ward_num"] in missing_nums]
    assert len(missing_rows) >= 6

    for r in missing_rows:
        assert r["target_ward_id"] == "", f"Missing ward {r['source_ward_num']} was matched"
        assert r["is_known_missing_target"] == "true"
        assert r["mapping_method"] in ("unmatched_known_missing", "unmatched_non_ghmc")


def test_crosswalk_coverage_reported() -> None:
    """Acceptance criterion: Coverage is reported and passes threshold."""
    with SUMMARY_JSON.open(encoding="utf-8") as fh:
        summary = json.load(fh)
    with CHECKS_JSON.open(encoding="utf-8") as fh:
        checks = json.load(fh)

    assert "ghmc_coverage_pct" in summary
    assert "total_coverage_pct" in summary
    assert checks["coverage_reported"] is True
    assert summary["ghmc_coverage_pct"] >= 85.0
    assert summary["total_census_source_rows"] == 162
    assert summary["exact_ward_number_matches"] == 145


def test_hh14_headers_and_zero_based_indices() -> None:
    """Technical gotcha: HH-14 columns are 0-based indices; assert headers."""
    for rel_path in (
        "data/raw/census/hyderabad/hh14.xlsx",
        "data/raw/census/rangareddy/hh14.xlsx",
    ):
        fpath = ROOT / rel_path
        assert fpath.is_file(), f"Missing {rel_path}"

        wb = openpyxl.load_workbook(fpath, read_only=True, data_only=True)
        ws = wb.active
        rows = list(ws.iter_rows(values_only=True, max_row=8))
        wb.close()

        # Row 3 (0-based) contains column headers
        hdr = rows[3]
        assert hdr[0] == "State Code"
        assert hdr[1] == "State Name"
        assert hdr[2] == "District Code"
        assert hdr[3] == "District Name"
        assert hdr[7] == "Ward No"
        assert hdr[8] == "Area Name"
        assert "Rural" in hdr[9] or "Urban" in hdr[9]

        # Row 6 (0-based) contains 1-based table indices [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, ...]
        indices = rows[6]
        assert indices[0] == 1
        assert indices[7] == 8  # 'Ward No' at 0-based index 7 corresponds to printed 8
        assert indices[8] == 9  # 'Area Name' at 0-based index 8 corresponds to printed 9


def test_verify_script_passes() -> None:
    """Ensure scripts/evidence/verify_crosswalk.py runs and passes cleanly."""
    script_path = ROOT / "scripts" / "evidence" / "verify_crosswalk.py"
    res = subprocess.run(
        [sys.executable, str(script_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    msg = f"verify_crosswalk.py failed:\nSTDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}"
    assert res.returncode == 0, msg
