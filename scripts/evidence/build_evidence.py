"""E2: reproducible historical ward evidence; never silently resolve ambiguous joins."""

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
]
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


def build(root: Path = ROOT) -> dict[str, bytes]:
    with (root / INPUTS[0]).open(encoding="utf-8", newline="") as handle:
        crosswalk = list(csv.DictReader(handle))
    features = json.loads((root / INPUTS[1]).read_text(encoding="utf-8"))["features"]
    hh = {
        "Hyderabad": load_hh(root / INPUTS[2], "536"),
        "Rangareddy": load_hh(root / INPUTS[3], "537"),
    }
    by_target = defaultdict(list)
    for source in crosswalk:
        if source["target_ward_id"]:
            by_target[source["target_ward_id"]].append(source)
    with (root / INPUTS[4]).open(encoding="utf-8", newline="") as handle:
        provenance = {r["file_path"]: r["source_url"] for r in csv.DictReader(handle)}
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
            "join_status": "NO_CROSSWALK",
            "review_required": True,
            "allocation_eligible": False,
            "quality_flags": "HISTORICAL;FACILITIES_UNAVAILABLE",
        }
        for key in METRICS:
            row[key], row[key + "_basis"] = None, "UNAVAILABLE"
        sources = by_target[target]
        if len(sources) > 1:
            row["join_status"] = "AMBIGUOUS_CROSSWALK"
        elif len(sources) == 1:
            source = sources[0]
            row.update(
                source_district=source["source_district"],
                source_ward_code=source["source_ward_code"],
                source_url=source["source_url"],
            )
            hh_path = INPUTS[2] if source["source_district"] == "Hyderabad" else INPUTS[3]
            row["hh14_source_url"] = provenance[hh_path]
            candidates = hh.get(source["source_district"], {}).get(
                int(source["source_ward_num"]), []
            )
            row["join_status"] = "HH14_MISSING" if not candidates else "HH14_AMBIGUOUS"
            if len(candidates) == 1:
                row["join_status"] = "PROVISIONAL_NUMBER_ONLY"
                row["quality_flags"] += ";LOCATION_UNVERIFIED"
                row.update(metrics(candidates[0]))
                for key, field in (("population", "source_tot_p"), ("households", "source_no_hh")):
                    value = source[field]
                    row[key] = int(value) if value.isdigit() else None
                for key in METRICS:
                    if row[key] is not None:
                        row[key + "_basis"] = "DERIVED"
                if any(row[k] is None for k in METRICS if k != "critical_facilities"):
                    row["quality_flags"] += ";INCOMPLETE_CENSUS"
        output.append(row)
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=list(output[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(output)
    summary = {
        "row_count": len(output),
        "join_status_counts": dict(sorted(Counter(r["join_status"] for r in output).items())),
        "allocation_eligible_count": 0,
        "current_ward_claim_blocked": True,
        "wad_non_tap_weight": None,
        "limitations": [
            "Number-only E1 mappings lack location validation; review all joins.",
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
    checks = {
        "inputs_sha256": {
            p: hashlib.sha256(
                (root / p).read_text(encoding="utf-8").encode("utf-8")
                if p in (INPUTS[0], INPUTS[4])
                else (root / p).read_bytes()
            ).hexdigest()
            for p in INPUTS
        },
        "outputs_sha256": {p: hashlib.sha256(b).hexdigest() for p, b in artifacts.items()},
        "schema_version": "E2-1",
        "normalized_lf_text_inputs": [INPUTS[0], INPUTS[4]],
    }
    artifacts[CHECKS] = (json.dumps(checks, indent=2, sort_keys=True) + "\n").encode()
    return artifacts


if __name__ == "__main__":
    for name, content in build().items():
        path = ROOT / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    print("E2 evidence built; provisional joins require review.")
