"""Section need, approximate section areas and section snapshot for the U5 screen.

HMWSSB publishes bookings per section and no section boundaries. Ward need (Census 2011) is
known per ward. This script carries need onto sections:

    section need = sum over wards of (building share of the section in that ward) x ward need

The building shares are the existing dasymetric weights (build_booking_transfer.py:
data/derived/crosswalk/section_ward_building_weights.csv). Wards with no value for an indicator
are left out and the rest renormalised; a section with under MIN_COVERED of its weight covered
has no need (UNAVAILABLE, never zero).

Section areas are the same approximate Voronoi cells that build_booking_transfer.py uses (cells()
in app/services/booking_transfer.py), with thin spikes removed and simplified for the screen.
They are NOT HMWSSB boundaries.

Outputs (all DERIVED_APPROXIMATE, geometry ASSUMED):
- data/derived/evidence/section_need.csv (also read by GET /atlas/live-sections)
- frontend/src/data/u5SectionEvidence.json (same shape as the ward snapshot u5Evidence.json)
- frontend/src/data/u5SectionGeometry.json (same shape as u5Geometry.json; ward_id = section id)
"""

from __future__ import annotations

import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

from pyproj import Transformer
from shapely.geometry import Point, shape
from shapely.ops import transform, unary_union

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
from app.config.allocation import ALLOCATION_CONFIG as ALLOC  # noqa: E402
from app.config.booking_transfer import BOOKING_TRANSFER_CONFIG as GEO  # noqa: E402
from app.config.live_need import LIVE_NEED_CONFIG as LIVE  # noqa: E402
from app.services.booking_transfer import cells  # noqa: E402

sys.path.insert(0, str(ROOT / "scripts" / "evidence"))
from build_booking_transfer import (  # noqa: E402
    OUTPUT_REVIEWED,
    reviewed_points,
)

WEIGHTS = "data/derived/crosswalk/section_ward_building_weights.csv"
# Built by `build_booking_transfer.py --with-reviewed`: the same transfer with the reviewed
# placements of sections the geocoder could not find. Used when present.
POINTS = "data/derived/crosswalk/section_to_ward_2016.csv"
CHECKS = "data/derived/underserved/section_checks.csv"
WARD_NEED = "data/derived/evidence/ward_evidence.csv"
FACILITIES = "data/derived/evidence/facility_points.csv"
EQUITY_SECTIONS = "data/derived/equity/sections.csv"
EQUITY_SUMMARY = "data/derived/equity/summary.json"
WARD_SNAPSHOT = "frontend/src/data/u5Evidence.json"
WARDS = "data/raw/geography/datameet/ghmc-wards.geojson"
NEED_OUT = "data/derived/evidence/section_need.csv"
FACILITIES_OUT = "data/derived/evidence/section_facilities.csv"
EVIDENCE_OUT = "frontend/src/data/u5SectionEvidence.json"
GEOMETRY_OUT = "frontend/src/data/u5SectionGeometry.json"
CELLS_OUT = "data/derived/crosswalk/section_cells.geojson"

INDICATORS = ("wad", "cad", "hardship", "non_tap_share")
MIN_COVERED = 0.5  # share of a section's building weight that must have ward need. ASSUMED.
SIMPLIFY_DEG = 0.0003  # about 30 m: smaller than the 32 m building grid behind the weights.
SMOOTH_M = 90.0  # spikes narrower than twice this are removed from a drawn area. ASSUMED.


def read(path: str) -> list[dict[str, str]]:
    with (ROOT / path).open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def number(text: str | None) -> float | None:
    return float(text) if text not in (None, "") else None


def blend(weights: dict[str, float], values: dict[str, float | None]) -> float | None:
    """Building-weighted mean over the wards that have a value; None if under MIN_COVERED."""
    used = sum(w for ward, w in weights.items() if values.get(ward) is not None)
    if used < MIN_COVERED * sum(weights.values()):
        return None
    return (
        sum(w * values[ward] for ward, w in weights.items() if values.get(ward) is not None) / used
    )


def main() -> None:
    ward_need = {r["ward_id"]: r for r in read(WARD_NEED)}
    ward_growth = {
        w["id"]: w.get("growthRatio")
        for w in json.loads((ROOT / WARD_SNAPSHOT).read_text())["wards"]
    }
    by_section: dict[str, dict[str, float]] = defaultdict(dict)
    with_reviewed = (ROOT / OUTPUT_REVIEWED).exists()
    for r in read(OUTPUT_REVIEWED if with_reviewed else WEIGHTS):
        by_section[r["section"]][r["ward_id"]] = float(r["weight"])

    to_utm = Transformer.from_crs(4326, GEO.projected_crs, always_xy=True)
    to_deg = Transformer.from_crs(GEO.projected_crs, 4326, always_xy=True)
    wards = json.loads((ROOT / WARDS).read_text(encoding="utf-8"))["features"]
    city = unary_union([transform(to_utm.transform, shape(f["geometry"])) for f in wards])
    points = read(POINTS)
    placed = {r["section"] for r in points if r["lat"] and r["lng"]}
    extra = (
        [p for p in reviewed_points(ROOT) if p["section"] not in placed] if with_reviewed else []
    )
    reviewed_names = {p["section"] for p in extra}
    points += extra
    sites = {
        r["section"]: (*to_utm.transform(float(r["lng"]), float(r["lat"])), r["division"])
        for r in points
        if r["lat"] and r["lng"]
    }
    areas = {}
    for name, cell in cells(sites, city, GEO.division_buffer_metres).items():
        smooth = cell.buffer(-SMOOTH_M).buffer(SMOOTH_M).intersection(city)
        areas[name] = smooth if not smooth.is_empty else cell

    facility_rows = read(FACILITIES)
    facilities = [Point(*to_utm.transform(float(r["lon"]), float(r["lat"]))) for r in facility_rows]
    # Each mapped facility goes to the section whose approximate area holds it (areas do not
    # overlap, except sections that share one point). OSM as mapped: incomplete, DERIVED.
    placed_facilities: list[dict[str, str]] = []
    for row, point in zip(facility_rows, facilities, strict=True):
        for section_name, area in areas.items():
            if not area.is_empty and area.contains(point):
                placed_facilities.append(
                    {
                        "section": section_name,
                        **{k: row[k] for k in ("osm_ref", "category", "name", "lat", "lon")},
                        "basis": "DERIVED",
                    }
                )
                break
    history = {(r["division"], r["section"]): r for r in read(EQUITY_SECTIONS)}
    summary = json.loads((ROOT / EQUITY_SUMMARY).read_text())

    need_rows, snapshot, features = [], [], []
    for row in read(CHECKS):
        name, division = row["section"], row["division"]
        weights = by_section.get(name, {})
        values = {
            k: blend(weights, {w: number(ward_need.get(w, {}).get(k)) for w in weights})
            if weights
            else None
            for k in INDICATORS
        }
        ok = (
            values["wad"] is not None
            and values["cad"] is not None
            and values["hardship"] is not None
        )
        score = (
            1
            + ALLOC.need_weight_wad * values["wad"]
            + ALLOC.need_weight_cad * values["cad"]
            + ALLOC.need_weight_hardship * values["hardship"]
            if ok
            else None
        )
        growth = blend(weights, {w: ward_growth.get(w) for w in weights}) if weights else None
        cell = areas.get(name)
        count = sum(1 for p in facilities if cell.contains(p)) if cell is not None else None
        main = max(weights, key=weights.get) if weights else ""
        past = history.get((division, name))
        usual = float(past["bookings"]) / LIVE.history_months if past else None
        conns = number(row["domestic_connections"])
        sid = row["section_id"]
        if ok:
            need_rows.append(
                {
                    "section_id": sid,
                    "section": name,
                    "division": division,
                    "wad": round(values["wad"], 6),
                    "cad": round(values["cad"], 6),
                    "hardship": round(values["hardship"], 6),
                    "non_tap_share": round(values["non_tap_share"] or 0.0, 6),
                    "need_weight": round(score, 4),
                    "growth_ratio": "" if growth is None else round(growth, 6),
                    "critical_facilities": "" if count is None else count,
                    "location_basis": "REVIEWED_PLACEMENT"
                    if name in reviewed_names
                    else "GEOCODED",
                    "main_ward_id": main,
                    "wards_overlapped": len(weights),
                    "domestic_connections": "" if conns is None else round(conns),
                    "usual_month_bookings": "" if usual is None else round(usual, 2),
                    "need_basis": "DERIVED_APPROXIMATE",
                    "method": GEO.method,
                }
            )
        snapshot.append(
            {
                "id": sid,
                "name": name,
                "division": division,
                "censusYear": 2011,
                "reviewRequired": False,
                "population2011": None,
                "households2011": None if conns is None else round(conns),
                "waterAccessDeficitShare": values["wad"],
                "constrainedAccessShare": values["cad"],
                "hardshipShare": values["hardship"],
                "needWeight": None if score is None else round(score, 4),
                "criticalFacilities": count if ok else None,
                "growthRatio": growth,
                "growthQuality": None,
                "bookings": float(past["bookings"]) if past else None,
                "bookingsPer1000": None,
                "bookingStatus": "EXACT_SECTION_COUNT",
                "fieldStatus": row["status"],
                "fieldCandidate": row["field_check_candidate"] == "True",
                "observedBookings": int(float(row["bookings"])),
                "peerExpected": None,
                "modelExpected": None,
                "fieldReasons": [],
            }
        )
        if cell is not None and not cell.is_empty and ok:
            geo = transform(to_deg.transform, cell).simplify(SIMPLIFY_DEG)
            geo = geo if geo.geom_type in ("Polygon", "MultiPolygon") else None
            if geo is not None:
                features.append(
                    {
                        "type": "Feature",
                        "properties": {"ward_id": sid, "ward_name": name},
                        "geometry": json.loads(
                            json.dumps(shape_to_json(geo), separators=(",", ":"))
                        ),
                    }
                )

    with (ROOT / FACILITIES_OUT).open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(placed_facilities[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(sorted(placed_facilities, key=lambda r: (r["section"], r["osm_ref"])))
    # Every section's approximate area, for placing a delivery stop in a section (water debt).
    cells_out = []
    division_of = {r["section"]: r["division"] for r in points}
    for section_name, area in sorted(areas.items()):
        if area.is_empty:
            continue
        shape_geo = transform(to_deg.transform, area).simplify(SIMPLIFY_DEG)
        if shape_geo.geom_type not in ("Polygon", "MultiPolygon"):
            continue
        cells_out.append(
            {
                "type": "Feature",
                "properties": {
                    "section": section_name,
                    "division": division_of.get(section_name, ""),
                },
                "geometry": shape_to_json(shape_geo),
            }
        )
    (ROOT / CELLS_OUT).write_text(
        json.dumps({"type": "FeatureCollection", "features": cells_out}, separators=(",", ":"))
        + "\n"
    )
    fields = list(need_rows[0])
    with (ROOT / NEED_OUT).open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(need_rows)
    evidence = {
        "snapshotDate": "2026-10-06",
        "basis": "DERIVED_APPROXIMATE",
        "geographyVersion": "SECTION_AREAS_APPROXIMATE",
        "sourceNotes": {
            "access": "Census 2011 ward values carried onto sections by Open Buildings share.",
            "areas": "Section areas are approximate Voronoi cells, not HMWSSB boundaries.",
        },
        "summary": {
            "wardCount": len(snapshot),
            "censusMappedCount": len(need_rows),
            "censusReviewCount": 0,
            "fieldCheckCount": sum(1 for s in snapshot if s["fieldCandidate"]),
            "eligibleCount": len(need_rows),
            "dataReviewCount": len(snapshot) - len(need_rows),
            "equity": {
                k: summary[k]
                for k in (
                    "bookings",
                    "delivered",
                    "gini",
                    "top_section_count",
                    "top_booking_share",
                    "bottom_section_count",
                    "bottom_booking_share",
                    "section_count",
                    "missing_source_months",
                    "interpretation",
                )
            },
        },
        "wards": snapshot,
        "fieldCheckLimitations": [],
    }
    (ROOT / EVIDENCE_OUT).write_text(json.dumps(evidence, separators=(",", ":")) + "\n")
    (ROOT / GEOMETRY_OUT).write_text(
        json.dumps({"type": "FeatureCollection", "features": features}, separators=(",", ":"))
        + "\n"
    )
    print(f"{len(snapshot)} sections; need for {len(need_rows)}; drawn {len(features)}")


def shape_to_json(geo) -> dict:
    from shapely.geometry import mapping

    def rnd(c):
        return (
            [rnd(x) for x in c]
            if isinstance(c[0], list | tuple)
            else [round(c[0], 5), round(c[1], 5)]
        )

    m = mapping(geo)
    return {"type": m["type"], "coordinates": rnd(m["coordinates"])}


if __name__ == "__main__":
    main()
