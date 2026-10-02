"""D1c fetch: HMWSSB billing and collection data (2022-2026) from the Telangana Open Data Portal.

Usage:
    python scripts/data/fetch_hmwssb_billing.py

Columns: year, month, division, section, collection, demand, noofcans, category.
`noofcans` is the number of consumer accounts (CANs, one per water connection) per section and
billing category. It gives an official per-section denominator for tanker bookings (E4) and a
connection-growth signal (E3); the section names are the same as in the tanker table.

Raw bytes are written exactly as received to data/raw/hmwssb_billing_portal/ (plus the portal
metadata); checksums go to data/verification/hmwssb_billing_manifest.csv and are checked by
backend/tests/test_d1c_billing.py. The portal stalls at random, so downloads retry.
"""

from __future__ import annotations

import csv
import json
import re
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fetch_hmwssb_portal import MANIFEST_FIELDS, download, manifest_row  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "data" / "raw" / "hmwssb_billing_portal"
MANIFEST_PATH = ROOT / "data" / "verification" / "hmwssb_billing_manifest.csv"
DATASET_ID = "3485ce9d-4a9c-4293-b7e9-02e6697b9a75"
METADATA_URL = (
    "https://data.telangana.gov.in/api/1/metastore/schemas/dataset/items/"
    f"{DATASET_ID}?show-reference-ids"
)
FILE_PATTERN = re.compile(r"billing_and_collection_report_(\d{4})_(\d{1,2})\.csv$")


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    retrieved = datetime.now(UTC).replace(microsecond=0).isoformat()
    metadata_bytes = download(METADATA_URL)
    metadata_path = OUT_DIR / "metadata.json"
    metadata_path.write_bytes(metadata_bytes)
    metadata = json.loads(metadata_bytes)
    licence, modified = metadata["license"], metadata["modified"]
    rows = [
        manifest_row(
            "D1c-HMWSSB-billing-metadata",
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
                f"D1c-HMWSSB-billing-{month}",
                path,
                url,
                retrieved,
                modified,
                licence,
                "Exact portal bytes; noofcans = consumer accounts per section and category.",
            )
        )
        print(f"  {month}: {path.stat().st_size} bytes", flush=True)
        time.sleep(2)
    for row in rows:
        row["granularity"] = "monthly section-level billing, collection and consumer accounts"
    rows.sort(key=lambda row: row["dataset_id"])
    with MANIFEST_PATH.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=MANIFEST_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} manifest rows to {MANIFEST_PATH.relative_to(ROOT).as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
