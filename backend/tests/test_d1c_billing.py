"""D1c: HMWSSB billing and collection data 2022-2026 (consumer accounts per section)."""

from __future__ import annotations

import csv
import hashlib
import re
from pathlib import Path

from app.services import hmwssb

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "data" / "verification" / "hmwssb_billing_manifest.csv"
BILLING = ROOT / "data" / "raw" / "hmwssb_billing_portal"
TANKERS = ROOT / "data" / "raw" / "hmwssb_tankers_portal"
COLUMNS = ["year", "month", "division", "section", "collection", "demand", "noofcans", "category"]


def test_manifest_hashes_and_licence() -> None:
    with MANIFEST.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    months = [r for r in rows if re.fullmatch(r"D1c-HMWSSB-billing-\d{4}-\d{2}", r["dataset_id"])]
    assert len(months) == 56
    for row in rows:
        assert row["basis"] == "REAL"
        # label as published by the portal for this dataset (GODL)
        assert row["license"] == "Government Open Data License - India"
        payload = (ROOT / row["file_path"]).read_bytes()
        assert len(payload) == int(row["bytes"])
        assert hashlib.sha256(payload).hexdigest() == row["sha256"]


def test_every_month_jan_2022_to_aug_2026_with_the_published_columns() -> None:
    stems = sorted(p.stem for p in BILLING.glob("????-??.csv"))
    expected = [f"{y}-{m:02d}" for y in range(2022, 2027) for m in range(1, 13)]
    assert stems == expected[: expected.index("2026-08") + 1]
    for path in BILLING.glob("????-??.csv"):
        with path.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            assert reader.fieldnames == COLUMNS, path.name
            first = next(reader)
            assert f"{int(first['year'])}-{int(first['month']):02d}" == path.stem


def test_billing_sections_are_the_tanker_sections() -> None:
    """Same names before the Feb/Mar 2026 re-cut, so accounts are an exact section denominator."""
    tankers = hmwssb.read_rows(TANKERS)
    for month in ("2022-06", "2023-05", "2024-04", "2025-05"):
        year, mon = map(int, month.split("-"))
        with (BILLING / f"{month}.csv").open(encoding="utf-8-sig", newline="") as handle:
            billed = {r["section"].strip().upper() for r in csv.DictReader(handle) if r["section"]}
        booked = {
            r["section"]: r["bookings"] for r in tankers if (r["year"], r["month"]) == (year, mon)
        }
        matched = sum(b for s, b in booked.items() if s in billed)
        assert matched / sum(booked.values()) >= 0.98, month
