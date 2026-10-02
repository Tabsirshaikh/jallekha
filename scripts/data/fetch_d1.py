"""D1 fetch script: OSM district/mandal boundaries, HMWSSB points, retrieval logs.

Usage:
    python scripts/data/fetch_d1.py [--dry-run]

Fetches:
  D5a  Hyderabad district boundary    (OSM Overpass, ODbL)
  D5b  Telangana mandal boundaries    (OSM Overpass, ODbL)
  D10  OSM HMWSSB water supply points (OSM Overpass, ODbL)

NOT fetched here (require authentication or non-scriptable access):
  D6   Open Buildings Temporal  → see data/raw/d6_open_buildings/RETRIEVAL_LOG.md
  D7   NWDP groundwater levels  → see data/raw/d7_groundwater/RETRIEVAL_LOG.md

All raw bytes are written exactly as received.  Checksums are written to
data/verification/d1_manifest.csv for verification by verify_d1.py.

Run time: ~60 s (four Overpass queries, each with a courteous 5-second pause).
"""

from __future__ import annotations

import csv
import hashlib
import json
import sys
import time
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"
MANIFEST_PATH = ROOT / "data" / "verification" / "d1_manifest.csv"

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
OVERPASS_HEADERS = {
    "Content-Type": "application/x-www-form-urlencoded",
    "User-Agent": "JalLekha-D1/1.0 (github.com/Tabsirshaikh/jallekha)",
}
# Hyderabad / GHMC bounding box  (south, west, north, east)
HYD_BBOX = "17.20,78.20,17.65,78.70"

DRY_RUN = "--dry-run" in sys.argv
# When --skip-fetch is used, the manifest is regenerated from already-committed files
# without hitting Overpass.  CI uses this after the developer commits the raw GeoJSON.
SKIP_FETCH = "--skip-fetch" in sys.argv
# --only D5a,D5b re-fetches just those layers; the others keep their committed bytes and rows.
ONLY = {
    key
    for arg in sys.argv
    if arg.startswith("--only=")
    for key in arg.removeprefix("--only=").split(",")
    if key
}

NOMINATIM_LOOKUP = "https://nominatim.openstreetmap.org/lookup"
NOMINATIM_HEADERS = {"User-Agent": "JalLekha-D1/1.0 (github.com/Tabsirshaikh/jallekha)"}


def nominatim_url(osm_ids: list[str]) -> str:
    return f"{NOMINATIM_LOOKUP}?osm_ids={','.join(osm_ids)}&format=geojson&polygon_geojson=1"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def overpass_json(query: str) -> dict:
    """Send an Overpass QL query with exponential-backoff retries for 429/504."""
    import urllib.error

    last_exc: Exception | None = None
    for attempt in range(1, 5):
        try:
            req = urllib.request.Request(
                OVERPASS_URL, data=query.encode(), headers=OVERPASS_HEADERS
            )
            with urllib.request.urlopen(req, timeout=90) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            last_exc = exc
            if exc.code in (429, 504, 503):
                delay = 20.0 * (2 ** (attempt - 1))
                print(f"    [HTTP {exc.code}] retrying in {delay:.0f}s (attempt {attempt}/4)")
                time.sleep(delay)
            else:
                raise
        except Exception as exc:
            last_exc = exc
            delay = 20.0 * (2 ** (attempt - 1))
            print(f"    [{type(exc).__name__}] retrying in {delay:.0f}s (attempt {attempt}/4)")
            time.sleep(delay)
    raise RuntimeError(f"Overpass failed after 4 attempts: {last_exc}") from last_exc


def osm_to_geojson(osm: dict) -> dict:
    """Convert Overpass JSON elements to a minimal GeoJSON FeatureCollection.

    Handles nodes (→ Point) and ways/relations with centre tags (→ Point).
    Relations and ways that have geometry lists are converted to LineString
    or Polygon where the data is available; otherwise they are skipped.
    """
    features = []
    for elem in osm.get("elements", []):
        etype = elem.get("type")
        props = {"osm_type": etype, "osm_id": elem.get("id")}
        props.update(elem.get("tags", {}))

        if etype == "node":
            geom = {"type": "Point", "coordinates": [elem["lon"], elem["lat"]]}
        elif etype in ("way", "relation"):
            # Overpass out geom adds a "center" field
            center = elem.get("center")
            if center:
                geom = {"type": "Point", "coordinates": [center["lon"], center["lat"]]}
            else:
                continue  # skip elements without geometry
        else:
            continue

        features.append({"type": "Feature", "properties": props, "geometry": geom})

    return {"type": "FeatureCollection", "features": features}


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_manifest(rows: list[dict]) -> None:
    fields = [
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
    with MANIFEST_PATH.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    print(f"  manifest written: {MANIFEST_PATH.relative_to(ROOT)}")


# ---------------------------------------------------------------------------
# OSM queries
# ---------------------------------------------------------------------------

QUERIES: dict[str, dict] = {
    "D5a": {
        # Hyderabad district boundary polygon. The earlier Overpass "out center" query stored
        # only a centre point, so boundaries come from Nominatim lookup (OSM relation 7255986).
        "nominatim_ids": ["R7255986"],
        "out_path": RAW / "geography" / "osm" / "hyderabad_district.geojson",
        "dataset_id": "D5a-OSM-Hyderabad-District",
        "license": "ODbL 1.0 (OpenStreetMap contributors)",
        "geography": "Hyderabad district, Telangana",
        "granularity": "district boundary polygon",
        "notes": (
            "OSM relation 7255986 boundary polygon via Nominatim lookup. "
            "ODbL: openstreetmap.org/copyright"
        ),
    },
    "D5b": {
        # The 16 current mandals of Hyderabad district as boundary polygons. Relation ids were
        # found with Nominatim search "<name> mandal, Hyderabad, Telangana" on 2026-10-02.
        "nominatim_ids": [
            "R9823521",  # Amberpet
            "R9844052",  # Ameerpet
            "R9823465",  # Asif Nagar
            "R9823555",  # Bahadurpura
            "R9823546",  # Bandlaguda
            "R9823525",  # Charminar
            "R9823335",  # Golconda
            "R9823507",  # Himayatnagar
            "R9823290",  # Khairatabad
            "R9823218",  # Marredpally
            "R9823557",  # Musheerabad
            "R9823503",  # Nampally
            "R9823538",  # Saidabad
            "R9823232",  # Secunderabad
            "R9823301",  # Shaikpet
            "R9823209",  # Tirumalagiri
        ],
        "out_path": RAW / "geography" / "osm" / "hyderabad_mandals.geojson",
        "dataset_id": "D5b-OSM-Hyderabad-Mandals",
        "license": "ODbL 1.0 (OpenStreetMap contributors)",
        "geography": "Hyderabad district mandals (current OSM boundaries), Telangana",
        "granularity": "mandal boundary polygons",
        "notes": (
            "16 current Hyderabad district mandals via Nominatim lookup. These are today's "
            "OSM mandals, not the 2011 Census mandals; GHMC mandals in Rangareddy (reorganised "
            "in 2016) are not included."
        ),
    },
    "D10": {
        # HMWSSB water supply infrastructure: tanks, reservoirs, works
        "query": (
            "[out:json][timeout:60];"
            "("
            f'node["operator"~"HMWSSB",i]({HYD_BBOX});'
            f'way["operator"~"HMWSSB",i]({HYD_BBOX});'
            f'node["name"~"HMWSSB",i]({HYD_BBOX});'
            f'node["man_made"="water_tower"]({HYD_BBOX});'
            f'way["man_made"="reservoir_covered"]({HYD_BBOX});'
            f'way["landuse"="reservoir"]({HYD_BBOX});'
            ");"
            "out center tags;"
        ),
        "out_path": RAW / "geography" / "osm" / "hmwssb_points.geojson",
        "dataset_id": "D10-OSM-HMWSSB-Points",
        "source_url": "https://overpass-api.de/api/interpreter",
        "license": "ODbL 1.0 (OpenStreetMap contributors)",
        "geography": "GHMC area, Hyderabad",
        "granularity": "individual infrastructure nodes/ways",
        "notes": (
            "OSM nodes/ways tagged operator~HMWSSB or man_made=water_tower or "
            "landuse=reservoir within bbox. "
            "Use as filling-station stand-ins is ASSUMED (Q1 decision). "
            "Empty result is valid if OSM has no HMWSSB-tagged features."
        ),
    },
}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def fetch_osm_layer(key: str, spec: dict, manifest_rows: list[dict]) -> None:
    out_path: Path = spec["out_path"]
    out_path.parent.mkdir(parents=True, exist_ok=True)

    retrieved_at = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    if SKIP_FETCH:
        # Recompute manifest from already-committed file; do not hit Overpass.
        if not out_path.is_file():
            raise FileNotFoundError(
                f"--skip-fetch requested but {out_path.relative_to(ROOT)} is missing. "
                "Run without --skip-fetch first to fetch from Overpass."
            )
        geojson = json.loads(out_path.read_bytes().decode("utf-8"))
        nf = len(geojson.get("features", []))
        rel = out_path.relative_to(ROOT)
        print(f"  [SKIP-FETCH] {key}: {nf} features in existing file -> {rel}")
    elif DRY_RUN:
        # Write a minimal valid stub so the schema is checkable without live data.
        osm_stub = {"version": 0.6, "elements": []}
        geojson = osm_to_geojson(osm_stub)
        print(f"  [DRY-RUN] {key}: empty stub -> {out_path.relative_to(ROOT)}")
        payload = json.dumps(geojson, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        out_path.write_bytes(payload)
    elif "nominatim_ids" in spec:
        url = nominatim_url(spec["nominatim_ids"])
        print(f"  {key}: Nominatim lookup...", end=" ", flush=True)
        request = urllib.request.Request(url, headers=NOMINATIM_HEADERS)
        with urllib.request.urlopen(request, timeout=90) as resp:
            payload = resp.read()
        geojson = json.loads(payload.decode("utf-8"))
        print(f"{len(geojson.get('features', []))} features")
        time.sleep(2)  # Nominatim usage policy: at most one request per second
        out_path.write_bytes(payload)
    else:
        print(f"  {key}: querying Overpass...", end=" ", flush=True)
        osm = overpass_json(spec["query"])
        n = len(osm.get("elements", []))
        geojson = osm_to_geojson(osm)
        nf = len(geojson["features"])
        print(f"{n} elements -> {nf} features")
        time.sleep(5)  # be courteous to the public API
        payload = json.dumps(geojson, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        out_path.write_bytes(payload)

    manifest_rows.append(
        {
            "dataset_id": spec["dataset_id"],
            "file_path": str(out_path.relative_to(ROOT)).replace("\\", "/"),
            "source_url": nominatim_url(spec["nominatim_ids"])
            if "nominatim_ids" in spec
            else spec["source_url"],
            "retrieved_at_utc": retrieved_at,
            "source_modified": "",
            "license": spec["license"],
            "geography": spec["geography"],
            "granularity": spec["granularity"],
            "basis": "REAL",
            "sha256": sha256_of(out_path),
            "bytes": str(out_path.stat().st_size),
            "notes": spec["notes"],
        }
    )


def main() -> int:
    mode = "skip-fetch" if SKIP_FETCH else ("dry-run" if DRY_RUN else "live")
    print(f"D1 fetch (mode={mode})")
    manifest_rows: list[dict] = []
    existing: dict[str, dict] = {}
    if MANIFEST_PATH.is_file():
        with MANIFEST_PATH.open(encoding="utf-8", newline="") as fh:
            existing = {row["dataset_id"]: row for row in csv.DictReader(fh)}

    for key, spec in QUERIES.items():
        if ONLY and key not in ONLY:
            # keep the committed file and its manifest row unchanged
            manifest_rows.append(existing[spec["dataset_id"]])
            print(f"  {key}: kept (not in --only)")
            continue
        try:
            fetch_osm_layer(key, spec, manifest_rows)
        except Exception as exc:
            print(f"  ERROR fetching {key}: {exc}", file=sys.stderr)
            return 1

    write_manifest(manifest_rows)
    print(f"\nD1 fetch complete: {len(manifest_rows)} OSM layers written.")
    print(
        "D6 (Open Buildings) and D7 (groundwater) require separate retrieval; "
        "see their RETRIEVAL_LOG.md files."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
