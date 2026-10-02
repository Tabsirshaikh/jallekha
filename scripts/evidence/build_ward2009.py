"""Rebuild the 2009 GHMC ward map and the 2009 -> 2016 ward crosswalk.

Why: Census 2011 numbers GHMC wards by the 2009 delimitation. The DataMeet layer is the 2016
delimitation, in which wards were renumbered and redrawn (only 15 of 144 numbers keep their
name). Joining by ward number puts Census values on the wrong area.

Method:
1. Ward boundaries and red ward-number labels are read from the official vector PDF
   (GHMC election_wards.pdf, 2009). Boundary lines are polygonized; each face takes the
   label inside it. The PDF has no line between wards 111 and 112, so they form one unit.
2. The union of the faces (the GHMC outline) is fitted to the DataMeet GHMC outline with an
   affine transform (symmetric iterative closest point, UTM 44N metres).
3. Independent checks (never used in the fit): the Census district of each ward against the
   OSM Hyderabad district polygon, and 2009 ward names against 2016 ward names.
4. Crosswalk weights: share of each 2009 ward's buildings (Open Buildings 2016 fractional
   count, 32 m grid from E3) that falls in each 2016 ward; area shares are kept alongside.

Outputs are DERIVED and approximate; boundary error is reported in the summary.
"""

from __future__ import annotations

import csv
import io
import json
import math
import re
from collections import defaultdict
from pathlib import Path

import numpy as np
import pdfplumber
import shapely
from pyproj import Transformer
from shapely.geometry import LineString, Point, Polygon, mapping, shape
from shapely.ops import polygonize, transform, unary_union

ROOT = Path(__file__).resolve().parents[2]
PDF = "data/raw/geography/ghmc_2009/ghmc_election_wards_2009.pdf"
NAMES = "data/raw/geography/ghmc_2009/wikipedia_ghmc_2009_election.json"
DISTRICT = "data/raw/geography/nominatim/hyderabad_district.geojson"
ZONES = "data/raw/geography/datameet/ghmc-zones.geojson"
WARDS_2016 = "data/raw/geography/datameet/ghmc-wards.geojson"
CENSUS_HYD = "data/raw/census/hyderabad/pca.csv"
TILES = "data/derived/growth_inputs/tiles"

WARDS = "data/derived/ward2009/ghmc_wards_2009.geojson"
SUMMARY = "data/derived/ward2009/summary.json"
WEIGHTS = "data/derived/crosswalk/ward2009_to_ghmc2016_weights.csv"

UTM = "EPSG:32644"
WARD_LINE_WIDTH = 2.88  # purple ward boundaries in the PDF legend
LABEL_COLOUR = (1.0, 0.0, 0.0)  # red ward numbers
MIN_FACE_AREA = 500.0  # PDF points^2; drops slivers between double-drawn lines
ICP_ITERATIONS = 100


def ward_names(root: Path = ROOT) -> dict[int, str]:
    """Ward number -> name from the pinned Wikipedia revision of the 2009 results table."""
    text = json.loads((root / NAMES).read_text(encoding="utf-8"))["parse"]["wikitext"]
    table = text[text.index("Results by ward") :]
    names = {}
    for number, cell in re.findall(r"\|-\n\|(\d+)\n\|([^\n]+)", table):
        link = re.fullmatch(r"\[\[(?:[^|\]]*\|)?([^\]]+)\]\]", cell.strip())
        names[int(number)] = (link.group(1) if link else cell).strip()
    return names


def pdf_geometry(root: Path = ROOT) -> tuple[list[Polygon], list[tuple[int, Point]]]:
    with pdfplumber.open(root / PDF) as pdf:
        page = pdf.pages[0]
        segments = [
            LineString([a, b])
            for obj in page.curves + page.lines
            if round(obj.get("linewidth") or 0, 2) == WARD_LINE_WIDTH
            for a, b in zip(obj["pts"], obj["pts"][1:], strict=False)
        ]
        words = page.extract_words(extra_attrs=["non_stroking_color"])
    labels = [
        (int(w["text"]), Point((w["x0"] + w["x1"]) / 2, (w["top"] + w["bottom"]) / 2))
        for w in words
        if re.fullmatch(r"\d{1,3}", w["text"])
        and tuple(w["non_stroking_color"] or ()) == LABEL_COLOUR
    ]
    faces = [f for f in polygonize(unary_union(segments)) if f.area > MIN_FACE_AREA]
    return faces, labels


def assemble_units(
    faces: list[Polygon], labels: list[tuple[int, Point]]
) -> dict[tuple[int, ...], Polygon]:
    """Group faces by the ward numbers they contain. Faces without a label are not wards."""
    parts: dict[tuple[int, ...], list[Polygon]] = defaultdict(list)
    for face in faces:
        inside = tuple(sorted({n for n, point in labels if face.contains(point)}))
        if inside:
            parts[inside].append(face)
    # a number that also appears inside a multi-number face belongs to that unit
    merged = [key for key in parts if len(key) > 1]
    for key in merged:
        for number in key:
            if (number,) in parts:
                parts[key].extend(parts.pop((number,)))
    return {key: unary_union(polys) for key, polys in sorted(parts.items())}


def _largest(geometry):
    return max(geometry.geoms, key=lambda g: g.area) if hasattr(geometry, "geoms") else geometry


def _ring_points(polygon: Polygon, n: int) -> np.ndarray:
    ring = polygon.exterior
    return np.array([ring.interpolate(i / n, normalized=True).coords[0] for i in range(n)])


def _nearest(a: np.ndarray, b: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    d2 = ((a[:, None, :] - b[None, :, :]) ** 2).sum(-1)
    return b[d2.argmin(1)], np.sqrt(d2.min(1))


def fit_affine(source: Polygon, target: Polygon) -> tuple[np.ndarray, np.ndarray, dict]:
    """Affine map from PDF page points to UTM metres, by symmetric iterative closest point."""
    src = _ring_points(source, 1500)
    dst = _ring_points(target, 3000)
    scale = math.sqrt(target.area / source.area)
    a = scale * np.diag([1.0, -1.0])  # page y grows downwards
    t = np.array(target.centroid.coords[0]) - a @ np.array(source.centroid.coords[0])
    for _ in range(ICP_ITERATIONS):
        forward, _ = _nearest(src @ a.T + t, dst)
        backward, _ = _nearest(dst, src @ a.T + t)
        back_src = (backward - t) @ np.linalg.inv(a).T
        x = np.vstack([src, back_src])
        y = np.vstack([forward, dst])
        solution, *_ = np.linalg.lstsq(np.hstack([x, np.ones((len(x), 1))]), y, rcond=None)
        a, t = solution[:2].T, solution[2]
    _, error = _nearest(src @ a.T + t, dst)
    metrics = {
        "median_boundary_error_m": round(float(np.median(error)), 1),
        "p90_boundary_error_m": round(float(np.percentile(error, 90)), 1),
        "metres_per_pdf_point": [round(float(v), 3) for v in np.sqrt((a**2).sum(0))],
    }
    return a, t, metrics


def _affine(a: np.ndarray, t: np.ndarray):
    def apply(x, y, z=None):
        x, y = np.asarray(x), np.asarray(y)
        return a[0, 0] * x + a[0, 1] * y + t[0], a[1, 0] * x + a[1, 1] * y + t[1]

    return apply


def _load_features(root: Path, relative: str) -> list[dict]:
    return json.loads((root / relative).read_text(encoding="utf-8-sig"))["features"]


def _wards_2016(root: Path, to_utm) -> dict[str, tuple[int, str, Polygon]]:
    out = {}
    for feature in _load_features(root, WARDS_2016):
        match = re.match(r"Ward (\d+) (.*)", feature["properties"]["name"])
        geometry = transform(to_utm, shape(feature["geometry"])).buffer(0)
        out[feature["properties"]["@id"]] = (int(match.group(1)), match.group(2), geometry)
    return out


def census_hyderabad_wards(root: Path = ROOT) -> set[int]:
    with (root / CENSUS_HYD).open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    return {
        int(m.group(1))
        for r in rows
        if "GHMC" in r["VName"].upper() and (m := re.search(r"WARD NO\.-0*(\d+)", r["VName"]))
    }


def building_cells(root: Path = ROOT) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Cell centres (UTM) and Open Buildings 2016 fractional counts from the E3 tiles."""
    xs, ys, vs = [], [], []
    for meta_path in sorted((root / TILES).glob("2016_*_32m.json")):
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        if meta["crs"] != UTM:
            raise ValueError(f"Unexpected tile CRS in {meta_path.name}")
        grid = np.load(meta_path.with_suffix(".npz"))
        values = np.where(grid["valid"], grid["values"], 0.0)
        a, _, c, _, e, f = meta["transform"]
        rows, cols = np.nonzero(values > 0)
        xs.append(c + (cols + 0.5) * a)
        ys.append(f + (rows + 0.5) * e)
        vs.append(values[rows, cols].astype(float))
    x, y, v = np.concatenate(xs), np.concatenate(ys), np.concatenate(vs)
    # tiles may overlap at their edges: keep one value per cell centre
    _, keep = np.unique(np.round(np.column_stack([x, y]), 1), axis=0, return_index=True)
    keep.sort()
    return x[keep], y[keep], v[keep]


def _assign(polygons: dict, x: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Index of the polygon containing each point (-1 when none)."""
    owner = np.full(len(x), -1)
    for index, polygon in enumerate(polygons.values()):
        x0, y0, x1, y1 = polygon.bounds
        box = np.nonzero((x >= x0) & (x <= x1) & (y >= y0) & (y <= y1) & (owner < 0))[0]
        if len(box):
            inside = shapely.contains_xy(polygon, x[box], y[box])
            owner[box[inside]] = index
    return owner


def unit_key(numbers: tuple[int, ...]) -> str:
    return ";".join(str(n) for n in numbers)


def build(root: Path = ROOT) -> dict[str, bytes]:
    to_utm = Transformer.from_crs("EPSG:4326", UTM, always_xy=True).transform
    to_wgs = Transformer.from_crs(UTM, "EPSG:4326", always_xy=True).transform

    faces, labels = pdf_geometry(root)
    units_page = assemble_units(faces, labels)
    zones = unary_union([shape(f["geometry"]) for f in _load_features(root, ZONES)]).buffer(0)
    outline_target = _largest(transform(to_utm, zones))
    a, t, fit = fit_affine(_largest(unary_union(list(units_page.values()))), outline_target)
    to_page_utm = _affine(a, t)
    units = {key: transform(to_page_utm, poly).buffer(0) for key, poly in units_page.items()}
    fitted_outline = unary_union(list(units.values()))
    fit["outline_iou"] = round(
        fitted_outline.intersection(outline_target).area
        / fitted_outline.union(outline_target).area,
        4,
    )
    fit["method"] = "affine, symmetric iterative closest point to DataMeet GHMC outline"

    # check 1: Census district (wards in the Hyderabad district PCA) vs OSM district polygon
    district = transform(to_utm, shape(_load_features(root, DISTRICT)[0]["geometry"]))
    in_census_hyd = census_hyderabad_wards(root)
    agree = false_inside = 0
    for key, polygon in units.items():
        inside = polygon.intersection(district).area / polygon.area >= 0.5
        census = any(n in in_census_hyd for n in key)
        agree += inside == census
        false_inside += inside and not census

    # check 2: 2009 ward names vs 2016 ward names (largest overlap)
    names = ward_names(root)
    wards16 = _wards_2016(root, to_utm)
    norm = {n: re.sub(r"[^a-z]", "", name.lower()) for n, name in names.items()}
    name_hits = name_total = 0
    for _number16, name16, geometry16 in wards16.values():
        same = [
            key
            for key in units
            if any(norm[n] == re.sub(r"[^a-z]", "", name16.lower()) for n in key)
        ]
        if len(same) != 1:
            continue
        name_total += 1
        largest = max(units, key=lambda key: units[key].intersection(geometry16).area)
        name_hits += largest == same[0]

    # crosswalk weights from building cells and areas
    x, y, v = building_cells(root)
    unit_owner = _assign(units, x, y)
    ward_owner = _assign({wid: g for wid, (_, _, g) in wards16.items()}, x, y)
    unit_keys, ward_ids = list(units), list(wards16)
    unit_total = np.bincount(
        unit_owner[unit_owner >= 0], weights=v[unit_owner >= 0], minlength=len(unit_keys)
    )
    pair = defaultdict(float)
    for u, w, value in zip(unit_owner, ward_owner, v, strict=True):
        if u >= 0 and w >= 0:
            pair[(u, w)] += value
    weight_rows = []
    for (u, w), value in sorted(pair.items()):
        share = value / unit_total[u]
        if share < 0.0005:
            continue
        unit_poly = units[unit_keys[u]]
        number16, name16, geometry16 = wards16[ward_ids[w]]
        weight_rows.append(
            {
                "source_unit_2009": unit_key(unit_keys[u]),
                "source_names_2009": "; ".join(names[n] for n in unit_keys[u]),
                "target_ward_id": ward_ids[w],
                "target_ward_name": f"Ward {number16} {name16}",
                "building_share": f"{share:.4f}",
                "building_index": f"{value:.4f}",
                "area_share": f"{unit_poly.intersection(geometry16).area / unit_poly.area:.4f}",
                "weight_basis": "DERIVED",
            }
        )

    features = []
    for key, polygon in units.items():
        geometry = shapely.set_precision(transform(to_wgs, polygon), 1e-6)
        features.append(
            {
                "type": "Feature",
                "properties": {
                    "unit_2009": unit_key(key),
                    "ward_numbers_2009": list(key),
                    "names_2009": [names[n] for n in key],
                    "geo_version": "GHMC_2009_150",
                    "basis": "DERIVED",
                    "method": "Polygonized from official GHMC 2009 ward PDF; affine-fitted",
                },
                "geometry": mapping(
                    geometry
                    if geometry.geom_type == "MultiPolygon"
                    else shapely.MultiPolygon([geometry])
                ),
            }
        )
    summary = {
        "units": len(units),
        "ward_numbers_covered": sorted(n for key in units for n in key) == list(range(1, 151)),
        "merged_units": [unit_key(k) for k in units if len(k) > 1],
        "fit": fit,
        "checks": {
            "census_district_agreement": round(agree / len(units), 4),
            "census_district_false_inside": false_inside,
            "same_name_pairs": name_total,
            "same_name_largest_overlap_share": round(name_hits / name_total, 4),
        },
        "weights": {
            "source": "Open Buildings 2.5D Temporal 2016 fractional count (E3 tiles, 32 m)",
            "sources_with_90pct_in_2016_layer": int(
                sum(
                    sum(
                        float(r["building_share"])
                        for r in weight_rows
                        if r["source_unit_2009"] == unit_key(k)
                    )
                    >= 0.9
                    for k in unit_keys
                )
            ),
        },
        "limitations": [
            "Boundaries come from a 2009 PDF map fitted by affine transform; see boundary error.",
            "Wards 111 and 112 share one polygon (no dividing line in the PDF).",
            "Building weights are from 2016; Census households are from 2011.",
            "Six 2016 wards are missing from the DataMeet layer; shares there are lost.",
        ],
    }

    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=list(weight_rows[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(weight_rows)
    collection = {"type": "FeatureCollection", "features": features}
    return {
        WARDS: (json.dumps(collection, separators=(",", ":")) + "\n").encode(),
        SUMMARY: (json.dumps(summary, indent=2, sort_keys=True) + "\n").encode(),
        WEIGHTS: stream.getvalue().encode(),
    }


def weights_close(committed: bytes, fresh: bytes, tolerance: float = 0.002) -> bool:
    def rows(data: bytes) -> dict:
        return {
            (r["source_unit_2009"], r["target_ward_id"]): float(r["building_share"])
            for r in csv.DictReader(io.StringIO(data.decode()))
        }

    a, b = rows(committed), rows(fresh)
    keys = set(a) | set(b)
    return all(abs(a.get(k, 0.0) - b.get(k, 0.0)) <= tolerance for k in keys)


def geojson_close(committed: bytes, fresh: bytes, tolerance_deg: float = 1e-4) -> bool:
    a = json.loads(committed)["features"]
    b = json.loads(fresh)["features"]
    if [f["properties"] for f in a] != [f["properties"] for f in b]:
        return False
    return all(
        shape(fa["geometry"]).hausdorff_distance(shape(fb["geometry"])) <= tolerance_deg
        for fa, fb in zip(a, b, strict=True)
    )


def summary_close(committed: bytes, fresh: bytes) -> bool:
    a, b = json.loads(committed), json.loads(fresh)
    return (
        a["units"] == b["units"]
        and a["merged_units"] == b["merged_units"]
        and abs(a["fit"]["outline_iou"] - b["fit"]["outline_iou"]) <= 0.005
        and a["checks"]["census_district_false_inside"]
        == b["checks"]["census_district_false_inside"]
    )


if __name__ == "__main__":
    for name, content in build().items():
        path = ROOT / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    print("2009 ward map and 2009 -> 2016 crosswalk weights built.")
