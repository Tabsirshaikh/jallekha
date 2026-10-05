"""D9: OSM hospitals, clinics, health centres, schools and care homes counted per 2016 ward.

Reads the logged OSM pull (scripts/data/fetch_d9_facilities.py), puts each feature in one
category and places it on the 2016 ward layer by its position (ways and relations at their
centre). Counts are REAL as mapped in OSM; the ward placement is DERIVED. OSM is incomplete,
so a ward with none mapped may still have some. The solution document's totals (from a D9
snapshot that was never found) are kept in the summary beside ours.

Categories, in priority order (a feature counts once):
  uphcs       a health feature whose name says UPHC, PHC, Urban/Primary Health Centre or
              Basti Dawakhana (public primary care)
  hospitals   amenity=hospital or healthcare=hospital
  clinics     amenity=clinic or doctors, healthcare=clinic, doctor or centre
  schools     amenity=school
  care_homes  amenity=nursing_home, or social_facility nursing_home / assisted_living / group_home
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import re
from collections import Counter
from pathlib import Path

from shapely.geometry import Point, shape
from shapely.prepared import prep

ROOT = Path(__file__).resolve().parents[2]
RAW = "data/raw/d9_facilities/osm_facilities.csv"
WARDS = "data/raw/geography/datameet/ghmc-wards.geojson"
DISTRICT = "data/raw/geography/osm/hyderabad_district.geojson"
INPUTS = (RAW, WARDS, DISTRICT)
OUTPUT = "data/derived/evidence/ward_facilities.csv"
# One row per classified feature with its ward: the F10 candidate critical stops.
POINTS = "data/derived/evidence/facility_points.csv"
SUMMARY = "data/derived/evidence/facilities_summary.json"
CHECKS = "data/verification/facilities_checks.json"
CATEGORIES = ("hospitals", "clinics", "uphcs", "schools", "care_homes")
# Solution document, section 4, D9 row ("885 / 310 / 350 / 399 / 59").
SOLUTION_DOC_TOTALS = {
    "hospitals": 885,
    "clinics": 310,
    "uphcs": 350,
    "schools": 399,
    "care_homes": 59,
}
HEALTH_AMENITY = {"hospital", "clinic", "doctors"}
HEALTHCARE = {"hospital", "clinic", "doctor", "centre"}
CARE_HOME_TYPES = {"nursing_home", "assisted_living", "group_home"}
PRIMARY_CARE_NAME = re.compile(
    r"\b(u\.?\s?p\.?\s?h\.?\s?c|p\.?\s?h\.?\s?c|urban primary health|primary health cent(?:re|er)"
    r"|basti\s*dawa\s*khana)\b",
    re.IGNORECASE,
)


def classify(tags: dict[str, str]) -> str | None:
    """The one category a feature counts in, or None when it is none of the five."""
    amenity = tags.get("amenity", "")
    healthcare = tags.get("healthcare", "")
    health = amenity in HEALTH_AMENITY or healthcare in HEALTHCARE
    if health and PRIMARY_CARE_NAME.search(tags.get("name", "")):
        return "uphcs"
    if amenity == "hospital" or healthcare == "hospital":
        return "hospitals"
    if health:
        return "clinics"
    if amenity == "school":
        return "schools"
    if amenity == "nursing_home" or (
        amenity == "social_facility" and tags.get("social_facility", "") in CARE_HOME_TYPES
    ):
        return "care_homes"
    return None


def place(
    points: list[tuple[str, float, float]], wards: list[tuple[str, object]]
) -> list[str | None]:
    """The ward of each (category, lon, lat) point, or None outside every ward. A point on a
    shared edge goes to the first ward in the given order that covers it."""
    prepared = [(ward_id, prep(polygon)) for ward_id, polygon in wards]
    return [
        next((ward_id for ward_id, poly in prepared if poly.covers(Point(lon, lat))), None)
        for _category, lon, lat in points
    ]


def count_by_ward(
    points: list[tuple[str, float, float]],
    wards: list[tuple[str, object]],
    placed: list[str | None] | None = None,
) -> tuple[dict[str, Counter], Counter]:
    """Counts per ward from (category, lon, lat) points, and the points in no ward."""
    placed = place(points, wards) if placed is None else placed
    counts: dict[str, Counter] = {ward_id: Counter() for ward_id, _ in wards}
    unplaced: Counter = Counter()
    for (category, _lon, _lat), ward in zip(points, placed, strict=True):
        if ward is None:
            unplaced[category] += 1
        else:
            counts[ward][category] += 1
    return counts, unplaced


def _features(root: Path) -> list[dict[str, str]]:
    """Raw OSM rows that fall in one of the categories, with the category added."""
    with (root / RAW).open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    return [{**row, "category": c} for row in rows if (c := classify(row)) is not None]


def _csv(rows: list[dict]) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode()


def build(root: Path = ROOT) -> dict[str, bytes]:
    features = json.loads((root / WARDS).read_text(encoding="utf-8"))["features"]
    wards = sorted(
        ((f["properties"]["@id"], shape(f["geometry"])) for f in features), key=lambda w: w[0]
    )
    names = {f["properties"]["@id"]: f["properties"]["name"] for f in features}
    found = _features(root)
    points = [(f["category"], float(f["lon"]), float(f["lat"])) for f in found]
    placed_in = place(points, wards)
    counts, unplaced = count_by_ward(points, wards, placed_in)

    district_doc = json.loads((root / DISTRICT).read_text(encoding="utf-8"))
    district_geometry = (
        district_doc["features"][0]["geometry"]
        if "features" in district_doc
        else district_doc["geometry"]
    )
    district = prep(shape(district_geometry))
    in_district = Counter(c for c, lon, lat in points if district.covers(Point(lon, lat)))

    output = []
    for ward_id, _polygon in wards:
        row = {"ward_id": ward_id, "ward_name": names[ward_id]}
        row.update({c: counts[ward_id][c] for c in CATEGORIES})
        row["critical_facilities"] = sum(counts[ward_id][c] for c in CATEGORIES)
        row["counts_basis"] = "REAL"
        row["placement_basis"] = "DERIVED"
        row["source"] = "D9-OSM-FACILITIES"
        output.append(row)
    point_rows = [
        {
            "osm_ref": f"{f['osm_type']}/{f['osm_id']}",
            "osm_type": f["osm_type"],
            "osm_id": f["osm_id"],
            "category": f["category"],
            "name": f["name"],
            "lat": f["lat"],
            "lon": f["lon"],
            "ward_id": ward or "",
            "ward_basis": "DERIVED" if ward else "UNPLACED",
        }
        for f, ward in zip(found, placed_in, strict=True)
    ]

    classified = Counter(c for c, _lon, _lat in points)
    placed = {c: sum(counts[w][c] for w, _ in wards) for c in CATEGORIES}
    summary = {
        "source": "D9-OSM-FACILITIES (data/raw/d9_facilities/RETRIEVAL_LOG.md)",
        "categories": list(CATEGORIES),
        "classified_in_bbox": {c: classified[c] for c in CATEGORIES},
        "placed_in_wards": placed,
        "outside_wards": {c: unplaced[c] for c in CATEGORIES},
        "in_hyderabad_district": {c: in_district[c] for c in CATEGORIES},
        "solution_doc_totals": SOLUTION_DOC_TOTALS,
        "wards_with_none_mapped": sum(1 for r in output if r["critical_facilities"] == 0),
        "limitations": [
            "OSM is incomplete and uneven: zero mapped is not zero present.",
            "The original D9 snapshot and its query were never found; tag choices are ours, "
            "so totals differ from the solution document's.",
            "Primary care (UPHC, PHC, Basti Dawakhana) is found by name, so unnamed or "
            "differently named centres count as clinics or hospitals.",
            "Placed on the historical 2016 ward layer (145 polygons; six wards missing).",
        ],
    }
    artifacts = {
        OUTPUT: _csv(output),
        SUMMARY: (json.dumps(summary, indent=2, sort_keys=True) + "\n").encode(),
        POINTS: _csv(point_rows),
    }
    checks = {
        "inputs_sha256": {p: hashlib.sha256((root / p).read_bytes()).hexdigest() for p in INPUTS},
        "outputs_sha256": {p: hashlib.sha256(b).hexdigest() for p, b in artifacts.items()},
        "schema_version": "D9-1",
    }
    artifacts[CHECKS] = (json.dumps(checks, indent=2, sort_keys=True) + "\n").encode()
    return artifacts


if __name__ == "__main__":
    for name, content in build().items():
        path = ROOT / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    print("D9 facilities counted per 2016 ward; see facilities_summary.json.")
