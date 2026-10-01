"""E3 public raster extraction. Cache reduced model signals, never Census household estimates."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pyproj
import rasterio
from rasterio.enums import Resampling
from rasterio.features import geometry_mask
from rasterio.transform import Affine
from shapely.geometry import box, mapping, shape
from shapely.ops import transform, unary_union

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
from app.config.growth import GROWTH_CONFIG as CONFIG  # noqa: E402

CACHE = ROOT / "data/derived/growth_inputs"
GEOMETRY = ROOT / "data/raw/geography/datameet/ghmc-wards.geojson"
BASE = "https://storage.googleapis.com/open-buildings-temporal-data/"


def projected_targets():
    features = json.loads(GEOMETRY.read_text(encoding="utf-8"))["features"]
    transformer = pyproj.Transformer.from_crs(4326, 32644, always_xy=True)
    targets = {
        f["properties"]["@id"]: transform(transformer.transform, shape(f["geometry"]))
        for f in features
    }
    bounds = unary_union([shape(f["geometry"]) for f in features]).bounds
    if bounds[0] < 78 or bounds[2] >= 84:
        raise ValueError("This extractor is scoped to Hyderabad in UTM 44N; choose CRS explicitly")
    if any(not g.is_valid for g in targets.values()):
        raise ValueError("Invalid target polygons require review")
    return targets


def tiles_for_year(year, targets):
    url = BASE + f"v1/manifests/3b_EPSG_32644_{year}_06_30.json"
    path = CACHE / "manifests" / f"{year}.json.gz"
    if path.exists():
        manifest_bytes = gzip.decompress(path.read_bytes())
    else:
        path = CACHE / "manifests" / f"{year}.json"
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            with urllib.request.urlopen(url, timeout=CONFIG.network_timeout_seconds) as response:
                path.write_bytes(response.read())
        manifest_bytes = path.read_bytes()
    manifest = json.loads(manifest_bytes)
    if (
        manifest["startTime"][:4] != str(year)
        or manifest["bands"][0]["id"] != "building_fractional_count"
    ):
        raise ValueError("Unexpected manifest year/band")
    region = unary_union(list(targets.values()))
    result = []
    for tileset in manifest["tilesets"]:
        if tileset["crs"] != "EPSG:32644":
            raise ValueError("Unexpected manifest CRS")
        for source in tileset["sources"]:
            affine, size = source["affineTransform"], source["dimensions"]
            left, top = affine["translateX"], affine["translateY"]
            footprint = box(
                left,
                top + affine["scaleY"] * size["height"],
                left + affine["scaleX"] * size["width"],
                top,
            )
            if footprint.intersects(region):
                uri = manifest["uriPrefix"] + source["uris"][0]
                result.append(
                    (year, uri.replace("gs://", "https://storage.googleapis.com/"), footprint)
                )
    if not result:
        raise ValueError("No raster tiles intersect the historical target layer")
    return result


def cache_tile(job, grid):
    year, url, _ = job
    token = hashlib.sha256(url.encode()).hexdigest()[:16]
    name = f"{year}_{token}_{grid}m"
    path = CACHE / "tiles" / (name + ".npz")
    meta = path.with_suffix(".json")
    if path.exists() and meta.exists():
        return name
    with rasterio.Env(
        GDAL_HTTP_TIMEOUT=CONFIG.network_timeout_seconds,
        GDAL_HTTP_MAX_RETRY=1,
        GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR",
    ):
        with rasterio.open(url) as source:
            if source.crs.to_epsg() != 32644 or source.count != 3:
                raise ValueError("Unexpected source raster CRS/bands")
            height = math.ceil(source.height * abs(source.transform.e) / grid)
            width = math.ceil(source.width * abs(source.transform.a) / grid)
            values = source.read(
                1, out_shape=(height, width), resampling=Resampling.average, masked=True
            )
            affine = source.transform * Affine.scale(source.width / width, source.height / height)
            metadata = {
                "year": year,
                "url": url,
                "grid_metres_requested": grid,
                "transform": list(affine)[:6],
                "crs": "EPSG:32644",
                "native_pixels_per_cell": source.width * source.height / (width * height),
                "native_resolution_metres": abs(source.transform.a),
                "retrieved_at_utc": datetime.now(UTC).isoformat(),
                "source_band": "building_fractional_count",
                "basis": "DERIVED",
                "method": "COG overview/average reduction; comparative building index",
                "license": "CC BY 4.0",
                "geography_sha256": hashlib.sha256(GEOMETRY.read_bytes()).hexdigest(),
            }
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        path, values=np.ma.filled(values, 0).astype("float32"), valid=~np.ma.getmaskarray(values)
    )
    metadata["archive_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    meta.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return name


def reduce_archive(path, targets):
    meta = json.loads(path.with_suffix(".json").read_text(encoding="utf-8"))
    if hashlib.sha256(path.read_bytes()).hexdigest() != meta["archive_sha256"]:
        raise ValueError("Cached raster checksum differs")
    if meta["geography_sha256"] != hashlib.sha256(GEOMETRY.read_bytes()).hexdigest():
        raise ValueError("Cached raster geography changed; re-extract and review")
    affine = Affine(*meta["transform"])
    result = {}
    with np.load(path, allow_pickle=False) as archive:
        values, valid = archive["values"], archive["valid"]
        footprint = box(*rasterio.transform.array_bounds(*values.shape, affine))
        for ward, geometry in targets.items():
            if not footprint.intersects(geometry):
                continue
            inside = geometry_mask([mapping(geometry)], values.shape, affine, invert=True)
            available = inside & valid
            if np.any(~np.isfinite(values[available])) or np.any(values[available] < 0):
                raise ValueError("Invalid fractional model values")
            result[ward] = {
                "index": float(values[available].sum(dtype="float64"))
                * meta["native_pixels_per_cell"],
                "cells": int(inside.sum()),
                "valid_cells": int(available.sum()),
            }
    return result, footprint


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--years", nargs="+", type=int, default=list(CONFIG.years))
    parser.add_argument("--grid", type=int, default=CONFIG.grid_metres)
    args = parser.parse_args()
    if any(year not in CONFIG.years for year in args.years) or args.grid not in (16, 32, 64):
        parser.error("Use years 2016–2023 and grid 16, 32 or 64 metres")
    targets = projected_targets()
    jobs = [job for year in args.years for job in tiles_for_year(year, targets)]
    print(
        f"Extracting {len(jobs)} public tiles at {args.grid}m; successful caches are reused",
        flush=True,
    )
    failures = []
    with ThreadPoolExecutor(max_workers=CONFIG.network_workers) as executor:
        futures = {executor.submit(cache_tile, job, args.grid): job for job in jobs}
        for index, future in enumerate(as_completed(futures), 1):
            try:
                print(f"{index}/{len(jobs)} {future.result()}", flush=True)
            except Exception as exc:
                failures.append(f"{futures[future][0]} {futures[future][1]}: {exc}")
                print(f"{index}/{len(jobs)} FAILED: {exc}", flush=True)
    if failures:
        raise SystemExit(
            "Incomplete extraction; rerun to retry failed tiles:\n" + "\n".join(failures)
        )


if __name__ == "__main__":
    main()
