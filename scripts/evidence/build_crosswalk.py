"""E1 build_crosswalk.py: Census 2011 to GHMC_2016_150 ward crosswalk.

Source geographies
------------------
  Census 2011 Hyderabad district  (108 ward rows, 16 mandals)
    - 99 GHMC ward rows (wards 18..150)
    - 8 Secunderabad Cantonment Board rows (non-GHMC, retained unmatched)
    - 1 Osmania University Census Town row (non-GHMC, retained unmatched)
  Census 2011 Rangareddy district (54 GHMC ward rows in Rangareddy town)
    - GHMC wards (1..17, 57..60, 101, 111..139, 148)

Target geography
----------------
  GHMC_2016_150: 150-ward historical DataMeet/OSM layer.
  Available DataMeet file contains 145 polygon features.
  Wards 3, 4, 11, 13, 31, and 113 are known missing polygons and must never be false-matched.

Important rules & acceptance criteria (docs/features.csv E1)
------------------------------------------------------------
  1. Coverage reported (> 85% for GHMC wards).
  2. Wards 104 and 107 are NEVER matched:
     Census 2011 Ward 104/107 in Shaikpet mandal conflicts geographically with
     GHMC 2016 Ward 104 (Kondapur) and Ward 107 (Madhapur) in Serilingampally circle.
  3. Historical geography frozen at GHMC_2016_150 (300-ward current claim is BLOCKED).
  4. All records carry basis = 'DERIVED'.
  5. One-to-many weights sum to 1.0 (or 0.0 for unmatched).

Usage
-----
  python scripts/evidence/build_crosswalk.py [--dry-run]

Outputs (all in data/derived/crosswalk/ and data/verification/)
--------------------------------------------------------------
  data/derived/crosswalk/census_to_ghmc_2016.csv
  data/derived/crosswalk/crosswalk_summary.json
  data/verification/crosswalk_checks.json
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
import sys
import unicodedata
from collections import Counter
from decimal import Decimal, InvalidOperation
from pathlib import Path

from location_validation import validate

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"
DERIVED = ROOT / "data" / "derived" / "crosswalk"
VERIFICATION = ROOT / "data" / "verification"

CROSSWALK_OUT = DERIVED / "census_to_ghmc_2016.csv"
SUMMARY_OUT = DERIVED / "crosswalk_summary.json"
CHECKS_OUT = VERIFICATION / "crosswalk_checks.json"

DRY_RUN = "--dry-run" in sys.argv

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TARGET_GEO_VERSION = "GHMC_2016_150"
SOURCE_GEO_VERSION_HYD = "Census2011_Hyderabad"
SOURCE_GEO_VERSION_RGR = "Census2011_Rangareddy"

# Known missing ward polygon numbers in DataMeet GHMC_2016_150 layer
KNOWN_MISSING_POLYGON_WARDS: frozenset[int] = frozenset([3, 4, 11, 13, 31, 113])

# Wards 104 and 107 must NEVER be matched per features.csv acceptance criteria
NEVER_MATCHED_WARDS: frozenset[int] = frozenset([104, 107])

BASIS = "DERIVED"

SOURCE_URL_HYD = (
    "https://data.opencity.in/dataset/hyderabad-census-2011-data"
    " | https://github.com/datameet/Municipal_Spatial_Data/tree/master/Hyderabad"
)
SOURCE_URL_RGR = (
    "https://censusindia.gov.in/nada/index.php/catalog/6728"
    " | https://github.com/datameet/Municipal_Spatial_Data/tree/master/Hyderabad"
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def normalise_name(raw: str) -> str:
    """Lowercase, strip accents, collapse whitespace, remove punctuation."""
    nfd = unicodedata.normalize("NFD", raw)
    ascii_only = "".join(c for c in nfd if unicodedata.category(c) != "Mn")
    lower = ascii_only.lower()
    no_punct = re.sub(r"[^a-z0-9\s]", " ", lower)
    return re.sub(r"\s+", " ", no_punct).strip()


def extract_target_ward_number(name: str) -> int | None:
    """Extract integer ward number from DataMeet name like 'Ward 91 Khairatabad'."""
    m = re.match(r"[Ww]ard\s+(\d+)", name)
    return int(m.group(1)) if m else None


def extract_target_ward_locality(name: str) -> str:
    """Return locality part after 'Ward N '."""
    m = re.match(r"[Ww]ard\s+\d+\s+(.*)", name)
    return normalise_name(m.group(1)) if m else normalise_name(name)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_text(encoding="utf-8").encode()).hexdigest()


# ---------------------------------------------------------------------------
# Load sources
# ---------------------------------------------------------------------------


def load_target_wards() -> list[dict]:
    """Load GHMC_2016_150 ward polygons from DataMeet GeoJSON."""
    geojson_path = RAW / "geography" / "datameet" / "ghmc-wards.geojson"
    if not geojson_path.is_file():
        raise FileNotFoundError(f"Missing target GeoJSON: {geojson_path}")

    with geojson_path.open(encoding="utf-8") as fh:
        data = json.load(fh)

    targets = []
    for f in data.get("features", []):
        props = f.get("properties", {})
        raw_name = props.get("name", "").strip()
        ward_num = extract_target_ward_number(raw_name)
        locality = extract_target_ward_locality(raw_name)
        osm_id = str(props.get("@id", ""))
        targets.append(
            {
                "target_ward_id": osm_id or (f"GHMC_{ward_num:03d}" if ward_num else raw_name),
                "target_ward_num": ward_num,
                "target_ward_name": raw_name,
                "target_locality_norm": locality,
                "target_name_norm": normalise_name(raw_name),
            }
        )
    return targets


def parse_readme_zone_map() -> dict[int, dict]:
    """Parse community DataMeet reference zones; never evidence of Census correspondence."""
    readme_path = RAW / "geography" / "datameet" / "Readme.md"
    if not readme_path.is_file():
        return {}

    zone_map: dict[int, dict] = {}
    zone = ""
    for line in readme_path.read_text(encoding="utf-8").splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) == 2 and re.match(r"Ward\s+\d+", cells[1]):
            if cells[0]:
                zone = cells[0]
            number = extract_target_ward_number(cells[1])
            zone_map[number] = {"ward_name": cells[1], "zone": zone, "circle": ""}
    if zone_map:
        return zone_map
    current_zone = ""
    current_circle = ""

    with readme_path.open(encoding="utf-8") as fh:
        for line in fh:
            line_s = line.strip()
            zm = re.match(r"###+\s+([A-Za-z\s]+Zone)", line_s, re.I)
            if zm:
                current_zone = zm.group(1).strip()
                continue
            cm = re.match(r"\*\*Circle\s+\d+\s*[-–]\s*([^*]+)\*\*", line_s)
            if cm:
                current_circle = cm.group(1).strip()
                continue
            wm = re.match(r"\d+\.\s+Ward\s+(\d+)\s*[-–]\s*(.*)", line_s)
            if wm:
                wnum = int(wm.group(1))
                wname = wm.group(2).strip()
                zone_map[wnum] = {
                    "ward_name": wname,
                    "circle": current_circle,
                    "zone": current_zone,
                }
    return zone_map


HYD_NAME_ALIASES = {
    "ammerpet": "ameerpet",
    "tirumalgiri": "tirumalagiri",
    "maredpally": "maredpalle",
    "himayatnagar": "himayathnagar",
    "golkonda": "golconda",
}


def hyd_census_codes():
    """Resolve mirror-specific local codes through HH-14's explicit town/ward/mandal keys."""
    import openpyxl

    book = openpyxl.load_workbook(
        RAW / "census/hyderabad/hh14.xlsx", read_only=True, data_only=True
    )
    codes = {}
    try:
        for row in list(book.active.values)[7:]:
            ward = str(row[7] or "").strip()
            if not ward.isdigit() or int(ward) == 0 or row[9] != "Urban":
                continue
            key = (normalise_name(str(row[5])), str(row[6]).zfill(6), int(ward))
            value = (str(row[2]).zfill(3), str(row[4]).zfill(5))
            if key in codes and codes[key] != value:
                raise ValueError("Ambiguous official HH-14 administrative code")
            codes[key] = value
    finally:
        book.close()
    return codes


def required_count(raw, field):
    try:
        value = Decimal(str(raw))
    except InvalidOperation as exc:
        raise ValueError(f"Missing/non-numeric Census {field}") from exc
    if not value.is_finite() or value < 0 or value != value.to_integral_value():
        raise ValueError(f"Invalid Census {field}: {raw}")
    return int(value)


def load_hyderabad_pca() -> list[dict]:
    """Load Census 2011 Hyderabad PCA ward rows.

    Columns in CSV: DISTRICT_CODE, DIVISION_CODE, DIVISION_NAME, Name_District,
    Mandal_Code, Name_Mandal, Village_Code, Ward, Level1, VName, TRU, No_HH, TOT_P, ...
    Filter: Level1 == 'WARD'
    """
    pca_path = RAW / "census" / "hyderabad" / "pca.csv"
    if not pca_path.is_file():
        raise FileNotFoundError(f"Missing Hyderabad PCA: {pca_path}")

    rows = []
    official_codes = hyd_census_codes()
    with pca_path.open(encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        for r in reader:
            if r.get("Level1", "").strip() != "WARD":
                continue

            vname = r.get("VName", "").strip()
            ward_col = r.get("Ward", "").strip()

            m = re.search(r"WARD NO\.-(\d+)", vname)
            ward_num = int(m.group(1)) if m else (int(ward_col) if ward_col.isdigit() else None)

            is_ghmc = "GHMC" in vname
            non_ghmc_type = ""
            if not is_ghmc:
                if "(CB)" in vname:
                    non_ghmc_type = "Cantonment_Board"
                elif "(CT)" in vname:
                    non_ghmc_type = "Census_Town"
                else:
                    non_ghmc_type = "Non_GHMC"

            mandal = normalise_name(r.get("Name_Mandal", ""))
            lookup = (
                HYD_NAME_ALIASES.get(mandal, mandal),
                r.get("Village_Code", "").zfill(6),
                ward_num,
            )
            district_code, subdistrict_code = official_codes.get(lookup, ("", ""))
            rows.append(
                {
                    "source_district": "Hyderabad",
                    "source_original_district_code": r.get("DISTRICT_CODE", ""),
                    "source_original_subdistt_code": r.get("Mandal_Code", ""),
                    "source_geo_version": SOURCE_GEO_VERSION_HYD,
                    "source_state_code": "28",
                    "source_district_code": district_code,
                    "source_subdistt_code": subdistrict_code,
                    "source_mandal_name": r.get("Name_Mandal", "").strip(),
                    "source_town_code": r.get("Village_Code", "").strip(),
                    "source_ward_code": ward_col,
                    "source_level": "WARD",
                    "source_name": vname,
                    "source_name_norm": normalise_name(vname),
                    "source_ward_num": ward_num,
                    "source_tot_p": required_count(r.get("TOT_P"), "TOT_P"),
                    "source_no_hh": required_count(r.get("No_HH"), "No_HH"),
                    "is_ghmc": is_ghmc,
                    "non_ghmc_type": non_ghmc_type,
                    "source_url": SOURCE_URL_HYD,
                }
            )
    return rows


def load_rangareddy_pca() -> list[dict]:
    """Load Census 2011 Rangareddy PCA GHMC ward rows.

    Excel format. Filter: Level == 'WARD' and 'GHMC' in Name
    """
    pca_path = RAW / "census" / "rangareddy" / "pca.xlsx"
    if not pca_path.is_file():
        raise FileNotFoundError(f"Missing Rangareddy PCA: {pca_path}")

    import openpyxl

    wb = openpyxl.load_workbook(pca_path, read_only=True, data_only=True)
    ws = wb.active
    rows_iter = ws.iter_rows(values_only=True)
    headers = [str(h).strip() if h is not None else "" for h in next(rows_iter)]

    col_idx = {h: i for i, h in enumerate(headers) if h}

    def get_val(row: tuple, col_name: str, default: str = "") -> str:
        idx = col_idx.get(col_name)
        if idx is None or idx >= len(row):
            return default
        val = row[idx]
        return str(val).strip() if val is not None else default

    rows = []
    for r in rows_iter:
        level = get_val(r, "Level")
        if level != "WARD":
            continue
        raw_name = get_val(r, "Name")
        if "GHMC" not in raw_name:
            continue

        ward_col = get_val(r, "Ward")
        m = re.search(r"WARD NO\.-(\d+)", raw_name)
        ward_num = int(m.group(1)) if m else (int(ward_col) if ward_col.isdigit() else None)

        tot_p = required_count(get_val(r, "TOT_P"), "TOT_P")
        no_hh = required_count(get_val(r, "No_HH"), "No_HH")

        subdistt = get_val(r, "Subdistt")

        rows.append(
            {
                "source_district": "Rangareddy",
                "source_original_district_code": get_val(r, "District"),
                "source_original_subdistt_code": subdistt,
                "source_geo_version": SOURCE_GEO_VERSION_RGR,
                "source_state_code": get_val(r, "State", "28"),
                "source_district_code": get_val(r, "District", "537"),
                "source_subdistt_code": subdistt,
                "source_mandal_name": f"subdist_{subdistt}",
                "source_town_code": get_val(r, "Town/Village"),
                "source_ward_code": ward_col,
                "source_level": "WARD",
                "source_name": raw_name,
                "source_name_norm": normalise_name(raw_name),
                "source_ward_num": ward_num,
                "source_tot_p": tot_p,
                "source_no_hh": no_hh,
                "is_ghmc": True,
                "non_ghmc_type": "",
                "source_url": SOURCE_URL_RGR,
            }
        )
    wb.close()
    return rows


# ---------------------------------------------------------------------------
# Crosswalk Construction
# ---------------------------------------------------------------------------

CROSSWALK_FIELDS = [
    "source_original_district_code",
    "source_original_subdistt_code",
    "source_state_code",
    "source_district_code",
    "source_subdistt_code",
    "source_town_code",
    "source_district",
    "source_geo_version",
    "source_level",
    "source_ward_code",
    "source_ward_num",
    "source_name",
    "source_mandal_name",
    "source_tot_p",
    "source_no_hh",
    "target_geo_version",
    "target_ward_id",
    "target_ward_num",
    "target_ward_name",
    "mapping_method",
    "match_score",
    "match_confidence",
    "one_to_many_weight",
    "is_known_missing_target",
    "never_matched",
    "notes",
    "basis",
    "reviewer_status",
    "location_status",
    "source_url",
]


def build_crosswalk(
    source_rows: list[dict],
    target_wards: list[dict],
    zone_map: dict[int, dict],
) -> list[dict]:
    """Execute the multi-tier crosswalk matching logic adhering to all rules."""
    target_counts = {}
    for target in target_wards:
        number = target["target_ward_num"]
        target_counts[number] = target_counts.get(number, 0) + 1
    target_by_num: dict[int, dict] = {}
    for t in target_wards:
        wn = t["target_ward_num"]
        if wn is not None and wn not in target_by_num:
            target_by_num[wn] = t

    crosswalk_rows = []

    for src in source_rows:
        src_num = src["source_ward_num"]
        src_name = src["source_name"]
        district = src["source_district"]
        is_ghmc = src.get("is_ghmc", True)
        non_ghmc_type = src.get("non_ghmc_type", "")
        mandal_name = src.get("source_mandal_name", "")

        matched_target: dict | None = None
        method = "unmatched"
        confidence = "none"
        score = 0.0
        notes = ""
        weight = 0.0
        is_known_missing = "true" if (src_num in KNOWN_MISSING_POLYGON_WARDS) else "false"
        never_matched = "true" if (src_num in NEVER_MATCHED_WARDS) else "false"

        # Case 1: Non-GHMC areas (Secunderabad CB, Osmania Univ CT)
        if not is_ghmc:
            method = "unmatched_non_ghmc"
            notes = (
                f"{src_name} ({non_ghmc_type}) is not part of GHMC municipal administration; "
                "retained unmatched per spec."
            )

        # Case 2: Wards 104 and 107 - NEVER MATCHED per features.csv acceptance criteria
        elif src_num in NEVER_MATCHED_WARDS:
            method = "unmatched_never_matched"
            notes = (
                f"Ward {src_num} in Census 2011 ({district}, mandal: {mandal_name}) has location "
                f"conflict with GHMC 2016 target ward {src_num}; never matched per spec."
            )

        # Case 3: Known missing polygon in target DataMeet layer
        elif src_num in KNOWN_MISSING_POLYGON_WARDS:
            method = "unmatched_known_missing"
            notes = (
                f"Ward {src_num} is a known missing polygon in DataMeet GHMC_2016_150 layer; "
                "retained unmatched per spec."
            )

        elif target_counts.get(src_num, 0) > 1:
            method = "unmatched_ambiguous_target"
            notes = "Multiple differently named target polygons share this number; no first match."

        # Case 4: Exact ward number match
        elif src_num is not None and src_num in target_by_num:
            matched_target = target_by_num[src_num]
            method = "ward_number"
            confidence = "low"
            score = 0.0
            weight = 0.0
            zinfo = zone_map.get(src_num, {})
            zone_desc = (
                f" (Zone: {zinfo.get('zone', 'N/A')}, Circle: {zinfo.get('circle', 'N/A')})"
                if zinfo
                else ""
            )
            notes = f"Exact ward number match to {matched_target['target_ward_name']}{zone_desc}."

        # Case 5: Mandal fallback when no exact ward join is defensible
        else:
            method = "mandal_fallback"
            confidence = "low"
            score = 0.0
            weight = 0.0
            notes = (
                f"No polygon with ward number {src_num} in DataMeet GHMC_2016_150 layer; "
                f"retained for mandal fallback ({mandal_name}, {district})."
            )

        row = {
            "source_original_district_code": src["source_original_district_code"],
            "source_original_subdistt_code": src["source_original_subdistt_code"],
            "source_state_code": src["source_state_code"],
            "source_district_code": src["source_district_code"],
            "source_subdistt_code": src["source_subdistt_code"],
            "source_town_code": src["source_town_code"],
            "source_district": district,
            "source_geo_version": src["source_geo_version"],
            "source_level": src["source_level"],
            "source_ward_code": src["source_ward_code"],
            "source_ward_num": str(src_num) if src_num is not None else "",
            "source_name": src_name,
            "source_mandal_name": mandal_name,
            "source_tot_p": src["source_tot_p"],
            "source_no_hh": src["source_no_hh"],
            "target_geo_version": TARGET_GEO_VERSION,
            "target_ward_id": matched_target["target_ward_id"] if matched_target else "",
            "target_ward_num": str(matched_target["target_ward_num"]) if matched_target else "",
            "target_ward_name": matched_target["target_ward_name"] if matched_target else "",
            "mapping_method": method,
            "match_score": f"{score:.4f}",
            "match_confidence": confidence,
            "one_to_many_weight": f"{weight:.4f}",
            "is_known_missing_target": is_known_missing,
            "never_matched": never_matched,
            "notes": notes,
            "basis": BASIS,
            "reviewer_status": "needs_review" if matched_target else "excluded_by_rule",
            "location_status": "PENDING_VALIDATION",
            "source_url": src["source_url"],
        }
        crosswalk_rows.append(row)

    source_path = VERIFICATION / "location" / "census2011_wards.geojson"
    source_layer = (
        json.loads(source_path.read_text(encoding="utf-8")) if source_path.exists() else None
    )
    targets_path = RAW / "geography" / "datameet" / "ghmc-wards.geojson"
    target_features = json.loads(targets_path.read_text(encoding="utf-8"))["features"]
    statuses = validate(crosswalk_rows, target_features, source_layer)
    for row, result in zip(crosswalk_rows, statuses, strict=True):
        row["location_status"] = result["location_status"]
        if row["location_status"] == "VERIFIED_EXACT_GEOMETRY":
            row.update(
                match_confidence="high",
                match_score="1.0000",
                reviewer_status="verified",
                one_to_many_weight="1.0000",
            )
        elif row["target_ward_id"]:
            row["notes"] += " Candidate only; location validation: " + row["location_status"] + "."
    return crosswalk_rows


# ---------------------------------------------------------------------------
# Summary & Verification Metrics
# ---------------------------------------------------------------------------


def compute_summary(
    crosswalk: list[dict],
    source_rows: list[dict],
    target_wards: list[dict],
) -> dict:
    """Compute audit metrics across crosswalk results."""
    if len(crosswalk) != len(source_rows):
        raise ValueError("Crosswalk/source row counts differ")
    if len({t["target_ward_id"] for t in target_wards}) != len(target_wards):
        raise ValueError("Duplicate target polygon IDs")
    matched_rows = [r for r in crosswalk if r["target_ward_id"]]
    unmatched_src = [r for r in crosswalk if not r["target_ward_id"]]

    matched_target_ids = {r["target_ward_id"] for r in matched_rows}
    all_target_ids = {t["target_ward_id"] for t in target_wards}
    unmatched_target_ids = all_target_ids - matched_target_ids

    target_by_id = {t["target_ward_id"]: t for t in target_wards}
    unmatched_target_nums = sorted(
        {
            target_by_id[tid]["target_ward_num"]
            for tid in unmatched_target_ids
            if tid in target_by_id and target_by_id[tid]["target_ward_num"] is not None
        }
    )

    method_counts: dict[str, int] = {}
    for r in crosswalk:
        m = r["mapping_method"]
        method_counts[m] = method_counts.get(m, 0) + 1

    total_src = len(source_rows)
    coverage_pct = round(len(matched_rows) / total_src * 100, 2) if total_src > 0 else 0.0

    ghmc_source_rows = [s for s in source_rows if s.get("is_ghmc", True)]
    ghmc_matched_rows = [
        r
        for r, s in zip(crosswalk, source_rows, strict=True)
        if s.get("is_ghmc", True) and r["target_ward_id"]
    ]
    ghmc_coverage_pct = (
        round(len(ghmc_matched_rows) / len(ghmc_source_rows) * 100, 2) if ghmc_source_rows else 0.0
    )

    matched_pop = sum(
        s["source_tot_p"]
        for s, r in zip(source_rows, crosswalk, strict=True)
        if r["target_ward_id"]
    )
    total_pop = sum(s["source_tot_p"] for s in source_rows)
    weighted_pop_coverage_pct = round(matched_pop / total_pop * 100, 2) if total_pop > 0 else 0.0

    target_counts: dict[str, list[str]] = {}
    for r in matched_rows:
        tid = r["target_ward_id"]
        target_counts.setdefault(tid, []).append(r["source_name"])
    duplicate_targets = {k: v for k, v in target_counts.items() if len(v) > 1}

    target_districts: dict[str, set[str]] = {}
    for r in matched_rows:
        tid = r["target_ward_id"]
        target_districts.setdefault(tid, set()).add(r["source_district"])
    conflicting_district = {k: sorted(v) for k, v in target_districts.items() if len(v) > 1}

    rows_need_review = [r for r in crosswalk if r["reviewer_status"] == "needs_review"]

    return {
        "source_data_year": 2011,
        "coverage_interpretation": "Candidate ward-number matches, not validated geography",
        "weighted_pop_coverage_interpretation": "Candidate-source population; not transferred",
        "location_status_counts": dict(
            sorted(Counter(r["location_status"] for r in crosswalk).items())
        ),
        "validated_location_count": sum(
            r["location_status"] == "VERIFIED_EXACT_GEOMETRY" for r in crosswalk
        ),
        "validated_location_coverage_pct": round(
            100
            * sum(r["location_status"] == "VERIFIED_EXACT_GEOMETRY" for r in crosswalk)
            / len(ghmc_source_rows),
            2,
        ),
        "source_geo_version_hyderabad": SOURCE_GEO_VERSION_HYD,
        "source_geo_version_rangareddy": SOURCE_GEO_VERSION_RGR,
        "target_geo_version": TARGET_GEO_VERSION,
        "target_vintage_status": "UNVERIFIED_HISTORICAL_150_WARD_LAYER",
        "current_ward_claim": "BLOCKED — no official machine-readable 300-ward boundary verified",
        "total_census_source_rows": len(source_rows),
        "total_target_ward_polygons": len(target_wards),
        "known_missing_polygon_wards": sorted(KNOWN_MISSING_POLYGON_WARDS),
        "never_matched_wards": sorted(NEVER_MATCHED_WARDS),
        "wards_104_107_never_matched": True,
        "exact_ward_number_matches": method_counts.get("ward_number", 0),
        "unmatched_never_matched_count": method_counts.get("unmatched_never_matched", 0),
        "unmatched_known_missing_count": method_counts.get("unmatched_known_missing", 0),
        "unmatched_non_ghmc_count": method_counts.get("unmatched_non_ghmc", 0),
        "mandal_fallback_count": method_counts.get("mandal_fallback", 0),
        "total_unmatched_source_rows": len(unmatched_src),
        "unmatched_target_ward_nums": unmatched_target_nums,
        "unmatched_target_ward_count": len(unmatched_target_nums),
        "unmatched_target_polygon_count": len(unmatched_target_ids),
        "candidate_target_polygon_count": len(matched_target_ids),
        "candidate_target_polygon_coverage_pct": round(
            100 * len(matched_target_ids) / len(all_target_ids), 2
        ),
        "candidate_target_unique_ward_count": len({r["target_ward_num"] for r in matched_rows}),
        "ambiguous_target_numbers": sorted(
            {
                t["target_ward_num"]
                for t in target_wards
                if sum(x["target_ward_num"] == t["target_ward_num"] for x in target_wards) > 1
            }
        ),
        "total_coverage_pct": coverage_pct,
        "ghmc_coverage_pct": ghmc_coverage_pct,
        "weighted_pop_coverage_pct": weighted_pop_coverage_pct,
        "duplicate_target_assignments": duplicate_targets,
        "conflicting_district_assignments": conflicting_district,
        "rows_requiring_review": len(rows_need_review),
        "basis": BASIS,
    }


def compute_checks(crosswalk: list[dict], summary: dict) -> dict:
    """Produce machine-readable verification report for verify_crosswalk.py."""
    # Ensure wards 104 and 107 are never matched
    for r in crosswalk:
        if r["source_ward_num"] in ("104", "107"):
            msg = f"Ward {r['source_ward_num']} was matched to {r['target_ward_id']}"
            assert not r["target_ward_id"], msg
            assert r["never_matched"] == "true"

    return {
        "source_data_year": 2011,
        "validated_location_count": summary["validated_location_count"],
        "normalized_lf_text_hashes": True,
        "optional_location_source_sha256": hashlib.sha256(
            (VERIFICATION / "location" / "census2011_wards.geojson").read_bytes()
        ).hexdigest()
        if (VERIFICATION / "location" / "census2011_wards.geojson").exists()
        else None,
        "target_geo_version": TARGET_GEO_VERSION,
        "current_ward_claim_blocked": True,
        "known_missing_polygon_wards": summary["known_missing_polygon_wards"],
        "never_matched_wards": summary["never_matched_wards"],
        "wards_104_107_never_matched": True,
        "total_source_rows": summary["total_census_source_rows"],
        "total_matched": summary["exact_ward_number_matches"],
        "total_unmatched_source": summary["total_unmatched_source_rows"],
        "ghmc_coverage_pct": summary["ghmc_coverage_pct"],
        "coverage_reported": True,
        "all_rows_have_basis": all(r["basis"] == BASIS for r in crosswalk),
        "all_rows_have_geo_version": all(
            r["target_geo_version"] == TARGET_GEO_VERSION for r in crosswalk
        ),
        "one_to_many_weights_valid": all(
            float(r["one_to_many_weight"])
            == (1.0 if r["location_status"] == "VERIFIED_EXACT_GEOMETRY" else 0.0)
            for r in crosswalk
        ),
        "output_sha256": {},
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def build_mandal_context(output_path):
    """Fallback at original Census geography, explicitly not joined to target wards."""
    import openpyxl
    from build_evidence import metrics

    with (VERIFICATION / "source_manifest.csv").open(encoding="utf-8", newline="") as handle:
        urls = {r["file_path"]: r["source_url"] for r in csv.DictReader(handle)}
    rows = []
    for district, filename in (("Hyderabad", "hyderabad"), ("Rangareddy", "rangareddy")):
        relative = f"data/raw/census/{filename}/hh14.xlsx"
        book = openpyxl.load_workbook(ROOT / relative, read_only=True, data_only=True)
        try:
            for row in list(book.active.values)[7:]:
                if row[9] != "Urban" or not str(row[8]).startswith("Sub-Dist"):
                    continue
                result = {
                    "district": district,
                    "district_code": str(row[2]).zfill(3),
                    "subdistrict_code": str(row[4]).zfill(5),
                    "subdistrict_name": row[5],
                    "census_year": 2011,
                    "scope": "ALL_URBAN_SUBDISTRICT_NOT_GHMC_ONLY",
                    "target_ward_id": "",
                    "target_mapping_status": "NOT_JOINED",
                    "source_url": urls[relative],
                }
                for key, value in metrics(row).items():
                    result[key] = value
                    result[key + "_basis"] = "DERIVED" if value is not None else "UNAVAILABLE"
                rows.append(result)
        finally:
            book.close()
    rows.sort(key=lambda r: (r["district_code"], r["subdistrict_code"]))
    keys = [(r["district_code"], r["subdistrict_code"]) for r in rows]
    if len(keys) != len(set(keys)):
        raise ValueError("Ambiguous Census urban subdistrict context")
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    mode = "dry-run" if DRY_RUN else "live"
    print(f"E1 build_crosswalk (mode={mode})")

    print("  Loading target wards (GHMC_2016_150)...")
    target_wards = load_target_wards()
    print(f"    {len(target_wards)} polygon features loaded")

    zone_map = parse_readme_zone_map()

    print("  Loading Census 2011 Hyderabad PCA...")
    hyd_rows = load_hyderabad_pca()
    print(f"    {len(hyd_rows)} ward-level rows loaded")

    print("  Loading Census 2011 Rangareddy PCA (GHMC wards)...")
    rgr_rows = load_rangareddy_pca()
    print(f"    {len(rgr_rows)} GHMC ward-level rows loaded")

    source_rows = hyd_rows + rgr_rows
    print(f"  Total source rows: {len(source_rows)}")

    print("  Building crosswalk...")
    crosswalk = build_crosswalk(source_rows, target_wards, zone_map)

    summary = compute_summary(crosswalk, source_rows, target_wards)
    checks = compute_checks(crosswalk, summary)

    print("\n  Results:")
    print(f"    Total source rows:      {summary['total_census_source_rows']}")
    print(f"    Target polygons:        {summary['total_target_ward_polygons']}")
    print(f"    Exact number match:     {summary['exact_ward_number_matches']}")
    print(f"    Unmatched (104/107):    {summary['unmatched_never_matched_count']}")
    print(f"    Unmatched (missing):    {summary['unmatched_known_missing_count']}")
    print(f"    Unmatched (non-GHMC):   {summary['unmatched_non_ghmc_count']}")
    print(f"    GHMC coverage:          {summary['ghmc_coverage_pct']}%")
    print(f"    Weighted pop coverage:  {summary['weighted_pop_coverage_pct']}%")
    print(f"    Wards 104/107 matched:  {not summary['wards_104_107_never_matched']}")

    if DRY_RUN:
        print("\n  [DRY-RUN] No files written.")
        return 0

    DERIVED.mkdir(parents=True, exist_ok=True)
    VERIFICATION.mkdir(parents=True, exist_ok=True)

    with CROSSWALK_OUT.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=CROSSWALK_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(crosswalk)
    print(f"\n  Written: {CROSSWALK_OUT.relative_to(ROOT)}")

    with SUMMARY_OUT.open("w", encoding="utf-8", newline="\n") as fh:
        json.dump(summary, fh, indent=2, ensure_ascii=False)
    print(f"  Written: {SUMMARY_OUT.relative_to(ROOT)}")

    context_path = DERIVED / "census_mandal_context.csv"
    build_mandal_context(context_path)
    checks["output_sha256"] = {
        "census_mandal_context.csv": sha256_file(context_path),
        "census_to_ghmc_2016.csv": sha256_file(CROSSWALK_OUT),
        "crosswalk_summary.json": sha256_file(SUMMARY_OUT),
    }
    with CHECKS_OUT.open("w", encoding="utf-8", newline="\n") as fh:
        json.dump(checks, fh, indent=2, ensure_ascii=False)
    print(f"  Written: {CHECKS_OUT.relative_to(ROOT)}")

    print("\nE1 crosswalk build complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
