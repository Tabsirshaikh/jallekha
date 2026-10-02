"""Fetch the sources for the 2009 GHMC ward map (the ward numbering used by Census 2011).

Usage:
    python scripts/data/fetch_ward2009.py

Census 2011 numbers GHMC wards by the 2009 delimitation; the DataMeet layer is the 2016
delimitation (wards renumbered and redrawn). These sources let E2 transfer Census values by
location instead of by ward number:

  ghmc_2009/ghmc_election_wards_2009.pdf   Official GHMC ward map (election_wards.pdf,
                                            12 June 2009), vector ArcMap export, GODL-India,
                                            via Wikimedia Commons.
  ghmc_2009/wikipedia_ghmc_2009_election.json  Ward number -> name table (pinned revision),
                                            CC BY-SA 4.0. Used for labels and a name check.
  nominatim/hyderabad_district.geojson     OSM Hyderabad district polygon (relation 7255986),
                                            ODbL. Used only to validate the rebuilt map
                                            (data/raw/geography/osm/hyderabad_district.geojson
                                            holds a point, not a boundary).

Raw bytes are written exactly as received. Checksums go to
data/verification/ward2009_manifest.csv; backend/tests/test_ward2009.py checks them.
"""

from __future__ import annotations

import csv
import hashlib
import sys
import time
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw" / "geography"
MANIFEST_PATH = ROOT / "data" / "verification" / "ward2009_manifest.csv"
HEADERS = {"User-Agent": "JalLekha-data/1.0 (github.com/Tabsirshaikh/jallekha)"}

SOURCES = [
    {
        "dataset_id": "W2009-GHMC-ward-map",
        "file": RAW / "ghmc_2009" / "ghmc_election_wards_2009.pdf",
        "url": "https://upload.wikimedia.org/wikipedia/commons/b/b5/Wards_of_Hyderabad_2011.pdf",
        "license": "Government Open Data License - India (GODL)",
        "notes": (
            "GHMC election_wards.pdf dated 2009-06-12 (originally "
            "http://www.ghmc.gov.in/tender pdfs/election_wards.pdf), via "
            "https://commons.wikimedia.org/wiki/File:Wards_of_Hyderabad_2011.pdf"
        ),
    },
    {
        "dataset_id": "W2009-ward-names",
        "file": RAW / "ghmc_2009" / "wikipedia_ghmc_2009_election.json",
        "url": (
            "https://en.wikipedia.org/w/api.php?action=parse&oldid=1369507921"
            "&prop=wikitext%7Crevid&format=json&formatversion=2"
        ),
        "license": "CC BY-SA 4.0",
        "notes": "2009 GHMC election results by ward (pinned revision 1369507921).",
    },
    {
        "dataset_id": "W2009-hyderabad-district",
        "file": RAW / "nominatim" / "hyderabad_district.geojson",
        "url": (
            "https://nominatim.openstreetmap.org/lookup?osm_ids=R7255986"
            "&format=geojson&polygon_geojson=1"
        ),
        "license": "ODbL 1.0 (OpenStreetMap contributors)",
        "notes": "OSM relation 7255986 boundary; validation only.",
    },
]
FIELDS = [
    "dataset_id",
    "file_path",
    "source_url",
    "retrieved_at_utc",
    "license",
    "basis",
    "sha256",
    "bytes",
    "notes",
]


def download(url: str, attempts: int = 5) -> bytes:
    for attempt in range(1, attempts + 1):
        try:
            request = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(request, timeout=60) as response:
                return response.read()
        except OSError as error:
            print(f"  retry {attempt}/{attempts}: {url} ({error})", flush=True)
            time.sleep(3 * attempt)
    raise RuntimeError(f"Download failed: {url}")


def main() -> int:
    retrieved = datetime.now(UTC).replace(microsecond=0).isoformat()
    rows = []
    for source in SOURCES:
        path: Path = source["file"]
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = download(source["url"])
        path.write_bytes(payload)
        rows.append(
            {
                "dataset_id": source["dataset_id"],
                "file_path": path.relative_to(ROOT).as_posix(),
                "source_url": source["url"],
                "retrieved_at_utc": retrieved,
                "license": source["license"],
                "basis": "REAL",
                "sha256": hashlib.sha256(payload).hexdigest(),
                "bytes": str(len(payload)),
                "notes": source["notes"],
            }
        )
        print(f"  {path.relative_to(ROOT).as_posix()}: {len(payload)} bytes")
        time.sleep(1.5)  # Nominatim usage policy: at most one request per second
    with MANIFEST_PATH.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} rows to {MANIFEST_PATH.relative_to(ROOT).as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
