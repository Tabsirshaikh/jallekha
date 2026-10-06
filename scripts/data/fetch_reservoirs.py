"""Fetch Q2 accepted Telangana reservoir source; separate manifest avoids E2/E5 hash churn."""

from __future__ import annotations

import csv
import hashlib
import json
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
URL = "https://data.telangana.gov.in/api/1/search?fulltext=reservoir&page-size=50"


def download(url: str) -> bytes:
    for attempt in range(3):
        try:
            with urllib.request.urlopen(
                urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=30
            ) as response:
                return response.read()
        except OSError:
            if attempt == 2:
                raise
    raise RuntimeError(url)


def main() -> int:
    out = ROOT / "data/raw/reservoirs"
    out.mkdir(parents=True, exist_ok=True)
    metadata = download(URL)
    (out / "catalogue.json").write_bytes(metadata)
    dataset = next(iter(json.loads(metadata)["results"].values()))
    items = [{"downloadURL": URL}] + dataset["distribution"]

    def fetch(item):
        url = item["downloadURL"]
        path = out / ("catalogue.json" if url == URL else url.rsplit("/", 1)[-1])
        payload = path.read_bytes() if path.exists() else download(url)
        path.write_bytes(payload)
        return {
            "file_path": path.relative_to(ROOT).as_posix(),
            "source_url": url,
            "sha256": hashlib.sha256(payload).hexdigest(),
            "bytes": len(payload),
            "basis": "REAL",
            "license": dataset["license"],
            "retrieved_at_utc": datetime.now(UTC).isoformat(),
        }

    with ThreadPoolExecutor(max_workers=6) as pool:
        rows = list(pool.map(fetch, items))
    with (ROOT / "data/verification/reservoir_manifest.csv").open(
        "w", newline="", encoding="utf-8"
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(sorted(rows, key=lambda r: r["file_path"]))
    print(f"Fetched {len(rows) - 1} monthly reservoir files with source hashes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
