"""Reduce cached Open Buildings signals by historical polygon, without household projection."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import sys
from pathlib import Path

import numpy as np
from rasterio.features import geometry_mask
from rasterio.transform import Affine
from shapely.geometry import box, mapping
from shapely.ops import unary_union

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import fetch_growth  # noqa: E402

from app.config.growth import GROWTH_CONFIG as CONFIG  # noqa: E402

GEO = "data/raw/geography/datameet/ghmc-wards.geojson"
CROSSWALK = "data/derived/crosswalk/census_to_ghmc_2016.csv"
CACHE = ROOT / "data/derived/growth_inputs"
OUT = "data/derived/growth/"
YEARS = CONFIG.years


def csv_bytes(rows):
    stream = io.StringIO(newline="")
    if not rows:
        raise ValueError("Cannot serialize empty growth output")
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode()


def aggregate(root=ROOT):
    geometry_path = root / GEO
    features = json.loads(geometry_path.read_text(encoding="utf-8"))["features"]
    targets = fetch_growth.projected_targets()
    crosspath = root / CROSSWALK
    crosswalk = list(csv.DictReader(crosspath.open(encoding="utf-8", newline="")))
    by_target = {}
    for row in crosswalk:
        if row["target_ward_id"]:
            by_target.setdefault(row["target_ward_id"], []).append(row)
    per_year = {
        year: {
            ward: {"index": 0.0, "cells": 0, "valid_cells": 0, "footprints": []} for ward in targets
        }
        for year in YEARS
    }
    tile_list = []
    manifest_hashes = {}
    for year in YEARS:
        manifest_path = CACHE / "manifests" / f"{year}.json.gz"
        if manifest_path.is_file():
            import gzip

            manifest_bytes = gzip.decompress(manifest_path.read_bytes())
        else:
            manifest_path = CACHE / "manifests" / f"{year}.json"
            if not manifest_path.is_file():
                raise FileNotFoundError(
                    f"Missing Open Buildings manifest {year}; run fetch_growth.py"
                )
            manifest_bytes = manifest_path.read_bytes()
        manifest = json.loads(manifest_bytes)
        if manifest["bands"][0]["id"] != "building_fractional_count" or manifest["startTime"][
            :4
        ] != str(year):
            raise ValueError("Open Buildings manifest vintage/band mismatch")
        jobs = fetch_growth.tiles_for_year(year, targets)
        url_by_hash = {
            __import__("hashlib").sha256(url.encode()).hexdigest()[:16]: footprint
            for _, url, footprint in jobs
        }
        manifest_hashes[str(year)] = hashlib.sha256(manifest_bytes).hexdigest()
        for path in sorted((CACHE / "tiles").glob(f"{year}_*_{CONFIG.grid_metres}m.npz")):
            meta_path = path.with_suffix(".json")
            if not meta_path.is_file():
                raise ValueError(f"Missing tile provenance {path.name}")
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            token = path.name.split("_")[1]
            if token not in url_by_hash or meta["year"] != year:
                raise ValueError("Cached tile is absent from official annual manifest")
            if hashlib.sha256(path.read_bytes()).hexdigest() != meta["archive_sha256"]:
                raise ValueError(f"Tile archive checksum mismatch: {path.name}")
            if meta["grid_metres_requested"] != CONFIG.grid_metres or meta["crs"] != "EPSG:32644":
                raise ValueError("Cached tile grid/CRS mismatch")
            affine = Affine(*meta["transform"])
            with np.load(path, allow_pickle=False) as archive:
                values, valid = archive["values"], archive["valid"]
                if values.shape != valid.shape or values.ndim != 2:
                    raise ValueError("Cached raster arrays have inconsistent dimensions")
                footprint = url_by_hash[token]
                for ward, geom in targets.items():
                    if not footprint.intersects(geom):
                        continue
                    inside = geometry_mask([mapping(geom)], values.shape, affine, invert=True)
                    selected = inside & valid
                    sample = values[selected]
                    if np.any(~np.isfinite(sample)) or np.any(sample < 0):
                        raise ValueError("Invalid fractional-building values")
                    record = per_year[year][ward]
                    record["index"] += (
                        float(sample.sum(dtype="float64")) * meta["native_pixels_per_cell"]
                    )
                    record["cells"] += int(inside.sum())
                    record["valid_cells"] += int(selected.sum())
                    record["footprints"].append(footprint)
            tile_list.append(
                {
                    "year": year,
                    "tile": path.name,
                    "source_url": meta["url"],
                    "source_sha256": meta["archive_sha256"],
                    "source_band": meta["source_band"],
                    "grid_metres": CONFIG.grid_metres,
                    "basis": "DERIVED",
                }
            )
        present = {row["tile"] for row in tile_list if row["year"] == year}
        expected = {
            f"{year}_{hashlib.sha256(url.encode()).hexdigest()[:16]}_{CONFIG.grid_metres}m.npz"
            for _, url, _ in jobs
        }
        if present != expected:
            raise ValueError(
                f"Incomplete annual raster coverage for {year}: "
                f"{len(present)}/{len(expected)} tiles"
            )
    annual = []
    for feature in sorted(features, key=lambda f: f["properties"]["@id"]):
        ward = feature["properties"]["@id"]
        area = targets[ward].area
        cross = by_target.get(ward, [])
        census_status = (
            cross[0]["location_status"]
            if len(cross) == 1
            else "AMBIGUOUS_CROSSWALK"
            if len(cross) > 1
            else "NO_CROSSWALK"
        )
        for year in YEARS:
            record = per_year[year][ward]
            footprint = (
                unary_union(record["footprints"]) if record["footprints"] else box(0, 0, 0, 0)
            )
            area_coverage = (
                min(1.0, footprint.intersection(targets[ward]).area / area) if area else 0
            )
            valid_fraction = record["valid_cells"] / record["cells"] if record["cells"] else 0
            usable = (
                area_coverage >= CONFIG.minimum_coverage
                and valid_fraction >= CONFIG.minimum_coverage
                and record["index"] > 0
            )
            annual.append(
                {
                    "ward_id": ward,
                    "ward_name": feature["properties"]["name"],
                    "year": year,
                    "building_count_index": round(record["index"], 6) if usable else None,
                    "raster_footprint_coverage": round(area_coverage, 6),
                    "valid_grid_cell_fraction": round(valid_fraction, 6),
                    "grid_metres": CONFIG.grid_metres,
                    "source_band": "building_fractional_count",
                    "census_location_status": census_status,
                    "household_estimate": None,
                    "basis": "DERIVED" if usable else "UNAVAILABLE",
                    "quality_flag": "OK" if usable else "COVERAGE_OR_BASELINE_GATE",
                }
            )
    lookup = {(row["ward_id"], row["year"]): row for row in annual}
    growth = []
    for feature in sorted(features, key=lambda f: f["properties"]["@id"]):
        ward = feature["properties"]["@id"]
        start, end = lookup[(ward, YEARS[0])], lookup[(ward, YEARS[-1])]
        base, current = start["building_count_index"], end["building_count_index"]
        ratio = current / base if base and current is not None else None
        yearly = [lookup[(ward, y)]["building_count_index"] for y in YEARS]
        complete = all(v is not None for v in yearly)
        rates = (
            [
                math.log(yearly[i + 1] / yearly[i])
                for i in range(len(yearly) - 1)
                if yearly[i] and yearly[i + 1]
            ]
            if complete
            else []
        )
        mean = sum(rates) / len(rates) if rates else None
        cv = (
            math.sqrt(sum((x - mean) ** 2 for x in rates) / len(rates)) / abs(mean)
            if mean is not None and mean != 0
            else None
        )
        crows = by_target.get(ward, [])
        census_status = (
            crows[0]["location_status"]
            if len(crows) == 1
            else "AMBIGUOUS_CROSSWALK"
            if len(crows) > 1
            else "NO_CROSSWALK"
        )
        growth.append(
            {
                "ward_id": ward,
                "ward_name": feature["properties"]["name"],
                "period_start": YEARS[0],
                "period_end": YEARS[-1],
                "building_index_2016": base,
                "building_index_2023": current,
                "building_growth_ratio": round(ratio, 8) if ratio is not None else None,
                "annual_log_change_cv": round(cv, 8) if cv is not None else None,
                "growth_stability": (
                    "INSUFFICIENT_HISTORY"
                    if not complete
                    else "REVIEW_HIGH_VARIABILITY"
                    if cv is not None and cv >= 0.25
                    else "NO_HIGH_VARIABILITY_FLAG"
                    if cv is not None
                    else "UNCLASSIFIED_NEAR_ZERO_MEAN"
                ),
                "all_years_usable": complete,
                "grid_metres": CONFIG.grid_metres,
                "census_location_status": census_status,
                "census_households_2011": None,
                "adjusted_current_households": None,
                "booking_validation": "BLOCKED_NO_SECTION_WARD_CROSSWALK",
                "basis": "DERIVED" if ratio is not None else "UNAVAILABLE",
                "quality_flag": "BUILDING_SIGNAL_ONLY;NOT_HOUSEHOLDS"
                if ratio is not None
                else "INSUFFICIENT_COVERAGE",
            }
        )
    source_comparison = [
        {
            "source": "Google Open Buildings Temporal",
            "period": "2016-2023",
            "status": "EXTRACTED_DERIVED_BUILDING_SIGNAL",
            "geographic_unit": "historical ward polygon",
            "use": "urban building-change covariate only",
            "source_url": "https://developers.google.com/earth-engine/datasets/catalog/GOOGLE_Research_open-buildings-temporal_v1",
            "basis": "DERIVED",
        },
        {
            "source": "WorldPop India population raster",
            "period": "2016-2020 common-comparison candidate",
            "status": "NOT_EXTRACTED_RANGE_READ_UNSUPPORTED; 1.84 GB full download excluded",
            "geographic_unit": "modelled population grid",
            "use": "independent population sensitivity not ground truth",
            "source_url": "https://data.worldpop.org/GIS/Population/Global_2000_2020/2020/IND/ind_ppp_2020.tif",
            "basis": "UNAVAILABLE",
        },
        {
            "source": "GHS-POP R2023A",
            "period": "five-year epochs, includes modelled 2025 projection",
            "status": "NOT_EXTRACTED_DIFFERING_EPOCHS_AND_GRID",
            "geographic_unit": "modelled population grid",
            "use": "independent population sensitivity, incomparable without harmonization",
            "source_url": "https://human-settlement.emergency.copernicus.eu/ghs_pop2023.php",
            "basis": "UNAVAILABLE",
        },
    ]
    growth_values = [
        r["building_growth_ratio"] for r in growth if r["building_growth_ratio"] is not None
    ]
    summary = {
        "row_count": len(growth),
        "polygon_count": len(features),
        "validated_census_joins": 0,
        "usable_growth_ratios": len(growth_values),
        "high_variability_review_flags": sum(
            row["growth_stability"] == "REVIEW_HIGH_VARIABILITY" for row in growth
        ),
        "variability_review_threshold": {
            "metric": "coefficient_of_variation_of_annual_log_growth",
            "threshold": 0.25,
            "status": "ENGINEERING_REVIEW_HEURISTIC_NOT_VALIDATED_QUALITY_BOUND",
        },
        "unclassified_stability_polygons": sum(
            row["growth_stability"] == "UNCLASSIFIED_NEAR_ZERO_MEAN" for row in growth
        ),
        "period": "2016-2023",
        "grid_metres": CONFIG.grid_metres,
        "source": "Google Open Buildings Temporal V1",
        "source_band": "building_fractional_count",
        "aggregation": (
            "32m average fractional count multiplied by native source-pixel area factor; "
            "approximate index"
        ),
        "interpretation": "Building-change signal; buildings are not households or population",
        "median_building_growth_ratio": round(float(np.median(growth_values)), 8)
        if growth_values
        else None,
        "growth_ratio_p10": round(float(np.quantile(growth_values, 0.1)), 8)
        if growth_values
        else None,
        "growth_ratio_p90": round(float(np.quantile(growth_values, 0.9)), 8)
        if growth_values
        else None,
        "booking_validation": "BLOCKED_NO_VERIFIED_SECTION_TO_WARD_CROSSWALK_AND_NO_2016_BOOKINGS",
        "population_projection": "BLOCKED; no current household estimate is computed",
        "boundary_vintage": (
            "Unverified historical 150-ward DataMeet layer; not current GHMC geography"
        ),
        "multi_source_growth_range": None,
        "limitations": [
            "Only 145 polygon features; layer is an incomplete historical 150-ward scheme.",
            "E1 has zero location-validated Census-to-polygon assignments.",
            (
                "Open Buildings confidence is uncalibrated; Google documents positional/temporal "
                "jitter, tile seams, and missed small buildings."
            ),
            (
                "32m aggregation bounds extraction; compare 16m/64m before treating small "
                "ranking differences as stable."
            ),
            (
                "WorldPop's India raster host does not support range reads; the 1.84GB file "
                "was not downloaded."
            ),
            (
                "GHS-POP grid epochs differ from 2016-2023; no multi-source agreement score "
                "is reported."
            ),
            (
                "Ward-level booking validation lacks an authoritative crosswalk; tanker data "
                "begins in 2022."
            ),
        ],
        "comparison_sources": source_comparison,
    }
    return {
        OUT + "annual.csv": csv_bytes(annual),
        OUT + "growth.csv": csv_bytes(growth),
        OUT + "source_comparison.csv": csv_bytes(source_comparison),
        OUT + "summary.json": (json.dumps(summary, indent=2, sort_keys=True) + "\n").encode(),
        "data/verification/growth_checks.json": build_checks(
            root, annual, growth, manifest_hashes, tile_list
        ),
    }


def build_checks(root, annual, growth, manifest_hashes, tile_list):
    return (
        json.dumps(
            {
                "schema_version": "E3-1",
                "geography_sha256": hashlib.sha256((root / GEO).read_bytes()).hexdigest(),
                "crosswalk_sha256_lf": hashlib.sha256(
                    (root / CROSSWALK).read_text(encoding="utf-8").encode()
                ).hexdigest(),
                "manifest_sha256": manifest_hashes,
                "tile_archives": sorted(tile_list, key=lambda r: r["tile"]),
                "output_sha256": {},
            },
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode()


def main():
    artifacts = aggregate()
    checks = json.loads(artifacts["data/verification/growth_checks.json"])
    checks["output_sha256"] = {
        path: hashlib.sha256(value).hexdigest()
        for path, value in artifacts.items()
        if path.startswith(OUT)
    }
    artifacts["data/verification/growth_checks.json"] = (
        json.dumps(checks, indent=2, sort_keys=True) + "\n"
    ).encode()
    for relative, content in artifacts.items():
        path = ROOT / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    print(
        "E3 built 145 growth rows from 80 verified 2016-2023 tile caches",
        flush=True,
    )


if __name__ == "__main__":
    main()
