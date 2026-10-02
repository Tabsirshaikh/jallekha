"""Build the E5 field-check screen from audited E2/E3 inputs; fail closed on joins."""

from __future__ import annotations

import csv
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.services.underserved import AreaEvidence, screen  # noqa: E402

INPUTS = (
    "data/derived/evidence/ward_evidence.csv",
    "data/derived/evidence/evidence_summary.json",
    "data/derived/growth/growth.csv",
    "data/derived/growth/summary.json",
    "data/derived/crosswalk/census_to_ghmc_2016.csv",
    "data/raw/geography/datameet/ghmc-wards.geojson",
    "data/verification/source_manifest.csv",
)
ROWS = "data/derived/underserved/field_checks.json"
SUMMARY = "data/derived/underserved/summary.json"
CHECKS = "data/verification/underserved_checks.json"


def optional_number(value: str | None) -> float | None:
    if value in (None, ""):
        return None
    return float(value)


def load_areas(root: Path = ROOT) -> list[AreaEvidence]:
    with (root / INPUTS[0]).open(encoding="utf-8-sig", newline="") as handle:
        evidence = list(csv.DictReader(handle))
    with (root / INPUTS[2]).open(encoding="utf-8-sig", newline="") as handle:
        growth = {row["ward_id"]: row for row in csv.DictReader(handle)}
    areas = []
    for row in evidence:
        growth_row = growth.get(row["ward_id"], {})
        census_valid = (
            row["location_status"] == "VERIFIED_EXACT_GEOMETRY"
            and row["allocation_eligible"].strip().lower() == "true"
        )
        booking_valid = growth_row.get("booking_validation") == "VERIFIED_SECTION_TO_WARD_TRANSFER"
        areas.append(
            AreaEvidence(
                ward_id=row["ward_id"],
                ward_name=row["ward_name"],
                households=optional_number(row["households"]),
                wad=optional_number(row["wad"]),
                non_tap_share=optional_number(row["non_tap_share"]),
                cad=optional_number(row["cad"]),
                hardship=optional_number(row["hardship"]),
                bookings=None,
                period_year=None,
                household_reference_year=int(row["census_year"]) if census_valid else None,
                need_reference_year=int(row["census_year"]) if census_valid else None,
                census_location_validated=census_valid,
                booking_transfer_validated=booking_valid,
                booking_period_complete=False,
                basis="REAL",
                geography_version=row["geo_version"],
                growth_ratio=optional_number(growth_row.get("building_growth_ratio")),
                growth_quality=growth_row.get("growth_stability", "UNAVAILABLE"),
            )
        )
    return areas


def build(root: Path = ROOT) -> dict[str, bytes]:
    areas = load_areas(root)
    result = screen(areas)
    blockers = Counter(
        reason["code"] for row in result["data_review_queue"] for reason in row["reasons"]
    )
    evidence_summary = json.loads((root / INPUTS[1]).read_text(encoding="utf-8"))
    growth_summary = json.loads((root / INPUTS[3]).read_text(encoding="utf-8"))
    summary = {
        **result["summary"],
        "screen_status": "DATA_REVIEW_REQUIRED" if result["data_review_queue"] else "SCREENED",
        "screening_basis": "REAL_SOURCE_INPUTS;NO_SYNTHETIC_VALUES_IN_OPERATIONAL_OUTPUT",
        "blocking_reason_counts": dict(sorted(blockers.items())),
        "e2_location_validated_joins": evidence_summary["allocation_eligible_count"],
        "e3_growth_context_only": True,
        "e3_high_variability_review_flags": growth_summary["high_variability_review_flags"],
        "booking_transfer": "UNAVAILABLE_NO_VERIFIED_SECTION_TO_WARD_CROSSWALK",
        "tanker_data_granularity": "MONTHLY_HMWSSB_SECTION_COUNTS",
        "reporting_probability": None,
        "under_service_ground_truth": None,
        "field_check_outcomes_recorded": 0,
        "interpretation": (
            "A low booking/reference ratio can trigger a field check only after all evidence "
            "gates pass; it does not estimate unreported demand or prove under-service."
        ),
        "limits": [
            (
                "E2 Census values are approximate (2009 to 2016 ward crosswalk); "
                "none is exact-geometry validated."
            ),
            (
                "HMWSSB tanker observations are monthly section totals; no verified "
                "section-to-ward transfer exists."
            ),
            (
                "Census household and need covariates are historical and provisional "
                "for unvalidated locations."
            ),
            (
                "All 145 E3 growth observations carry a review-only variability flag; "
                "growth is not used for ranking."
            ),
            (
                "No field-check labels exist, so empirical precision/recall and "
                "real-world accuracy are unavailable."
            ),
            (
                "This screen cannot identify who did not report or infer reporting "
                "propensity from counts alone."
            ),
            (
                "A candidate means 'send someone to check'; it never changes allocation, "
                "eligibility, or entitlement."
            ),
        ],
    }
    artifacts = {
        ROWS: (json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n").encode(),
        SUMMARY: (json.dumps(summary, indent=2, sort_keys=True, allow_nan=False) + "\n").encode(),
    }
    checks = {
        "schema_version": "E5-1",
        "inputs_sha256": {
            path: hashlib.sha256((root / path).read_bytes()).hexdigest() for path in INPUTS
        },
        "outputs_sha256": {
            path: hashlib.sha256(value).hexdigest() for path, value in artifacts.items()
        },
    }
    artifacts[CHECKS] = (json.dumps(checks, indent=2, sort_keys=True) + "\n").encode()
    return artifacts


def main() -> None:
    artifacts = build()
    checks = json.loads(artifacts[CHECKS])
    checks["outputs_sha256"] = {
        path: hashlib.sha256(content).hexdigest()
        for path, content in artifacts.items()
        if path in (ROWS, SUMMARY)
    }
    artifacts[CHECKS] = (json.dumps(checks, indent=2, sort_keys=True) + "\n").encode()
    for relative, content in artifacts.items():
        path = ROOT / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    print("P1:E5 built fail-closed ward field-check artifacts from E2/E3")


if __name__ == "__main__":
    main()
