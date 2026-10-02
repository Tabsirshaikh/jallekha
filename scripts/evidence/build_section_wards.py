"""Place HMWSSB sections on 2016 GHMC wards (section -> ward link for the A3 fair queue).

HMWSSB publishes bookings per section with no section boundaries or locations. Sections are
named after localities, so:

1. Each cleaned section name was looked up with Nominatim inside the GHMC box
   (scripts/data/fetch_section_geocodes.py, raw answers committed).
2. The best answer inside GHMC (1 km margin) is kept: places/boundaries first, then by OSM
   importance.
3. The section goes to the 2016 ward containing that point, or the nearest ward within 500 m
   when the point falls in a gap of the ward layer.
4. Check: sections of one HMWSSB division lie close together. A section farther from the
   median location of its division than both OUTLIER_KM and SPREAD_FACTOR x the division's
   median distance is a likely wrong lookup (e.g. another place with the same name) and is
   not used. The relative part keeps wide edge-of-city divisions from being cut.
5. Second chance for unplaced sections, each within 6 km of its division's centre: another
   OSM answer for the same name (common names like "Srinivas Nagar" have several), or a 2016
   ward whose name is a spelling variant ("Mehidipatnam" -> "Mehdipatnam").
6. Independent check (names never decide the ward in step 3): a section placed by its own OSM
   location and named like a 2016 ward should land in that ward or a neighbouring one.

The link is DERIVED and approximate (one point per section, not a service area). Voronoi
service areas are deliberately not generated (docs/research/P1.md).
"""

from __future__ import annotations

import csv
import io
import json
import math
import re
import statistics
import sys
from collections import defaultdict
from difflib import SequenceMatcher
from pathlib import Path

from pyproj import Transformer
from shapely.geometry import Point, shape
from shapely.ops import transform, unary_union

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "scripts" / "data"))
from fetch_section_geocodes import LAST_MONTH_BEFORE_RECUT, clean_name  # noqa: E402

from app.services import hmwssb  # noqa: E402

SEARCH = "data/raw/geography/nominatim/hmwssb_section_search.json"
WARDS = "data/raw/geography/datameet/ghmc-wards.geojson"
ZONES = "data/raw/geography/datameet/ghmc-zones.geojson"
PORTAL = "data/raw/hmwssb_tankers_portal"
OUTPUT = "data/derived/crosswalk/section_to_ward_2016.csv"
SUMMARY = "data/derived/crosswalk/section_to_ward_summary.json"

GHMC_MARGIN_M = 1000.0
NEAREST_WARD_M = 500.0
# A section farther than both limits from its division's median location is treated as a
# wrong lookup. Basis: ASSUMED; HMWSSB divisions span a few kilometres in the core and more at
# the edge of the city, hence the relative limit.
OUTLIER_KM = 6.0
SPREAD_FACTOR = 3.0
MIN_DIVISION_SECTIONS = 3
# Second pass: a 2016 ward name counts as a spelling variant of a section name at this
# similarity, clearly ahead of the next ward name. Basis: ASSUMED.
WARD_NAME_MIN_RATIO = 0.85
WARD_NAME_MARGIN = 0.05
ADJACENT_M = 200.0
PREFERRED_CATEGORIES = ("place", "boundary")


def _norm(text: str) -> str:
    return re.sub(r"[^a-z]", "", text.lower())


def _best(results: list[dict], ghmc, to_utm) -> dict | None:
    inside = [r for r in results if ghmc.contains(Point(to_utm(float(r["lon"]), float(r["lat"]))))]
    if not inside:
        return None
    return sorted(
        inside,
        key=lambda r: (
            r.get("category") not in PREFERRED_CATEGORIES,
            -float(r.get("importance") or 0),
            str(r.get("osm_id")),
        ),
    )[0]


def build(root: Path = ROOT) -> dict[str, bytes]:
    to_utm = Transformer.from_crs("EPSG:4326", "EPSG:32644", always_xy=True).transform
    zones = json.loads((root / ZONES).read_text(encoding="utf-8-sig"))["features"]
    ghmc = transform(to_utm, unary_union([shape(f["geometry"]) for f in zones])).buffer(
        GHMC_MARGIN_M
    )
    wards = {}
    for feature in json.loads((root / WARDS).read_text(encoding="utf-8-sig"))["features"]:
        props = feature["properties"]
        wards[props["@id"]] = (props["name"], transform(to_utm, shape(feature["geometry"])))
    answers = {
        q["name"]: q["results"]
        for q in json.loads((root / SEARCH).read_text(encoding="utf-8"))["queries"]
    }

    bookings: dict[str, int] = defaultdict(int)
    division: dict[str, str] = {}
    for row in hmwssb.read_rows(root / PORTAL):
        if (row["year"], row["month"]) <= LAST_MONTH_BEFORE_RECUT:
            bookings[row["section"]] += row["bookings"]
            division[row["section"]] = row["division"]

    table = []
    for section in sorted(bookings):
        name = clean_name(section)
        best = _best(answers.get(name, []), ghmc, to_utm)
        row = {
            "section": section,
            "division": division[section],
            "lookup_name": name,
            "lat": "",
            "lng": "",
            "osm": "",
            "osm_label": "",
            "ward_id": "",
            "ward_name": "",
            "ward_method": "",
            "division_distance_km": "",
            "status": "UNMAPPED_NO_RESULT",
            "bookings_2022_01_2026_01": bookings[section],
            "basis": "DERIVED",
        }
        if best:
            x, y = to_utm(float(best["lon"]), float(best["lat"]))
            point = Point(x, y)
            row.update(
                lat=f"{float(best['lat']):.6f}",
                lng=f"{float(best['lon']):.6f}",
                osm=f"{best.get('osm_type')}/{best.get('osm_id')}",
                osm_label=f"{best.get('category')}:{best.get('type')}",
                status="UNMAPPED_NO_WARD",
            )
            containing = [wid for wid, (_, geom) in wards.items() if geom.contains(point)]
            if containing:
                ward_id, method = containing[0], "INSIDE"
            else:
                ward_id, distance = min(
                    ((wid, geom.distance(point)) for wid, (_, geom) in wards.items()),
                    key=lambda item: item[1],
                )
                method = "NEAREST_500M" if distance <= NEAREST_WARD_M else ""
                ward_id = ward_id if method else ""
            if ward_id:
                row.update(
                    ward_id=ward_id,
                    ward_name=wards[ward_id][0],
                    ward_method=method,
                    status="MAPPED",
                )
            row["_xy"] = (x, y)
        table.append(row)

    # division check
    by_division: dict[str, list[dict]] = defaultdict(list)
    for row in table:
        if "_xy" in row:
            by_division[row["division"]].append(row)
    for members in by_division.values():
        if len(members) < MIN_DIVISION_SECTIONS:
            continue
        mx = statistics.median(r["_xy"][0] for r in members)
        my = statistics.median(r["_xy"][1] for r in members)
        distances = {r["section"]: math.dist(r["_xy"], (mx, my)) / 1000 for r in members}
        limit = max(OUTLIER_KM, SPREAD_FACTOR * statistics.median(distances.values()))
        for row in members:
            km = distances[row["section"]]
            row["division_distance_km"] = f"{km:.2f}"
            if km > limit:
                row.update(
                    ward_id="", ward_name="", ward_method="", status="UNMAPPED_DIVISION_OUTLIER"
                )

    # second chance for unplaced sections, both checked against the division (strict limit):
    # 2. another OSM answer for the same name (common names have several) near the division;
    # 3. a 2016 ward whose name is a spelling variant of the section name.
    to_wgs = Transformer.from_crs("EPSG:32644", "EPSG:4326", always_xy=True).transform
    centres = {}
    for division in {r["division"] for r in table}:
        points = [r["_xy"] for r in table if r["division"] == division and r["status"] == "MAPPED"]
        if len(points) >= MIN_DIVISION_SECTIONS:
            centres[division] = (
                statistics.median(p[0] for p in points),
                statistics.median(p[1] for p in points),
            )
    ward_keys = {wid: _norm(re.sub(r"^Ward \d+ ", "", name)) for wid, (name, _) in wards.items()}

    def place(row, x, y, method):
        point = Point(x, y)
        inside = [wid for wid, (_, geom) in wards.items() if geom.contains(point)]
        if not inside:
            return False
        lng, lat = to_wgs(x, y)
        row.update(
            lat=f"{lat:.6f}",
            lng=f"{lng:.6f}",
            ward_id=inside[0],
            ward_name=wards[inside[0]][0],
            ward_method=method,
            division_distance_km=f"{math.dist((x, y), centres[row['division']]) / 1000:.2f}",
            status="MAPPED",
            _xy=(x, y),
        )
        return True

    for row in table:
        if row["status"] == "MAPPED" or row["division"] not in centres:
            continue
        centre = centres[row["division"]]
        candidates = [
            to_utm(float(r["lon"]), float(r["lat"]))
            for r in answers.get(row["lookup_name"], [])
            if ghmc.contains(Point(to_utm(float(r["lon"]), float(r["lat"]))))
        ]
        near = [c for c in candidates if math.dist(c, centre) / 1000 <= OUTLIER_KM]
        if near:
            best = min(near, key=lambda c: math.dist(c, centre))
            row["osm_label"] = row["osm_label"] or "second_pass"
            if place(row, best[0], best[1], "OSM_NEAR_DIVISION"):
                continue
        key = _norm(
            re.sub(r"\b(HIGH LEVEL|LOW LEVEL|OLD|NEW|SECTION)\b", "", row["section"].split("(")[0])
        )
        scores = sorted(
            ((SequenceMatcher(None, key, value).ratio(), wid) for wid, value in ward_keys.items()),
            reverse=True,
        )
        if scores[0][0] >= WARD_NAME_MIN_RATIO and scores[0][0] - scores[1][0] >= WARD_NAME_MARGIN:
            spot = wards[scores[0][1]][1].representative_point()
            if math.dist((spot.x, spot.y), centre) / 1000 <= OUTLIER_KM:
                place(row, spot.x, spot.y, "WARD_NAME")

    # independent name check (only sections placed by their own OSM location)
    by_name = {_norm(re.sub(r"^Ward \d+ ", "", name)): wid for wid, (name, _) in wards.items()}
    pairs = hits = 0
    for row in table:
        if row["status"] != "MAPPED" or row["ward_method"] not in ("INSIDE", "NEAREST_500M"):
            continue
        key = _norm(row["lookup_name"])
        same = [wid for n, wid in by_name.items() if SequenceMatcher(None, n, key).ratio() >= 0.9]
        if len(same) != 1:
            continue
        pairs += 1
        target = wards[same[0]][1].buffer(ADJACENT_M)
        hits += row["ward_id"] == same[0] or target.intersects(wards[row["ward_id"]][1])

    for row in table:
        row.pop("_xy", None)
    total = sum(bookings.values())
    mapped = [r for r in table if r["status"] == "MAPPED"]
    summary = {
        "sections": len(table),
        "mapped_section_count": len(mapped),
        "mapped_booking_share": round(
            sum(r["bookings_2022_01_2026_01"] for r in mapped) / total, 4
        ),
        "status_counts": {
            s: sum(r["status"] == s for r in table) for s in sorted({r["status"] for r in table})
        },
        "wards_with_a_section": len({r["ward_id"] for r in mapped}),
        "checks": {
            "same_name_ward_pairs": pairs,
            "same_name_in_or_adjacent_share": round(hits / pairs, 4) if pairs else None,
            "outlier_km": OUTLIER_KM,
            "outlier_spread_factor": SPREAD_FACTOR,
        },
        "method": "Nominatim lookup of the section locality name inside GHMC; point in 2016 ward",
        "limitations": [
            "One point per section, not a service area; a section serving several wards is "
            "attributed to one.",
            "Unmapped sections use a flagged fallback entitlement in the fair queue.",
            "Section names after the Feb/Mar 2026 re-cut are not covered.",
        ],
    }
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=list(table[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(table)
    return {
        OUTPUT: stream.getvalue().encode(),
        SUMMARY: (json.dumps(summary, indent=2, sort_keys=True) + "\n").encode(),
    }


if __name__ == "__main__":
    for name, content in build().items():
        path = ROOT / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    print("Section -> 2016 ward links built.")
