"""Tests for D16 supply timings data fetching, parsing, and coverage (Prompt A)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = ROOT / "scripts" / "data" / "fetch_supply_timings.py"

# Import fetch_supply_timings dynamically from scripts/data/
spec = importlib.util.spec_from_file_location("fetch_supply_timings", SCRIPT_PATH)
if spec and spec.loader:
    fst = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = fst
    spec.loader.exec_module(fst)
else:
    fst = None


def test_script_exists_and_loaded():
    assert fst is not None, "scripts/data/fetch_supply_timings.py could not be loaded"


def test_parse_time_conversions():
    """Verify conversion of colloquial HMWSSB time strings to 24h format and decimal hours."""
    # Standard times
    assert fst.parse_time_str("1.0", "PM") == ("13:00", 13.0)
    assert fst.parse_time_str("2.0", "PM") == ("14:00", 14.0)
    assert fst.parse_time_str("11.0", "AM") == ("11:00", 11.0)
    assert fst.parse_time_str("12.0", "PM") == ("12:00", 12.0)
    assert fst.parse_time_str("12.0", "AM") == ("00:00", 0.0)

    # Fractional times: .3 means :30, .15 means :15
    assert fst.parse_time_str("4.3", "PM") == ("16:30", 16.5)
    assert fst.parse_time_str("3.3", "AM") == ("03:30", 3.5)
    assert fst.parse_time_str("7.15", "AM") == ("07:15", 7.25)
    assert fst.parse_time_str("8.3", "AM") == ("08:30", 8.5)


def test_calc_duration_hours():
    """Verify duration calculation between from_time and to_time."""
    # 1.0 PM (13.0) to 2.0 PM (14.0) -> 1.0 hr
    assert fst.calc_hours(13.0, 14.0) == pytest.approx(1.0)
    # 3.0 PM (15.0) to 4.3 PM (16.5) -> 1.5 hr
    assert fst.calc_hours(15.0, 16.5) == pytest.approx(1.5)
    # 7.15 AM (7.25) to 8.3 AM (8.5) -> 1.25 hr
    assert fst.calc_hours(7.25, 8.5) == pytest.approx(1.25)
    # 11.0 PM (23.0) to 1.0 AM (1.0) -> overnight 2.0 hrs
    assert fst.calc_hours(23.0, 1.0) == pytest.approx(2.0)


def test_parse_empty_page_returns_empty_list():
    """A page returning alert('No Data Found') should yield zero locality records."""
    empty_html = """
    <html><body>
    <script language="javaScript">alert('No Data Found');</script>
    </body></html>
    """
    rows = fst.parse_timings_table(
        html=empty_html,
        division_code="6",
        section="TEST",
        section_code="0600",
        captured_at="2026-10-06T12:00:00Z",
        capture_source="live",
        source_url="https://bms.hyderabadwater.gov.in/test",
    )
    assert rows == []


def test_parse_wayback_sr_nagar_page():
    """Verify parsing of the archived S.R. Nagar page produces 21 records with valid columns."""
    sample_path = (
        ROOT / "data" / "raw" / "d16_supply_timings" / "raw_pages" / "sr_nagar_2024-05-14.html"
    )
    if not sample_path.exists():
        # Fall back to scratch if raw_pages not yet populated
        sample_path = Path("wayback_sr_nagar.html")

    assert sample_path.exists(), f"Sample file not found at {sample_path}"
    html = sample_path.read_text(encoding="utf-8")

    rows = fst.parse_timings_table(
        html=html,
        division_code="6",
        section="S.R.NAGAR",
        section_code="0624",
        captured_at="2024-05-14T21:57:12Z",
        capture_source="wayback",
        source_url="http://web.archive.org/web/20240514215712id_/https://bms.hyderabadwater.gov.in/wstl/WaterSupplyView/ViewTimings.aspx?Divisioncode=6&Section=S.R.NAGAR&Sectioncode=0624",
    )

    assert len(rows) == 21, f"Expected 21 localities for S.R. Nagar, got {len(rows)}"

    first = rows[0]
    assert first["division_code"] == "6"
    assert first["section"] == "S.R.NAGAR"
    assert first["section_code"] == "0624"
    assert first["locality_code"] == "1173"
    assert "BJR Nagar" in first["locality"]
    assert first["slum_status"] == "Non Slum"
    assert first["from_time"] == "13:00"
    assert first["to_time"] == "14:00"
    assert float(first["hours"]) == pytest.approx(1.0)
    assert first["pattern"] == "Daily"
    assert first["water_source"] == "Singoor / Lingampally"
    assert first["captured_at"] == "2024-05-14T21:57:12Z"
    assert first["capture_source"] == "wayback"

    # Check row with fractional time (row index 4, s_no 5: 3.0 PM to 4.3 PM)
    row5 = [r for r in rows if r["locality_code"] == "1175"][0]
    assert row5["from_time"] == "15:00"
    assert row5["to_time"] == "16:30"
    assert float(row5["hours"]) == pytest.approx(1.5)

    # Check row with 7.15 AM (row index 16, s_no 17: 7.15 AM to 8.3 AM)
    row17 = [r for r in rows if r["locality_code"] == "1168"][0]
    assert row17["from_time"] == "07:15"
    assert row17["to_time"] == "08:30"
    assert float(row17["hours"]) == pytest.approx(1.25)


def test_coverage_maths():
    """Verify coverage calculation against 89 sections and 2025 tanker portal bookings."""
    stats = fst.compute_coverage_stats(
        sections_with_data=1,
        total_sections=89,
        localities_count=21,
        covered_section_name="S.R.NAGAR",
    )
    assert stats["sections_with_data"] == 1
    assert stats["total_sections"] == 89
    assert stats["section_coverage_pct"] == pytest.approx(1.1236, rel=1e-2)
    assert stats["total_localities"] == 21
    assert stats["covered_2025_bookings"] == 40862
    assert stats["total_2025_bookings"] == 1436768
    assert stats["bookings_coverage_pct"] == pytest.approx(2.8440, rel=1e-2)
    assert stats["ward_id"] == "relation/7857794"
    assert stats["ward_name"] == "Ward 98 Ameerpet"


def test_verifier_passes():
    """Verify that the D16 verifier script executes and exits with 0."""
    verifier_path = ROOT / "scripts" / "data" / "verify_supply_timings.py"
    spec_v = importlib.util.spec_from_file_location("verify_supply_timings", verifier_path)
    assert spec_v and spec_v.loader
    vst = importlib.util.module_from_spec(spec_v)
    spec_v.loader.exec_module(vst)
    assert vst.main() == 0
