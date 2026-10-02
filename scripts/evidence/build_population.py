"""2025 population and households per 2016 ward (modelled estimate with a range).

Census 2011 (E2) is the only observed ward count. Three estimates carry it to 2025:
  A  buildings:   Census 2011 x exp(14 x ward building trend)        (E3, Open Buildings)
  B  GHS-POP:     GHS-POP R2023A 2025 cells inside the ward          (EU JRC, modelled level)
  C  GHS growth:  Census 2011 x (GHS-POP 2025 / 2015)^(14/10)        (EU JRC, modelled growth)
City-wide they bracket the truth: buildings over-state residential growth (offices, malls,
~3.2%/yr) and GHS-POP spreads national growth (~1.2%/yr). Ward by ward, only the building
pattern predicts HMWSSB's own domestic-connection growth (Spearman ~0.5; GHS-POP ~0.04, as it
gives almost every ward +11-15%). So the central estimate uses the building growth pattern,
shifted so the whole city grows at the REAL HMWSSB connection rate (billing data, 2022 ->
2025); GHS-POP enters the level check and the range. Households = central / 2011 household
size (ASSUMED constant). Every ward keeps low-high = min-max of A, B, C and central.
"""

from __future__ import annotations

import csv
import glob
import hashlib
import io
import json
import math
import sys
from pathlib import Path

import numpy as np
import rasterio
import shapely
from shapely.geometry import shape

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_growth import spearman  # noqa: E402

WARDS = "data/raw/geography/datameet/ghmc-wards.geojson"
EVIDENCE = "data/derived/evidence/ward_evidence.csv"
GROWTH = "data/derived/growth/growth.csv"
GHS = "data/derived/population_inputs/ghs_pop_{year}_ghmc.tif"
BILLING = "data/raw/hmwssb_billing_portal"
OUTPUT = "data/derived/population/ward_population_2025.csv"
SUMMARY = "data/derived/population/summary.json"
CHECKS = "data/verification/population_checks.json"

YEARS_SINCE_CENSUS = 14  # 2011 -> 2025
GHS_SPAN = 10  # 2015 -> 2025
CONNECTION_YEARS = (2022, 2025)
DOMESTIC_CATEGORIES = ("D", "DS", "DM", "DP", "M0", "M1", "M4", "MB")
# A ward's range (high - low) / central above this is flagged for review. Basis: ASSUMED.
WIDE_RANGE = 0.6


def _rows(root: Path, relative: str) -> dict[str, dict[str, str]]:
    with (root / relative).open(encoding="utf-8", newline="") as handle:
        return {r["ward_id"]: r for r in csv.DictReader(handle)}


def ghs_ward_sums(root: Path, year: int, wards: dict) -> dict[str, float]:
    with rasterio.open(root / GHS.format(year=year)) as src:
        values = src.read(1).astype(float)
        nodata = src.nodata
        t = src.transform
    values = np.where((values != nodata) & (values > 0), values, 0.0)
    rows, cols = np.nonzero(values)
    xs, ys, vs = t.c + (cols + 0.5) * t.a, t.f + (rows + 0.5) * t.e, values[rows, cols]
    sums = {}
    for ward_id, geom in wards.items():
        x0, y0, x1, y1 = geom.bounds
        box = (xs >= x0) & (xs <= x1) & (ys >= y0) & (ys <= y1)
        inside = shapely.contains_xy(geom, xs[box], ys[box])
        sums[ward_id] = float(vs[box][inside].sum())
    return sums


def connection_growth_rate(root: Path) -> tuple[float, list[Path]]:
    """Annual growth of mean monthly HMWSSB domestic connections, whole city."""
    means, paths = {}, []
    for year in CONNECTION_YEARS:
        files = sorted(glob.glob(str(root / BILLING / f"{year}-*.csv")))
        total = 0.0
        for name in files:
            paths.append(Path(name))
            with open(name, encoding="utf-8-sig", newline="") as handle:
                total += sum(
                    float(r["noofcans"] or 0)
                    for r in csv.DictReader(handle)
                    if r["category"] in DOMESTIC_CATEGORIES
                )
        means[year] = total / len(files)
    span = CONNECTION_YEARS[1] - CONNECTION_YEARS[0]
    return (means[CONNECTION_YEARS[1]] / means[CONNECTION_YEARS[0]]) ** (1 / span) - 1, paths


def build(root: Path = ROOT) -> dict[str, bytes]:
    features = json.loads((root / WARDS).read_text(encoding="utf-8-sig"))["features"]
    wards = {f["properties"]["@id"]: shape(f["geometry"]) for f in features}
    names = {f["properties"]["@id"]: f["properties"]["name"] for f in features}
    evidence, growth = _rows(root, EVIDENCE), _rows(root, GROWTH)
    ghs15, ghs25 = ghs_ward_sums(root, 2015, wards), ghs_ward_sums(root, 2025, wards)
    rate, billing_paths = connection_growth_rate(root)
    t = YEARS_SINCE_CENSUS

    base: dict[str, dict] = {}
    for ward_id in sorted(wards):
        e2, e3 = evidence.get(ward_id, {}), growth.get(ward_id, {})
        if not (e2.get("population") and e2.get("households") and e3.get("adjusted_annual_growth")):
            continue
        if ghs15[ward_id] <= 0 or ghs25[ward_id] <= 0:
            continue
        g_buildings = math.log1p(float(e3["adjusted_annual_growth"]))
        g_ghs = math.log(ghs25[ward_id] / ghs15[ward_id]) / GHS_SPAN
        base[ward_id] = {
            "p11": float(e2["population"]),
            "h11": float(e2["households"]),
            "g_buildings": g_buildings,
            "g_ghs": g_ghs,
        }
    census_total = sum(b["p11"] for b in base.values())
    target = census_total * (1 + rate) ** t
    raw = sum(b["p11"] * math.exp(t * b["g_buildings"]) for b in base.values())
    shift = math.log(target / raw) / t

    out = []
    for ward_id in sorted(wards):
        row = {
            "ward_id": ward_id,
            "ward_name": names[ward_id],
            "census_population_2011": evidence.get(ward_id, {}).get("population") or None,
            "census_households_2011": evidence.get(ward_id, {}).get("households") or None,
            "household_size_2011": None,
            "building_annual_growth": None,
            "ghs_pop_2015": round(ghs15[ward_id]),
            "ghs_pop_2025": round(ghs25[ward_id]),
            "estimate_buildings_2025": None,
            "estimate_ghs_growth_2025": None,
            "population_2025_central": None,
            "population_2025_low": None,
            "population_2025_high": None,
            "range_spread": None,
            "households_2025_central": None,
            "central_annual_growth": None,
            "review_flag": "NO_CENSUS_BASE",
            "basis": "UNAVAILABLE",
        }
        b = base.get(ward_id)
        if b:
            a = b["p11"] * math.exp(t * b["g_buildings"])
            c = b["p11"] * math.exp(t * b["g_ghs"])
            growth_rate = b["g_buildings"] + shift
            central = b["p11"] * math.exp(t * growth_rate)
            values = (a, ghs25[ward_id], c, central)
            low, high = min(values), max(values)
            spread = (high - low) / central
            size = b["p11"] / b["h11"]
            row.update(
                household_size_2011=round(size, 6),
                building_annual_growth=round(math.expm1(b["g_buildings"]), 6),
                estimate_buildings_2025=round(a),
                estimate_ghs_growth_2025=round(c),
                population_2025_central=round(central),
                population_2025_low=round(low),
                population_2025_high=round(high),
                range_spread=round(spread, 6),
                households_2025_central=round(round(central) / size, 3),
                central_annual_growth=round(math.expm1(growth_rate), 6),
                review_flag="WIDE_RANGE" if spread > WIDE_RANGE else "OK",
                basis="MODELLED_ESTIMATE",
            )
        out.append(row)

    est = [r for r in out if r["population_2025_central"] is not None]
    connected = [r for r in est if growth.get(r["ward_id"], {}).get("connection_growth_2022_2025")]
    conn = [float(growth[r["ward_id"]]["connection_growth_2022_2025"]) for r in connected]
    connection_pairs = [
        (
            float(r["central_annual_growth"]),
            float(growth[r["ward_id"]]["connection_growth_2022_2025"]),
        )
        for r in est
        if growth.get(r["ward_id"], {}).get("connection_growth_2022_2025")
    ]
    summary = {
        "wards_estimated": len(est),
        "city": {
            "census_2011": round(census_total),
            "buildings_2025": round(sum(r["estimate_buildings_2025"] for r in est)),
            "ghs_level_2025": round(sum(r["ghs_pop_2025"] for r in est)),
            "ghs_growth_2025": round(sum(r["estimate_ghs_growth_2025"] for r in est)),
            "central_2025": round(sum(r["population_2025_central"] for r in est)),
            "connection_growth_annual": round(rate, 6),
            "households_2025_central": round(sum(r["households_2025_central"] for r in est)),
        },
        "checks": {
            "buildings_vs_connections_spearman": round(
                spearman([base[r["ward_id"]]["g_buildings"] for r in connected], conn), 4
            ),
            "ghs_growth_vs_connections_spearman": round(
                spearman([base[r["ward_id"]]["g_ghs"] for r in connected], conn), 4
            ),
            "central_pattern": "BUILDINGS",
            "buildings_vs_ghs_growth_spearman": round(
                spearman(
                    [b["g_buildings"] for b in base.values()], [b["g_ghs"] for b in base.values()]
                ),
                4,
            ),
            "central_vs_connection_growth": {
                "wards": len(connection_pairs),
                "spearman": round(spearman(*map(list, zip(*connection_pairs, strict=True))), 4)
                if connection_pairs
                else None,
            },
        },
        "wide_range_wards": sum(r["review_flag"] == "WIDE_RANGE" for r in est),
        "method": (
            "central = Census 2011 x exp(14 x (ward building log growth + city shift)), shift set "
            "so the city grows at the HMWSSB domestic-connection rate; GHS-POP in range only"
        ),
        "sources": {
            "census": "Census 2011 via E2 (2009 to 2016 ward crosswalk)",
            "buildings": "Open Buildings Temporal via E3 (year shocks removed)",
            "ghs_pop": "GHS-POP R2023A 3 arc-second, EU JRC, CC BY 4.0",
            "connections": "HMWSSB billing and collection data (Telangana portal, GODL)",
        },
        "limitations": [
            "Modelled estimate, not a count; use the low-high range, not only the central value.",
            "The connection growth rate (2022-2025) is assumed to hold since 2011.",
            "Household size is held at its 2011 value; falling household size would mean more "
            "households than shown.",
            "One HMWSSB connection can serve many flats, so connection growth may understate "
            "household growth in apartment areas.",
        ],
    }
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=list(out[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(out)
    artifacts = {
        OUTPUT: stream.getvalue().encode(),
        SUMMARY: (json.dumps(summary, indent=2, sort_keys=True) + "\n").encode(),
    }
    checks = {
        "inputs_sha256": {
            **{
                p: hashlib.sha256((root / p).read_text(encoding="utf-8").encode()).hexdigest()
                for p in (EVIDENCE, GROWTH)
            },
            **{
                GHS.format(year=y): hashlib.sha256(
                    (root / GHS.format(year=y)).read_bytes()
                ).hexdigest()
                for y in (2015, 2025)
            },
            **{
                str(p.relative_to(root)).replace("\\", "/"): hashlib.sha256(
                    p.read_bytes()
                ).hexdigest()
                for p in billing_paths
            },
        },
        "outputs_sha256": {p: hashlib.sha256(c).hexdigest() for p, c in artifacts.items()},
    }
    artifacts[CHECKS] = (json.dumps(checks, indent=2, sort_keys=True) + "\n").encode()
    return artifacts


if __name__ == "__main__":
    for name, content in build().items():
        path = ROOT / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    print("2025 ward population estimates built.")
