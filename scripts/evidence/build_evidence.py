"""E2: reproducible historical ward evidence; never silently resolve ambiguous joins.

Census 2011 numbers GHMC wards by the 2009 delimitation, while the ward layer is the 2016
delimitation (renumbered and redrawn). Census values therefore move to 2016 wards by
location: each 2009 ward's households are split over the 2016 wards in proportion to its
buildings there (crosswalk from scripts/evidence/build_ward2009.py). Values are DERIVED and
approximate; per-ward Census coverage and the main 2009 source wards are reported.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

import openpyxl

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = "data/derived/evidence/ward_evidence.csv"
SUMMARY = "data/derived/evidence/evidence_summary.json"
CHECKS = "data/verification/evidence_checks.json"
INPUTS = [
    "data/derived/crosswalk/census_to_ghmc_2016.csv",
    "data/raw/geography/datameet/ghmc-wards.geojson",
    "data/raw/census/hyderabad/hh14.xlsx",
    "data/raw/census/rangareddy/hh14.xlsx",
    "data/verification/source_manifest.csv",
    "data/derived/crosswalk/ward2009_to_ghmc2016_weights.csv",
]
WARD2009_SUMMARY = "data/derived/ward2009/summary.json"
# Share of a 2016 ward's buildings that must come from 2009 wards with usable Census rows.
MIN_CENSUS_COVERAGE = 0.8
# Share of the estimated households a metric must cover to be reported.
MIN_METRIC_COVERAGE = 0.9
# Below this share from one 2009 ward, a 2016 ward is a mixture and is flagged for review.
MIXTURE_SHARE = 0.5
FAILURE_ORDER = ("HH14_AMBIGUOUS", "HH14_MISSING", "NO_CENSUS_ROW")
METRICS = [
    "population",
    "households",
    "wad",
    "non_tap_share",
    "cad",
    "one_room_or_less_share",
    "dilapidated_share",
    "no_assets_share",
    "hardship",
    "critical_facilities",
]


def percentage(value: object) -> float | None:
    """Missing, non-numeric and out-of-range percentages remain unknown."""
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (ValueError, TypeError):
        return None
    return number if math.isfinite(number) and 0 <= number <= 100 else None


def share(values: list[object], *, complement: bool = False) -> float | None:
    parts = [percentage(v) for v in values]
    if any(v is None for v in parts):
        return None
    total = sum(parts)
    # HH-14 values have two decimals; tolerate only component rounding.
    if total > 100 + 0.01 * len(parts) + 1e-9:
        return None
    total = min(total, 100)
    return round((100 - total if complement else total) / 100, 6)


def metrics(row: tuple) -> dict:
    result = {
        "wad": share([row[82], row[83]]),
        "non_tap_share": share([row[71], row[72]], complement=True),
        "cad": share([row[131], row[132], row[133]], complement=True),
        "one_room_or_less_share": share([row[48], row[49]]),
        "dilapidated_share": share([row[13]]),
        "no_assets_share": share([row[138]]),
    }
    components = [
        result[k] for k in ("one_room_or_less_share", "dilapidated_share", "no_assets_share")
    ]
    result["hardship"] = (
        round(sum(components) / 3, 6) if all(v is not None for v in components) else None
    )
    return result


def load_hh(path: Path, district: str) -> dict:
    book = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        rows = list(book.active.iter_rows(values_only=True))
    finally:
        book.close()
    if rows[5][13] != "Dilapidated":
        raise ValueError("HH-14 condition column changed")
    expected = {
        48: "No exclusive room",
        49: "One room",
        71: "Tapwater from treated source",
        81: "Within premises",
        82: "Near premises",
        83: "Away",
    }
    for index, label in expected.items():
        if rows[4][index] != label:
            raise ValueError(f"HH-14 header changed: {path.name}, column {index}")
    if rows[5][131:134] != ("Landline only", "Mobile only", "Both"):
        raise ValueError("HH-14 phone columns changed")
    if not str(rows[4][138]).startswith("None of the assets"):
        raise ValueError("HH-14 assets column changed")
    found = defaultdict(list)
    for row in rows[7:]:
        area = str(row[8] or "")
        ward = str(row[7] or "").strip()
        if (
            str(row[2]).strip() == district
            and ward.isdigit()
            and int(ward) > 0
            and "GHMC" in area
            and row[9] == "Urban"
        ):
            found[int(ward)].append(row)
    return found


def _read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def census_units(root: Path = ROOT, hh: dict | None = None) -> dict[int, dict]:
    """Census 2011 GHMC wards (2009 numbering) with counts. A ward fails if any of its rows
    has no single matching HH-14 record."""
    if hh is None:
        hh = {
            "Hyderabad": load_hh(root / INPUTS[2], "536"),
            "Rangareddy": load_hh(root / INPUTS[3], "537"),
        }
    units: dict[int, dict] = {}
    for source in _read_csv(root / INPUTS[0]):
        if "GHMC" not in source["source_name"] or not source["source_ward_num"].isdigit():
            continue
        number = int(source["source_ward_num"])
        unit = units.setdefault(
            number,
            {
                "status": "OK",
                "households": 0,
                "population": 0,
                "numerator": defaultdict(float),
                "denominator": defaultdict(float),
                "districts": set(),
                "source_url": source["source_url"],
            },
        )
        unit["districts"].add(source["source_district"])
        candidates = [
            r
            for r in hh.get(source["source_district"], {}).get(number, [])
            if str(r[4]).zfill(5) == source["source_subdistt_code"].zfill(5)
            and str(r[6]).zfill(6) == source["source_town_code"].zfill(6)
        ]
        if len(candidates) != 1:
            if unit["status"] == "OK":
                unit["status"] = "HH14_MISSING" if not candidates else "HH14_AMBIGUOUS"
            continue
        households = int(source["source_no_hh"]) if source["source_no_hh"].isdigit() else 0
        population = int(source["source_tot_p"]) if source["source_tot_p"].isdigit() else 0
        unit["households"] += households
        unit["population"] += population
        for key, value in metrics(candidates[0]).items():
            if value is not None:
                unit["numerator"][key] += value * households
                unit["denominator"][key] += households
    return units


def census_unit_totals(root: Path = ROOT) -> dict[str, int]:
    usable = [u for u in census_units(root).values() if u["status"] == "OK"]
    return {
        "households": sum(u["households"] for u in usable),
        "population": sum(u["population"] for u in usable),
    }


def _unit_for(key: str, units: dict[int, dict]) -> dict | None:
    """Combine the Census wards of one 2009 map unit ("111;112" is a single polygon)."""
    parts = [units.get(int(n)) for n in key.split(";")]
    if any(p is None for p in parts):
        return None
    combined = {
        "status": next((p["status"] for p in parts if p["status"] != "OK"), "OK"),
        "households": sum(p["households"] for p in parts),
        "population": sum(p["population"] for p in parts),
        "numerator": defaultdict(float),
        "denominator": defaultdict(float),
        "districts": set().union(*(p["districts"] for p in parts)),
        "source_url": parts[0]["source_url"],
    }
    for part in parts:
        for name, value in part["numerator"].items():
            combined["numerator"][name] += value
        for name, value in part["denominator"].items():
            combined["denominator"][name] += value
    return combined


def _estimate(row: dict, usable: list[tuple]) -> None:
    """Fill counts and shares for a 2016 ward from building-weighted 2009 Census wards."""
    households = sum(share * u["households"] for _k, share, _i, u in usable)
    population = sum(share * u["population"] for _k, share, _i, u in usable)
    parts = sorted(
        ((key, share * u["households"] / households) for key, share, _i, u in usable),
        key=lambda kv: (-kv[1], kv[0]),
    )
    districts = sorted(set().union(*(u["districts"] for *_x, u in usable)))
    row.update(
        source_district=";".join(districts),
        source_ward_code=";".join(key.replace(";", "+") for key, _ in parts),
        source_url=usable[0][3]["source_url"],
        dominant_source_share=f"{parts[0][1]:.4f}",
        source_units=";".join(f"{key.replace(';', '+')}:{value:.2f}" for key, value in parts[:6]),
        population=round(population),
        households=round(households),
    )
    for key in METRICS:
        if key in ("population", "households", "critical_facilities", "hardship"):
            continue
        covered = sum(share * u["denominator"][key] for _k, share, _i, u in usable)
        if households and covered / households >= MIN_METRIC_COVERAGE:
            numerator = sum(share * u["numerator"][key] for _k, share, _i, u in usable)
            row[key] = round(numerator / covered, 6)
    components = [
        row[k] for k in ("one_room_or_less_share", "dilapidated_share", "no_assets_share")
    ]
    if all(v is not None for v in components):
        row["hardship"] = round(sum(components) / 3, 6)
    for key in METRICS:
        if row[key] is not None:
            row[key + "_basis"] = "DERIVED"
    complete = all(row[k] is not None for k in METRICS if k != "critical_facilities")
    if not complete:
        row["quality_flags"] += ";INCOMPLETE_CENSUS"
    if parts[0][1] < MIXTURE_SHARE:
        row["quality_flags"] += ";MIXED_2009_SOURCES"
    row["allocation_eligible"] = complete
    row["review_required"] = not complete or parts[0][1] < MIXTURE_SHARE


def build(root: Path = ROOT) -> dict[str, bytes]:
    features = json.loads((root / INPUTS[1]).read_text(encoding="utf-8"))["features"]
    hh = {
        "Hyderabad": load_hh(root / INPUTS[2], "536"),
        "Rangareddy": load_hh(root / INPUTS[3], "537"),
    }
    units = census_units(root, hh)
    provenance = {r["file_path"]: r["source_url"] for r in _read_csv(root / INPUTS[4])}
    hh_url = {"Hyderabad": provenance[INPUTS[2]], "Rangareddy": provenance[INPUTS[3]]}
    pairs = defaultdict(list)
    for weight in _read_csv(root / INPUTS[5]):
        pairs[weight["target_ward_id"]].append(weight)

    output = []
    for feature in sorted(features, key=lambda f: f["properties"]["@id"]):
        properties = feature["properties"]
        target = properties["@id"]
        row = {
            "ward_id": target,
            "ward_name": properties["name"],
            "geo_version": "GHMC_2016_150",
            "census_year": 2011,
            "source_district": "",
            "source_ward_code": "",
            "source_url": "",
            "hh14_source_url": "",
            "join_status": "NO_CENSUS_ROW",
            "location_status": "NO_2009_OVERLAP",
            "review_required": True,
            "allocation_eligible": False,
            "quality_flags": "HISTORICAL;FACILITIES_UNAVAILABLE;APPROX_AREAL_CROSSWALK",
            "crosswalk_method": "BUILDING_WEIGHTED_2009_MAP",
            "census_coverage": "",
            "dominant_source_share": "",
            "source_units": "",
        }
        for key in METRICS:
            row[key], row[key + "_basis"] = None, "UNAVAILABLE"
        # (2009 unit, building share of that unit, building index here, Census unit or None)
        contributions = [
            (
                w["source_unit_2009"],
                float(w["building_share"]),
                float(w["building_index"]),
                _unit_for(w["source_unit_2009"], units),
            )
            for w in pairs[target]
        ]
        buildings = sum(c[2] for c in contributions)
        usable = [c for c in contributions if c[3] is not None and c[3]["status"] == "OK"]
        coverage = sum(c[2] for c in usable) / buildings if buildings else 0.0
        if contributions:
            row["location_status"] = "APPROXIMATE_2009_MAP"
            row["census_coverage"] = f"{coverage:.4f}"
        if coverage >= MIN_CENSUS_COVERAGE:
            row["join_status"] = "AREAL_2009_CROSSWALK"
            _estimate(row, usable)
            row["hh14_source_url"] = " | ".join(
                hh_url[d] for d in row["source_district"].split(";")
            )
        elif usable:
            row["join_status"] = "PARTIAL_CENSUS_COVERAGE"
        elif contributions:
            failed: dict[str, float] = defaultdict(float)
            for _key, _share, index, unit in contributions:
                failed["NO_CENSUS_ROW" if unit is None else unit["status"]] += index
            row["join_status"] = max(FAILURE_ORDER, key=lambda status: failed[status])
        output.append(row)

    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=list(output[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(output)
    ward2009 = json.loads((root / WARD2009_SUMMARY).read_text(encoding="utf-8"))
    summary = {
        "row_count": len(output),
        "join_status_counts": dict(sorted(Counter(r["join_status"] for r in output).items())),
        "allocation_eligible_count": sum(1 for r in output if r["allocation_eligible"]),
        "review_required_count": sum(1 for r in output if r["review_required"]),
        "current_ward_claim_blocked": True,
        "wad_non_tap_weight": None,
        "census_ward_numbering": "GHMC 2009 delimitation (not the 2016 ward numbers)",
        "crosswalk": {
            "method": "Census 2011 wards placed on the rebuilt 2009 ward map and split over "
            "2016 wards by Open Buildings 2016 building share",
            "median_boundary_error_m": ward2009["fit"]["median_boundary_error_m"],
            "census_district_agreement": ward2009["checks"]["census_district_agreement"],
            "same_name_largest_overlap_share": ward2009["checks"][
                "same_name_largest_overlap_share"
            ],
            "min_census_coverage": MIN_CENSUS_COVERAGE,
            "min_metric_coverage": MIN_METRIC_COVERAGE,
        },
        "limitations": [
            "Values are Census 2011 moved from 2009 wards to 2016 wards; approximate.",
            "The 2009 map is fitted from a PDF (median boundary error in crosswalk).",
            "2009 wards 115-116 were in Medak district; that Census table is not loaded.",
            "Census 2011 percentages are not current household observations.",
            "No verified facilities source; counts remain empty.",
            "Hardship is a mean of overlapping proxies, not a household union.",
            "Non-tap weight requires approved policy; no composite WAD invented.",
        ],
    }
    artifacts = {
        OUTPUT: stream.getvalue().encode(),
        SUMMARY: (json.dumps(summary, indent=2, sort_keys=True) + "\n").encode(),
    }
    text_inputs = (INPUTS[0], INPUTS[4], INPUTS[5])
    checks = {
        "inputs_sha256": {
            p: hashlib.sha256(
                (root / p).read_text(encoding="utf-8").encode("utf-8")
                if p in text_inputs
                else (root / p).read_bytes()
            ).hexdigest()
            for p in INPUTS
        },
        "outputs_sha256": {p: hashlib.sha256(b).hexdigest() for p, b in artifacts.items()},
        "schema_version": "E2-2",
        "normalized_lf_text_inputs": list(text_inputs),
    }
    artifacts[CHECKS] = (json.dumps(checks, indent=2, sort_keys=True) + "\n").encode()
    return artifacts


if __name__ == "__main__":
    for name, content in build().items():
        path = ROOT / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    print("E2 evidence built from the 2009 -> 2016 crosswalk; approximate values flagged.")
