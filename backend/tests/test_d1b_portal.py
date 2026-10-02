"""D1b: HMWSSB tanker table from the Telangana Open Data Portal (Jan 2022 - Aug 2026).

The portal files are stored beside the S2 OpenCity files, never mixed into them,
so the verified S2 counts (4,398 rows, 26 files) stay unchanged.
"""

from __future__ import annotations

import csv
import hashlib
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = ROOT / "data" / "verification" / "hmwssb_portal_manifest.csv"
PORTAL_DIR = ROOT / "data" / "raw" / "hmwssb_tankers_portal"
S2_DIR = ROOT / "data" / "raw" / "hmwssb_tankers"


def _manifest() -> list[dict[str, str]]:
    with MANIFEST_PATH.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _month_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _count(value: str) -> int:
    return int(value or 0)


def _monthly_totals(directory: Path) -> dict[str, tuple[int, int]]:
    totals: dict[str, tuple[int, int]] = {}
    for path in sorted(directory.glob("????-??.csv")):
        rows = _month_rows(path)
        totals[path.stem] = (
            sum(_count(row["noofbookings"]) for row in rows),
            sum(_count(row["delivered"]) for row in rows),
        )
    return totals


def test_manifest_lists_56_monthly_files_with_matching_bytes() -> None:
    rows = _manifest()
    months = [row for row in rows if re.fullmatch(r"D1b-HMWSSB-\d{4}-\d{2}", row["dataset_id"])]
    assert len(months) == 56
    assert {row["dataset_id"] for row in rows} - {row["dataset_id"] for row in months} == {
        "D1b-HMWSSB-metadata"
    }
    for row in rows:
        assert row["basis"] == "REAL"
        assert row["license"] == "Open Government License, India"
        assert row["source_url"].startswith("https://data.telangana.gov.in/")
        payload = (ROOT / row["file_path"]).read_bytes()
        assert len(payload) == int(row["bytes"]), row["file_path"]
        assert hashlib.sha256(payload).hexdigest() == row["sha256"], row["file_path"]


def test_months_run_jan_2022_to_aug_2026_without_gaps() -> None:
    stems = sorted(path.stem for path in PORTAL_DIR.glob("????-??.csv"))
    expected = [f"{year}-{month:02d}" for year in range(2022, 2027) for month in range(1, 13)]
    assert stems == expected[: expected.index("2026-08") + 1]


def test_totals_match_the_portal_download() -> None:
    totals = _monthly_totals(PORTAL_DIR)
    assert sum(b for b, _ in totals.values()) == 5_356_766
    assert sum(d for _, d in totals.values()) == 5_281_651


def test_december_2022_has_no_data_rows() -> None:
    assert _month_rows(PORTAL_DIR / "2022-12.csv") == []


def test_delivered_never_exceeds_bookings() -> None:
    for path in PORTAL_DIR.glob("????-??.csv"):
        for row in _month_rows(path):
            assert int(row["delivered"]) <= int(row["noofbookings"]), (path.name, row)


def test_overlapping_months_equal_the_s2_opencity_files() -> None:
    portal = _monthly_totals(PORTAL_DIR)
    s2 = _monthly_totals(S2_DIR)
    assert len(s2) == 26
    assert {month: portal[month] for month in s2} == s2


def test_section_rows_match_s2_for_overlapping_months() -> None:
    def by_section(directory: Path) -> dict[tuple[str, str], tuple[int, int]]:
        out: dict[tuple[str, str], tuple[int, int]] = defaultdict(lambda: (0, 0))
        for path in S2_DIR.glob("????-??.csv"):
            for row in _month_rows(directory / path.name):
                key = (path.stem, row["section"].strip())
                bookings, delivered = out[key]
                out[key] = (
                    bookings + _count(row["noofbookings"]),
                    delivered + _count(row["delivered"]),
                )
        return dict(out)

    assert by_section(PORTAL_DIR) == by_section(S2_DIR)
