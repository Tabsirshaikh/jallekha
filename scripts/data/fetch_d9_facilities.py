"""Fetch D9: hospitals, clinics, health centres, schools and care homes from OpenStreetMap (REAL).

Writes data/raw/d9_facilities/osm_facilities.csv (one row per OSM node, way or relation: its
position, or the centre for ways and relations, and the tags used to classify it) and
RETRIEVAL_LOG.md with the Overpass query, the OSM data timestamp and SHA-256. The area is the
bounding box of the 2016 ward layer, so wards outside Hyderabad district are covered too.
Classification and ward placement are done by scripts/evidence/build_facilities.py.

OSM data (c) OpenStreetMap contributors, ODbL 1.0 (https://www.openstreetmap.org/copyright).

    python scripts/data/fetch_d9_facilities.py
"""

from __future__ import annotations

import csv
import hashlib
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "data/raw/d9_facilities"
OUT = OUT_DIR / "osm_facilities.csv"
WARDS = ROOT / "data/raw/geography/datameet/ghmc-wards.geojson"
ENDPOINTS = (
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
)
# Every feature that can be a hospital, clinic, health centre, school or care home. Pharmacies,
# dentists and laboratories are not fetched; build_facilities.py decides the category.
SELECTORS = (
    '["amenity"~"^(hospital|clinic|doctors|school|nursing_home|social_facility)$"]',
    '["healthcare"~"^(hospital|clinic|doctor|centre)$"]',
)
TAGS = ("amenity", "healthcare", "social_facility", "name")
FIELDS = ("osm_type", "osm_id", "lat", "lon", *TAGS)
MARGIN_DEG = 0.005  # about 500 m, so features on the outer ward edges are fetched


def ward_bbox() -> tuple[float, float, float, float]:
    """(south, west, north, east) of the 2016 ward layer, widened by MARGIN_DEG."""
    features = json.loads(WARDS.read_text(encoding="utf-8"))["features"]
    lons, lats = [], []

    def walk(coords: list) -> None:
        if isinstance(coords[0], int | float):
            lons.append(coords[0])
            lats.append(coords[1])
        else:
            for part in coords:
                walk(part)

    for feature in features:
        walk(feature["geometry"]["coordinates"])
    return (
        round(min(lats) - MARGIN_DEG, 4),
        round(min(lons) - MARGIN_DEG, 4),
        round(max(lats) + MARGIN_DEG, 4),
        round(max(lons) + MARGIN_DEG, 4),
    )


def query(bbox: tuple[float, float, float, float]) -> str:
    box = ",".join(str(v) for v in bbox)
    parts = "".join(f"nwr{selector}({box});" for selector in SELECTORS)
    return f"[out:json][timeout:300];({parts});out center tags;"


def fetch(text: str) -> tuple[str, dict]:
    body = urllib.parse.urlencode({"data": text}).encode()
    last: Exception | None = None
    for attempt in range(4):
        for endpoint in ENDPOINTS:
            request = urllib.request.Request(
                endpoint, data=body, headers={"User-Agent": "jallekha-d9-fetch"}
            )
            try:
                with urllib.request.urlopen(request, timeout=360) as response:
                    return endpoint, json.loads(response.read().decode("utf-8"))
            except (urllib.error.URLError, TimeoutError) as exc:
                last = exc
        time.sleep(30 * (attempt + 1))  # Overpass answers 429 when busy; wait and retry
    raise RuntimeError(f"Overpass did not answer: {last}")


def rows(data: dict) -> list[dict[str, str]]:
    out = []
    for element in data["elements"]:
        point = element if element["type"] == "node" else element.get("center")
        if point is None:
            continue
        tags = element.get("tags", {})
        out.append(
            {
                "osm_type": element["type"],
                "osm_id": str(element["id"]),
                "lat": f"{point['lat']:.7f}",
                "lon": f"{point['lon']:.7f}",
                **{tag: tags.get(tag, "") for tag in TAGS},
            }
        )
    return sorted(out, key=lambda r: (r["osm_type"], int(r["osm_id"])))


def main() -> None:
    bbox = ward_bbox()
    text = query(bbox)
    endpoint, data = fetch(text)
    found = rows(data)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(found)
    digest = hashlib.sha256(OUT.read_bytes()).hexdigest()
    osm_base = data.get("osm3s", {}).get("timestamp_osm_base", "not reported")
    (OUT_DIR / "RETRIEVAL_LOG.md").write_text(
        f"""# D9 Health facilities, schools and care homes (OpenStreetMap) — Retrieval Log

**Dataset:** OpenStreetMap features via the Overpass API
**Basis:** REAL as mapped in OSM (incomplete: a ward with none mapped may still have some)
**Licence:** ODbL 1.0, (c) OpenStreetMap contributors, https://www.openstreetmap.org/copyright
**Used by:** F1 critical facilities (E2), F8 tier 0 and F10 candidate critical stops

| Field | Value |
|---|---|
| Endpoint | `{endpoint}` |
| Area | 2016 ward layer bounding box + {MARGIN_DEG} deg: {bbox} (south, west, north, east) |
| OSM data as of | {osm_base} |
| Retrieved | {datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")} |
| Features | {len(found)} (nodes, and ways and relations at their centre) |
| File | `osm_facilities.csv` |
| SHA-256 | `{digest}` |

Query:

```
{text}
```

The original D9 snapshot (885 / 310 / 350 / 399 / 59 in the solution document) and its query
were never found (`data/verification/SOURCES.md`), so this is a fresh pull with our own tag
choices; `scripts/evidence/build_facilities.py` documents them and compares the totals.
OSM changes daily: re-running gives a different file, so compare before replacing it.
""",
        encoding="utf-8",
    )
    print(f"Wrote {OUT} ({len(found)} features, OSM as of {osm_base}, sha256 {digest[:12]})")


if __name__ == "__main__":
    main()
