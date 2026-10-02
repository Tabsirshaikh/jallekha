"""D1b fetch: HMWSSB tanker table from the Telangana Open Data Portal.

Usage:
    python scripts/data/fetch_hmwssb_portal.py

Same columns as the S2 OpenCity files (year, month, division, section,
noofbookings, delivered) but continued to the latest published month.
Found during R-P2 (docs/research/P2.md).

Files go to data/raw/hmwssb_tankers_portal/ (never into the S2 folder, whose
verified counts must not change). Raw bytes are written exactly as received.
The dataset metadata JSON is kept as provenance. Checksums are written to
data/verification/hmwssb_portal_manifest.csv; backend/tests/test_d1b_portal.py
checks them.

The portal refuses some cloud runners, so CI only verifies committed files.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
import sys
import time
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "data" / "raw" / "hmwssb_tankers_portal"
MANIFEST_PATH = ROOT / "data" / "verification" / "hmwssb_portal_manifest.csv"

DATASET_ID = "7f408a3a-7cdb-4d33-bfa3-1869f88c0e25"
METADATA_URL = (
    "https://data.telangana.gov.in/api/1/metastore/schemas/dataset/items/"
    f"{DATASET_ID}?show-reference-ids"
)
# The portal times out on custom User-Agent strings (tested 2026-10-02); a plain one works.
HEADERS = {"User-Agent": "Mozilla/5.0"}
FILE_PATTERN = re.compile(r"tankers_reports_(\d{4})_(\d{1,2})\.csv$")

MANIFEST_FIELDS = [
    "dataset_id",
    "file_path",
    "source_url",
    "retrieved_at_utc",
    "source_modified",
    "license",
    "geography",
    "granularity",
    "basis",
    "sha256",
    "bytes",
    "notes",
]
GEOGRAPHY = "HMWSSB divisions and sections, Hyderabad (sections re-cut Feb/Mar 2026)"


def download(url: str, attempts: int = 8) -> bytes:
    # The portal stalls at random (same URL: 200 in 3 s, then no reply for 20 s+), so back off.
    for attempt in range(1, attempts + 1):
        try:
            request = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(request, timeout=30) as response:
                return response.read()
        except OSError as error:
            print(f"  retry {attempt}/{attempts}: {url} ({error})", flush=True)
            time.sleep(5 * attempt)
    raise RuntimeError(f"Download failed: {url}")


def manifest_row(
    dataset_id: str, path: Path, url: str, retrieved: str, modified: str, licence: str, notes: str
) -> dict[str, str]:
    payload = path.read_bytes()
    return {
        "dataset_id": dataset_id,
        "file_path": path.relative_to(ROOT).as_posix(),
        "source_url": url,
        "retrieved_at_utc": retrieved,
        "source_modified": modified,
        "license": licence,
        "geography": GEOGRAPHY,
        "granularity": "monthly section-level bookings and delivered counts",
        "basis": "REAL",
        "sha256": hashlib.sha256(payload).hexdigest(),
        "bytes": str(len(payload)),
        "notes": notes,
    }


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    retrieved = datetime.now(UTC).replace(microsecond=0).isoformat()

    metadata_bytes = download(METADATA_URL)
    metadata_path = OUT_DIR / "metadata.json"
    metadata_path.write_bytes(metadata_bytes)
    metadata = json.loads(metadata_bytes)
    licence = metadata["license"]
    modified = metadata["modified"]

    rows = [
        manifest_row(
            "D1b-HMWSSB-metadata",
            metadata_path,
            METADATA_URL,
            retrieved,
            modified,
            licence,
            "Portal metadata as received: title, coverage text, licence, file list.",
        )
    ]
    for item in metadata["distribution"]:
        url = item.get("data", item)["downloadURL"]
        match = FILE_PATTERN.search(url)
        if match is None:
            raise RuntimeError(f"Unexpected file name: {url}")
        month = f"{match.group(1)}-{int(match.group(2)):02d}"
        path = OUT_DIR / f"{month}.csv"
        path.write_bytes(download(url))
        rows.append(
            manifest_row(
                f"D1b-HMWSSB-{month}",
                path,
                url,
                retrieved,
                modified,
                licence,
                "Exact portal bytes; a header-only file means no rows were published.",
            )
        )
        print(f"  {month}: {path.stat().st_size} bytes")
        time.sleep(2)

    rows.sort(key=lambda row: row["dataset_id"])
    with MANIFEST_PATH.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=MANIFEST_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} manifest rows to {MANIFEST_PATH.relative_to(ROOT).as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
