"""Verify committed S2 raw files against the provenance manifest."""

from __future__ import annotations

import csv
import hashlib
import json
import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "data" / "verification" / "source_manifest.csv"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def verify_csv(path: Path) -> None:
    with path.open("r", encoding="utf-8-sig", errors="strict", newline="") as handle:
        rows = list(csv.reader(handle))
    require(bool(rows), f"CSV is empty: {path}")
    require(len(rows[0]) >= 2, f"CSV has no usable header: {path}")


def main() -> int:
    require(MANIFEST.is_file(), "Missing data/verification/source_manifest.csv")
    with MANIFEST.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    require(len(rows) == 33, f"Expected 33 S2 resources, found {len(rows)}")
    require(len({row["file_path"] for row in rows}) == len(rows), "Manifest paths are not unique")
    require(
        sum(row["dataset_id"].startswith("D1-HMWSSB-") for row in rows) == 26,
        "Expected 26 HMWSSB monthly files",
    )
    require(all(row["basis"] == "REAL" for row in rows), "Every raw source must be labelled REAL")
    require(
        all(row["source_url"].startswith("https://") for row in rows),
        "Every source needs HTTPS provenance",
    )
    require(all(row["license"] for row in rows), "Every source needs a licence or terms status")

    for row in rows:
        path = ROOT / row["file_path"]
        require(path.is_file(), f"Missing raw file: {row['file_path']}")
        payload = path.read_bytes()
        require(len(payload) == int(row["bytes"]), f"Size mismatch: {row['file_path']}")
        require(
            hashlib.sha256(payload).hexdigest() == row["sha256"],
            f"SHA-256 mismatch: {row['file_path']}",
        )
        if path.suffix.lower() == ".csv":
            verify_csv(path)
        elif path.suffix.lower() == ".xlsx":
            require(zipfile.is_zipfile(path), f"Invalid XLSX container: {row['file_path']}")
        elif path.suffix.lower() == ".geojson":
            data = json.loads(path.read_text(encoding="utf-8-sig"))
            require(data.get("type") == "FeatureCollection", f"Invalid GeoJSON: {row['file_path']}")
            require(bool(data.get("features")), f"GeoJSON has no features: {row['file_path']}")

    tanker_rows: list[dict[str, str]] = []
    for path in sorted((ROOT / "data/raw/hmwssb_tankers").glob("*.csv")):
        with path.open(encoding="utf-8-sig", newline="") as handle:
            tanker_rows.extend(csv.DictReader(handle))
    require(len(tanker_rows) == 4_398, "HMWSSB row count changed from the verified 4,398")
    require(
        sum(int(row["noofbookings"] or 0) for row in tanker_rows) == 1_316_215,
        "HMWSSB booking total mismatch",
    )
    require(
        sum(int(row["delivered"] or 0) for row in tanker_rows) == 1_315_622,
        "HMWSSB delivered total mismatch",
    )
    require(len({row["section"] for row in tanker_rows}) == 201, "HMWSSB section count mismatch")
    require(
        not any(row["year"] == "2022" and row["month"] == "12" for row in tanker_rows),
        "December 2022 should contain no data rows",
    )

    wards = json.loads(
        (ROOT / "data/raw/geography/datameet/ghmc-wards.geojson").read_text(encoding="utf-8-sig")
    )
    zones = json.loads(
        (ROOT / "data/raw/geography/datameet/ghmc-zones.geojson").read_text(encoding="utf-8-sig")
    )
    require(
        len(wards["features"]) == 145,
        "Historical ward file no longer has the verified 145 features",
    )
    require(
        len(zones["features"]) == 5, "Historical zone file no longer has the verified 5 features"
    )

    with (ROOT / "data/raw/census/hyderabad/pca.csv").open(
        encoding="utf-8-sig", newline=""
    ) as handle:
        pca_rows = list(csv.DictReader(handle))
    require(len(pca_rows) == 108, "Hyderabad PCA must retain 108 ward rows")
    require(
        {"Ward", "No_HH", "TOT_P"}.issubset(pca_rows[0]),
        "Hyderabad PCA required columns are missing",
    )

    expected_xlsx_rows = {
        "data/raw/census/hyderabad/hh14.xlsx": 165,
        "data/raw/census/rangareddy/hh14.xlsx": 1_097,
        "data/raw/census/rangareddy/pca.xlsx": 1_168,
    }
    for relative_path, expected_rows in expected_xlsx_rows.items():
        with zipfile.ZipFile(ROOT / relative_path) as archive:
            sheet_names = [
                name
                for name in archive.namelist()
                if name.startswith("xl/worksheets/sheet") and name.endswith(".xml")
            ]
            row_count = sum(
                1
                for sheet_name in sheet_names
                for _, element in ET.iterparse(archive.open(sheet_name), events=("end",))
                if element.tag.endswith("}row")
            )
        require(
            row_count == expected_rows,
            f"Unexpected worksheet row count for {relative_path}: {row_count}",
        )

    print(f"P1:S2 verified {len(rows)} sources; integrity and totals pass")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as exc:
        print(f"P1:S2 verification failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
