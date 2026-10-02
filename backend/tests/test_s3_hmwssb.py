"""S3: HMWSSB tanker reader ported from v1, recomputing real figures from the raw files."""

from __future__ import annotations

from pathlib import Path

from app.services import hmwssb

ROOT = Path(__file__).resolve().parents[2]
S2_DIR = ROOT / "data" / "raw" / "hmwssb_tankers"
PORTAL_DIR = ROOT / "data" / "raw" / "hmwssb_tankers_portal"


def test_reads_the_verified_s2_files() -> None:
    rows = hmwssb.read_rows(S2_DIR)
    assert len(rows) == 4_398
    assert sum(r["bookings"] for r in rows) == 1_316_215
    assert sum(r["delivered"] for r in rows) == 1_315_622
    assert len({r["section"] for r in rows}) == 201


def test_reads_the_portal_files_including_header_only_month() -> None:
    rows = hmwssb.read_rows(PORTAL_DIR)
    totals = hmwssb.monthly_totals(rows)
    assert sum(totals.values()) == 5_356_766
    assert (2022, 12) not in totals
    assert totals[(2026, 5)] == 319_106


def test_january_to_may_2022_surge() -> None:
    insights = hmwssb.insights(hmwssb.read_rows(S2_DIR))
    assert insights["jan_may_2022"] == {"jan": 22_834, "may": 83_920, "surge": 3.68}


def test_top_tenth_of_sections_hold_most_bookings() -> None:
    rows = hmwssb.read_rows(S2_DIR)
    for month in (1, 5, 8):
        share = hmwssb.concentration(rows, 2022, month)
        assert 0.56 <= share["top10_share"] <= 0.66, share
        assert 0.03 <= share["bottom50_share"] <= 0.06, share


def test_seasonality_peaks_before_the_monsoon() -> None:
    index = hmwssb.seasonality_index(hmwssb.read_rows(S2_DIR))
    assert max(index, key=index.get) in (4, 5, 6)
    assert min(index[4], index[5], index[6]) > 1.5 * max(index[9], index[10], index[11])
