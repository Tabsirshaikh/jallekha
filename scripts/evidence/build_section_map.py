"""Section need and approximate section areas for the U5 map (feat/section-need-map).

HMWSSB publishes bookings per section and no section boundaries. Ward need (Census 2011) is
known per ward. This script carries need onto sections:

    section need = sum over wards of (building share of the section in that ward) x ward need

The building shares are the existing dasymetric weights (build_booking_transfer.py:
data/derived/crosswalk/section_ward_building_weights.csv). Wards with no value for an indicator
are left out and the rest renormalised; a section with under MIN_COVERED of its weight covered
has no need (UNAVAILABLE, never zero).

Section areas are the same approximate Voronoi cells that build_booking_transfer.py uses (cells()
in app/services/booking_transfer.py), simplified for the screen. They are NOT HMWSSB boundaries.

Outputs (all DERIVED_APPROXIMATE, geometry ASSUMED):
- data/derived/evidence/section_need.csv
- frontend/src/data/u5Sections.json (one item per section checked in 2025: need, bookings,
  rate, peer rate, expected bookings, flag, and the area outline as lng/lat rings)
"""

from __future__ import annotations

import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

from pyproj import Transformer
from shapely.geometry import shape
from shapely.ops import transform, unary_union

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
from app.config.allocation import ALLOCATION_CONFIG as ALLOC  # noqa: E402
from app.config.booking_transfer import BOOKING_TRANSFER_CONFIG as GEO  # noqa: E402
from app.services.booking_transfer import cells  # noqa: E402

WEIGHTS = "data/derived/crosswalk/section_ward_building_weights.csv"
POINTS = "data/derived/crosswalk/section_to_ward_2016.csv"
CHECKS = "data/derived/underserved/section_checks.csv"
WARD_NEED = "data/derived/evidence/ward_evidence.csv"
WARDS = "data/raw/geography/datameet/ghmc-wards.geojson"
NEED_OUT = "data/derived/evidence/section_need.csv"
MAP_OUT = "frontend/src/data/u5Sections.json"

INDICATORS = ("wad", "cad", "hardship", "non_tap_share")
MIN_COVERED = 0.5  # share of a section's building weight that must have ward need. ASSUMED.
SIMPLIFY_DEG = 0.0003  # about 30 m: smaller than the 32 m building grid behind the weights.


def read(path: str) -> list[dict[str, str]]:
    with (ROOT / path).open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def number(text: str | None) -> float | None:
    return float(text) if text not in (None, "") else None


def section_need(weights: dict[str, float], ward_need: dict[str, dict[str, str]]) -> dict | None:
    """Building-weighted ward need; None when too little of the section has ward need."""
    out: dict[str, float] = {}
    covered = 0.0
    for name in INDICATORS:
        total = used = 0.0
        for ward, w in weights.items():
            value = number(ward_need.get(ward, {}).get(name))
            if value is not None:
                total += w * value
                used += w
        if used < MIN_COVERED * sum(weights.values()):
            return None
        out[name] = total / used
        covered = used / sum(weights.values()) if name == "wad" else covered
    out["need_weight"] = (
        1
        + ALLOC.need_weight_wad * out["wad"]
        + ALLOC.need_weight_cad * out["cad"]
        + ALLOC.need_weight_hardship * out["hardship"]
    )
    out["covered_weight"] = covered
    return out


def main() -> None:
    ward_need = {r["ward_id"]: r for r in read(WARD_NEED)}
    by_section: dict[str, dict[str, float]] = defaultdict(dict)
    for r in read(WEIGHTS):
        by_section[r["section"]][r["ward_id"]] = float(r["weight"])

    to_utm = Transformer.from_crs(4326, GEO.projected_crs, always_xy=True)
    to_deg = Transformer.from_crs(GEO.projected_crs, 4326, always_xy=True)
    wards = json.loads((ROOT / WARDS).read_text(encoding="utf-8"))["features"]
    city = unary_union([transform(to_utm.transform, shape(f["geometry"])) for f in wards])
    points = read(POINTS)
    sites = {
        r["section"]: (*to_utm.transform(float(r["lng"]), float(r["lat"])), r["division"])
        for r in points
        if r["lat"] and r["lng"]
    }
    areas = cells(sites, city, GEO.division_buffer_metres)

    items, need_rows = [], []
    for row in read(CHECKS):
        name = row["section"]
        need = section_need(by_section[name], ward_need) if name in by_section else None
        if name in by_section and need is not None:
            need_rows.append(
                {
                    "section": name,
                    "division": row["division"],
                    **{k: round(v, 6) for k, v in need.items()},
                    "wards_overlapped": len(by_section[name]),
                    "need_basis": "DERIVED_APPROXIMATE",
                    "method": GEO.method,
                }
            )
        outline = []
        cell = areas.get(name)
        if cell is not None and not cell.is_empty:
            geo = transform(to_deg.transform, cell).simplify(SIMPLIFY_DEG)
            polys = list(geo.geoms) if geo.geom_type == "MultiPolygon" else [geo]
            outline = [
                [[round(x, 5), round(y, 5)] for x, y in p.exterior.coords]
                for p in polys
                if p.geom_type == "Polygon" and not p.is_empty
            ]
        conns = number(row["domestic_connections"])
        peer = number(row["reference_rate"])
        items.append(
            {
                "section_id": row["section_id"],
                "section": name,
                "division": row["division"],
                "bookings": int(float(row["bookings"])),
                "connections": round(conns) if conns else None,
                "rate": number(row["rate"]),
                "peer_rate": peer,
                "expected": round(peer * conns / 1000) if peer is not None and conns else None,
                "ratio": number(row["ratio"]),
                "peers": json.loads(row["peer_sections"]),
                "flagged": row["field_check_candidate"] == "True",
                "status": row["status"],
                "location": "approximate" if row["location_basis"] else "none",
                "need": (
                    {k: round(need[k], 4) for k in ("need_weight", "wad", "cad", "hardship")}
                    if need
                    else None
                ),
                "outline": outline,
            }
        )

    fields = list(need_rows[0])
    with (ROOT / NEED_OUT).open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(need_rows)
    payload = {
        "basis": "DERIVED_APPROXIMATE",
        "note": "Section areas are approximate Voronoi cells, not HMWSSB boundaries.",
        "year": 2025,
        "items": items,
    }
    (ROOT / MAP_OUT).write_text(json.dumps(payload, separators=(",", ":")) + "\n", encoding="utf-8")
    drawn = sum(1 for i in items if i["outline"])
    print(
        f"{len(items)} sections; need for {len(need_rows)}; drawn {drawn}; "
        f"flagged {sum(i['flagged'] for i in items)}"
    )


if __name__ == "__main__":
    main()
