"""Reduce cached Open Buildings signals by historical polygon, without household projection.

Stability: Open Buildings counts jump city-wide from year to year (Google: "building count over
an area could also be unstable ... due to cloud cover, misalignment between input images and
fewer Sentinel-2 timeframes for years 2016-2017"). The shared shock of each year (median ward
log change, minus the city's own linear trend) is removed; each ward's remaining log series is
fitted with a line and is STABLE_TREND when its slope is >= minimum_trend_t standard errors.

Census values come from E2 (Census 2011 placed on 2016 wards through the rebuilt 2009 ward
map). Independent check (F2): ward building trend vs HMWSSB domestic connection growth
2022 -> 2025, with sections placed on wards (data/derived/crosswalk/section_to_ward_2016.csv).
Growth stays a covariate; no household projection is made.
"""

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
EVIDENCE = "data/derived/evidence/ward_evidence.csv"
SECTION_WARDS = "data/derived/crosswalk/section_to_ward_2016.csv"
BILLING = "data/raw/hmwssb_billing_portal"
CONNECTION_YEARS = (2022, 2025)  # whole years before the Feb/Mar 2026 section re-cut
MIN_BASE_CONNECTIONS = 500  # smaller ward totals give unstable growth ratios
# Domestic connection categories (HMWSSB billing legend), as in E4.
DOMESTIC_CATEGORIES = ("D", "DS", "DM", "DP", "M0", "M1", "M4", "MB")
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


def year_shocks(series):
    """Shared shock per year: cumulative median ward log change minus its own linear trend."""
    years = len(next(iter(series.values())))
    effect = [0.0] + [
        float(np.median([s[i] - s[i - 1] for s in series.values()])) for i in range(1, years)
    ]
    cumulative = np.cumsum(effect)
    x = np.arange(years) - (years - 1) / 2
    slope = float((x * (cumulative - cumulative.mean())).sum() / (x * x).sum())
    shocks = cumulative - (cumulative.mean() + slope * x)
    return [float(v) for v in shocks], slope


def trend(values):
    """Least-squares slope of a log series and its t statistic."""
    y = np.asarray(values, dtype=float)
    x = np.arange(len(y)) - (len(y) - 1) / 2
    slope = float((x * (y - y.mean())).sum() / (x * x).sum())
    residual = y - (y.mean() + slope * x)
    sd = math.sqrt(float((residual * residual).sum()) / (len(y) - 2))
    t = slope / (sd / math.sqrt(float((x * x).sum()))) if sd > 0 else math.inf
    return slope, t


def spearman(a, b):
    def ranks(values):
        order = sorted(range(len(values)), key=lambda i: values[i])
        out = [0.0] * len(values)
        i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
                j += 1
            for k in range(i, j + 1):
                out[order[k]] = (i + j) / 2
            i = j + 1
        return np.asarray(out)

    ra, rb = ranks(a), ranks(b)
    ra, rb = ra - ra.mean(), rb - rb.mean()
    return float((ra * rb).sum() / math.sqrt(float((ra * ra).sum() * (rb * rb).sum())))


def connection_growth(root):
    """Ward growth of mean monthly domestic HMWSSB connections between CONNECTION_YEARS."""
    with (root / SECTION_WARDS).open(encoding="utf-8", newline="") as handle:
        links = {r["section"]: r["ward_id"] for r in csv.DictReader(handle) if r["ward_id"]}
    means = {}
    paths = []
    for year in CONNECTION_YEARS:
        totals, months = {}, 0
        for path in sorted((root / BILLING).glob(f"{year}-*.csv")):
            months += 1
            paths.append(path)
            with path.open(encoding="utf-8-sig", newline="") as handle:
                for row in csv.DictReader(handle):
                    ward = links.get((row["section"] or "").strip())
                    if ward and row["category"] in DOMESTIC_CATEGORIES:
                        totals[ward] = totals.get(ward, 0.0) + float(row["noofcans"] or 0)
        means[year] = {w: v / months for w, v in totals.items()} if months else {}
    first, last = (means[y] for y in CONNECTION_YEARS)
    growth = {
        w: last[w] / first[w] - 1 for w in first if w in last and first[w] >= MIN_BASE_CONNECTIONS
    }
    return growth, set(links.values()), paths


def aggregate(root=ROOT):
    geometry_path = root / GEO
    features = json.loads(geometry_path.read_text(encoding="utf-8"))["features"]
    targets = fetch_growth.projected_targets()
    with (root / EVIDENCE).open(encoding="utf-8", newline="") as handle:
        evidence = {row["ward_id"]: row for row in csv.DictReader(handle)}
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
        census_status = evidence.get(ward, {}).get("location_status", "NO_E2_ROW")
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
    complete_logs = {}
    for feature in features:
        ward = feature["properties"]["@id"]
        yearly = [lookup[(ward, y)]["building_count_index"] for y in YEARS]
        if all(v for v in yearly):
            complete_logs[ward] = [math.log(v) for v in yearly]
    shocks, city_slope = year_shocks(complete_logs)
    connections, placed_wards, billing_paths = connection_growth(root)
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
        census_status = evidence.get(ward, {}).get("location_status", "NO_E2_ROW")
        if ward in complete_logs:
            slope, t = trend([v - s for v, s in zip(complete_logs[ward], shocks, strict=True)])
            stability = "STABLE_TREND" if t >= CONFIG.minimum_trend_t else "REVIEW_NOISY_TREND"
        else:
            slope, t, stability = None, None, "INSUFFICIENT_HISTORY"
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
                "adjusted_annual_growth": round(math.exp(slope) - 1, 6)
                if slope is not None
                else None,
                "trend_t": round(t, 4) if t is not None and math.isfinite(t) else None,
                "growth_stability": stability,
                "all_years_usable": complete,
                "grid_metres": CONFIG.grid_metres,
                "census_location_status": census_status,
                "census_households_2011": evidence.get(ward, {}).get("households") or None,
                "adjusted_current_households": None,
                "connection_growth_2022_2025": round(connections[ward], 6)
                if ward in connections
                else None,
                "booking_validation": "APPROXIMATE_SECTION_POINT_IN_WARD"
                if ward in placed_wards
                else "NO_PLACED_SECTION",
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
        "approximate_census_joins": sum(
            r["location_status"] == "APPROXIMATE_2009_MAP" and r["allocation_eligible"] == "True"
            for r in evidence.values()
        ),
        "exact_geometry_census_joins": sum(
            r["location_status"] == "VERIFIED_EXACT_GEOMETRY" for r in evidence.values()
        ),
        "usable_growth_ratios": len(growth_values),
        "noisy_trend_review_flags": sum(
            row["growth_stability"] == "REVIEW_NOISY_TREND" for row in growth
        ),
        "stability": {
            "method": (
                "remove city-wide year shocks (cumulative median ward log change minus its "
                "linear trend), then least-squares trend per ward; STABLE_TREND if t >= "
                "minimum_trend_t"
            ),
            "minimum_trend_t": CONFIG.minimum_trend_t,
            "city_year_shocks_log": [round(s, 6) for s in shocks],
            "city_trend_annual_growth": round(math.exp(city_slope) - 1, 6),
            "replaced": "CV of annual log change >= 0.25 (flagged all 145 wards)",
            "source_note": (
                "Google Open Buildings Temporal: aggregates like building count can be unstable "
                "(cloud cover, image misalignment, fewer Sentinel-2 frames in 2016-2017)"
            ),
        },
        "independent_checks": {
            "connection_growth": {
                "description": (
                    "Spearman rank correlation, ward adjusted building trend vs growth of mean "
                    "monthly HMWSSB domestic connections 2022 -> 2025 (sections placed on wards)"
                ),
                "wards": sum(
                    1
                    for row in growth
                    if row["connection_growth_2022_2025"] is not None
                    and row["adjusted_annual_growth"] is not None
                ),
                "spearman": round(
                    spearman(
                        [
                            row["adjusted_annual_growth"]
                            for row in growth
                            if row["connection_growth_2022_2025"] is not None
                            and row["adjusted_annual_growth"] is not None
                        ],
                        [
                            row["connection_growth_2022_2025"]
                            for row in growth
                            if row["connection_growth_2022_2025"] is not None
                            and row["adjusted_annual_growth"] is not None
                        ],
                    ),
                    4,
                ),
                "basis": "DERIVED (REAL billing counts, approximate section placement)",
            }
        },
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
        "booking_validation": (
            "APPROXIMATE_SECTION_POINT_IN_WARD; checked against HMWSSB connection growth "
            "(independent_checks); tanker and billing data begin in 2022"
        ),
        "population_projection": "BLOCKED; no current household estimate is computed",
        "boundary_vintage": (
            "Unverified historical 150-ward DataMeet layer; not current GHMC geography"
        ),
        "multi_source_growth_range": None,
        "limitations": [
            "Only 145 polygon features; layer is an incomplete historical 150-ward scheme.",
            (
                "Census placement is approximate (E2: Census 2011 via the rebuilt 2009 ward map); "
                "no exact-geometry join exists."
            ),
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
                "The connection check uses approximate section placement (about 80% of bookings) "
                "and 2022-2025, a later period than the 2016-2023 building trend."
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
            root, annual, growth, manifest_hashes, tile_list, billing_paths
        ),
    }


def build_checks(root, annual, growth, manifest_hashes, tile_list, billing_paths):
    return (
        json.dumps(
            {
                "schema_version": "E3-2",
                "geography_sha256": hashlib.sha256((root / GEO).read_bytes()).hexdigest(),
                "evidence_sha256_lf": hashlib.sha256(
                    (root / EVIDENCE).read_text(encoding="utf-8").encode()
                ).hexdigest(),
                "section_wards_sha256_lf": hashlib.sha256(
                    (root / SECTION_WARDS).read_text(encoding="utf-8").encode()
                ).hexdigest(),
                "billing_sha256": {
                    str(p.relative_to(root)).replace("\\", "/"): hashlib.sha256(
                        p.read_bytes()
                    ).hexdigest()
                    for p in billing_paths
                },
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
