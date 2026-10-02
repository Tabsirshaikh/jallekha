"""Look up HMWSSB section names on OpenStreetMap (Nominatim) to place sections on the map.

Usage:
    python scripts/data/fetch_section_geocodes.py

HMWSSB publishes tanker bookings per section but no section boundaries or locations
(docs/research/P1.md, P2.md). Sections are named after localities, so each cleaned name is
searched with Nominatim inside the GHMC bounding box. Raw answers are stored unchanged in
data/raw/geography/nominatim/hmwssb_section_search.json (one entry per query, with the
query URL) so the mapping can be rebuilt without querying again; the manifest row is in
data/verification/section_geocode_manifest.csv. Sections are those of Jan 2022 - Jan 2026
(the section map before the Feb/Mar 2026 re-cut). Nominatim policy: one request per second.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
from app.services import hmwssb  # noqa: E402

OUT = ROOT / "data" / "raw" / "geography" / "nominatim" / "hmwssb_section_search.json"
MANIFEST = ROOT / "data" / "verification" / "section_geocode_manifest.csv"
PORTAL = ROOT / "data" / "raw" / "hmwssb_tankers_portal"
SEARCH = "https://nominatim.openstreetmap.org/search"
HEADERS = {"User-Agent": "JalLekha-data/1.0 (github.com/Tabsirshaikh/jallekha)"}
VIEWBOX = "78.20,17.65,78.70,17.20"  # GHMC bounding box: west, north, east, south
LAST_MONTH_BEFORE_RECUT = (2026, 1)


def clean_name(section: str) -> str:
    """'KONDAPUR (DIV 15)' -> 'Kondapur'; 'ADIKMET DMA-1' -> 'Adikmet'."""
    name = re.sub(r"\s*\(.*$", "", section)
    name = re.sub(r"\s+DMA-?\d+$", "", name)
    name = re.sub(r"[.\-]", " ", name)
    return re.sub(r"\s+", " ", name).strip().title()


def sections(root: Path = ROOT) -> list[str]:
    rows = hmwssb.read_rows(root / PORTAL.relative_to(ROOT))
    return sorted(
        {r["section"] for r in rows if (r["year"], r["month"]) <= LAST_MONTH_BEFORE_RECUT}
    )


def search(query: str) -> tuple[str, list[dict]]:
    params = {
        "q": query,
        "format": "jsonv2",
        "limit": 5,
        "viewbox": VIEWBOX,
        "bounded": 1,
        "countrycodes": "in",
    }
    url = f"{SEARCH}?{urllib.parse.urlencode(params)}"
    for attempt in range(1, 5):
        try:
            request = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(request, timeout=60) as response:
                return url, json.loads(response.read().decode("utf-8"))
        except OSError as error:
            print(f"  retry {attempt}: {query} ({error})", flush=True)
            time.sleep(5 * attempt)
    raise RuntimeError(f"Nominatim failed: {query}")


def main() -> int:
    names = sorted({clean_name(s) for s in sections()})
    results = []
    for i, name in enumerate(names, 1):
        url, answer = search(f"{name}, Hyderabad, Telangana")
        if not answer:
            time.sleep(1.1)
            url, answer = search(f"{name}, Telangana")
        results.append({"name": name, "url": url, "results": answer})
        print(f"  {i}/{len(names)} {name}: {len(answer)} results", flush=True)
        time.sleep(1.1)
    retrieved = datetime.now(UTC).replace(microsecond=0).isoformat()
    payload = (
        json.dumps(
            {"retrieved_at_utc": retrieved, "queries": results}, ensure_ascii=False, indent=1
        )
        + "\n"
    ).encode("utf-8")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_bytes(payload)
    with MANIFEST.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(
            [
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
        )
        writer.writerow(
            [
                "SEC-nominatim-search",
                OUT.relative_to(ROOT).as_posix(),
                SEARCH,
                retrieved,
                "ODbL 1.0 (OpenStreetMap contributors)",
                "REAL",
                hashlib.sha256(payload).hexdigest(),
                len(payload),
                f"{len(names)} cleaned HMWSSB section names, GHMC viewbox, raw answers",
            ]
        )
    print(f"Wrote {len(results)} queries to {OUT.relative_to(ROOT).as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
