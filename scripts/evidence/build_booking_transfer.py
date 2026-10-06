"""Section-to-ward dasymetric approximation using existing Open Buildings count grids.

This does not claim vector footprints or authoritative section polygons. All outputs are
DERIVED_APPROXIMATE; the geometry/buffer is ASSUMED. No fallback to a point or areal split.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
from pyproj import Transformer
from rasterio.features import geometry_mask
from rasterio.transform import Affine
from shapely.geometry import mapping, shape
from shapely.ops import transform, unary_union

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
from app.config.booking_transfer import BOOKING_TRANSFER_CONFIG as CONFIG  # noqa: E402
from app.services.booking_transfer import cells  # noqa: E402

OUTPUT = "data/derived/crosswalk/section_ward_building_weights.csv"
SUMMARY = "data/derived/crosswalk/section_ward_building_summary.json"
POINTS = "data/derived/crosswalk/section_to_ward_2016.csv"
# Second build (--with-reviewed): the same method with the reviewed placements of sections the
# geocoder could not find (scripts/data/place_missing_sections.py, then a person's review) added as
# extra points. Adding points changes every neighbour's cell, so the whole transfer is rebuilt.
# Written beside, never over, the first build, which the ward-level files were built from.
REVIEWED = "data/derived/crosswalk/section_placement_reviewed.csv"
OUTPUT_REVIEWED = "data/derived/crosswalk/section_ward_building_weights_reviewed.csv"
SUMMARY_REVIEWED = "data/derived/crosswalk/section_ward_building_summary_reviewed.json"
ACCEPTED = ("ACCEPT_AUTO", "ACCEPT_REVIEWED")
GEOMETRY = "data/raw/geography/datameet/ghmc-wards.geojson"


def records(path):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def sample(geometry, values, valid, affine):
    """Sample only the polygon's window; centre-of-cell boundary error is at most one grid cell."""
    if geometry.is_empty:
        return 0.0, 0, 0
    left, bottom, right, top = geometry.bounds
    inv = ~affine
    col0, row0 = inv * (left, top)
    col1, row1 = inv * (right, bottom)
    r0, c0 = max(0, math.floor(row0)), max(0, math.floor(col0))
    r1, c1 = min(values.shape[0], math.ceil(row1)), min(values.shape[1], math.ceil(col1))
    if r1 <= r0 or c1 <= c0:
        return 0.0, 0, 0
    window = values[r0:r1, c0:c1]
    inside = geometry_mask(
        [mapping(geometry)], window.shape, affine * Affine.translation(c0, r0), invert=True
    )
    selected = inside & valid[r0:r1, c0:c1]
    samples = window[selected]
    if np.any(~np.isfinite(samples)) or np.any(samples < 0):
        raise ValueError("Invalid Open Buildings count weights")
    return float(samples.sum(dtype="float64")), int(inside.sum()), int(selected.sum())


def reviewed_points(root):
    """Placed sections of the review file, as rows shaped like the geocoded points."""
    return [
        {"section": r["section"], "division": r["division"], "lat": r["lat"], "lng": r["lng"]}
        for r in records(root / REVIEWED)
        if r["final_status"] in ACCEPTED and r["lat"] and r["lng"]
    ]


def build(root=ROOT, with_reviewed=False):
    projected = Transformer.from_crs(4326, CONFIG.projected_crs, always_xy=True)
    features = json.loads((root / GEOMETRY).read_text(encoding="utf-8"))["features"]
    wards = {
        f["properties"]["@id"]: transform(projected.transform, shape(f["geometry"]))
        for f in features
    }
    city = unary_union(list(wards.values()))
    points = records(root / POINTS)
    if with_reviewed:
        known = {r["section"] for r in points if r["lat"] and r["lng"]}
        points += [p for p in reviewed_points(root) if p["section"] not in known]
    sites = {
        r["section"]: (*projected.transform(float(r["lng"]), float(r["lat"])), r["division"])
        for r in points
        if r["lat"] and r["lng"]
    }
    areas = cells(sites, city, CONFIG.division_buffer_metres)
    intersections = {
        s: {w: cell.intersection(g) for w, g in wards.items() if cell.intersects(g)}
        for s, cell in areas.items()
    }
    masses = {s: defaultdict(float) for s in sites}
    inside, valid_counts = defaultdict(int), defaultdict(int)
    tiles = sorted(
        (root / "data/derived/growth_inputs/tiles").glob(f"{CONFIG.building_year}_*_32m.npz")
    )
    if not tiles:
        raise ValueError("Missing Open Buildings grid inputs")
    inputs = [root / POINTS, root / GEOMETRY] + ([root / REVIEWED] if with_reviewed else [])
    coverage = []
    for path in tiles:
        meta_path = path.with_suffix(".json")
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        if (
            meta["crs"] != CONFIG.projected_crs
            or meta["source_band"] != "building_fractional_count"
            or hashlib.sha256(path.read_bytes()).hexdigest() != meta["archive_sha256"]
        ):
            raise ValueError(f"Invalid grid provenance: {path.name}")
        affine = Affine(*meta["transform"])
        inputs += [path, meta_path]
        with np.load(path, allow_pickle=False) as archive:
            values, valid = archive["values"], archive["valid"]
            from shapely.geometry import box

            x0, y0 = affine * (0, 0)
            x1, y1 = affine * (values.shape[1], values.shape[0])
            extent = box(x0, y1, x1, y0)
            coverage.append(extent)
            for section, cell in areas.items():
                if not extent.intersects(cell):
                    continue
                _, n, v = sample(cell, values, valid, affine)
                inside[section] += n
                valid_counts[section] += v
                for ward, intersection in intersections[section].items():
                    if extent.intersects(intersection):
                        weight, _, _ = sample(intersection, values, valid, affine)
                        masses[section][ward] += weight * meta["native_pixels_per_cell"]
    covered = unary_union(coverage)
    rows, statuses = [], {}
    point_by_section = {r["section"]: r for r in points}
    for section, point in point_by_section.items():
        cell = areas.get(section)
        total = sum(masses.get(section, {}).values())
        fraction = valid_counts[section] / inside[section] if inside[section] else 0
        geometry_coverage = covered.intersection(cell).area / cell.area if cell and cell.area else 0
        status = (
            "UNLOCATED_SECTION"
            if cell is None
            else "EMPTY_CLIPPED_CELL"
            if cell.is_empty
            else "INCOMPLETE_BUILDING_COVERAGE"
            if min(fraction, geometry_coverage) < CONFIG.minimum_valid_coverage
            else "NO_BUILDING_MASS"
            if total <= 0
            else CONFIG.method
        )
        statuses[section] = status
        if status != CONFIG.method:
            continue
        for ward, mass in sorted(masses[section].items()):
            if mass <= 0:
                continue
            rows.append(
                {
                    "section": section,
                    "division": point["division"],
                    "ward_id": ward,
                    "weight": mass / total,
                    "building_count_index": mass,
                    "building_basis": "DERIVED",
                    "coverage_fraction": fraction,
                    "geometry_coverage_fraction": geometry_coverage,
                    "method": CONFIG.method,
                    "basis": "DERIVED_APPROXIMATE",
                }
            )
    summary = {
        "method": CONFIG.method,
        "basis": "DERIVED_APPROXIMATE",
        "geometry_basis": "ASSUMED",
        "division_buffer_metres": CONFIG.division_buffer_metres,
        "building_source": (
            "Open Buildings 2023 fractional-count grid, 32m cached reduction; not vector footprints"
        ),
        "section_status": statuses,
        "weighted_sections": len({r["section"] for r in rows}),
        "ward_count": len({r["ward_id"] for r in rows}),
        "inputs_sha256": {
            str(p.relative_to(root)).replace("\\", "/"): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in inputs
        },
        "limitations": [
            "Voronoi/hull geometry is not an official section boundary.",
            "Building counts do not identify residents, connections, supply or booking demand.",
            "Unlocated/empty/incomplete sections stay unplaced; no point or areal fallback.",
        ],
    }
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return {
        OUTPUT_REVIEWED if with_reviewed else OUTPUT: stream.getvalue().encode(),
        SUMMARY_REVIEWED if with_reviewed else SUMMARY: (
            json.dumps(summary, indent=2, sort_keys=True) + "\n"
        ).encode(),
    }


if __name__ == "__main__":
    reviewed = "--with-reviewed" in sys.argv
    for name, content in build(with_reviewed=reviewed).items():
        (ROOT / name).write_bytes(content)
    print(
        "Approximate building-weighted section transfer built"
        + (" (with reviewed placements)" if reviewed else "")
    )
