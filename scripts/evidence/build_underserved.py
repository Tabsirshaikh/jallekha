"""Build the E5 field-check screen from audited inputs; fail closed on missing data.

Inputs per 2016 ward: Census 2011 need shares (E2, historical structural indicators),
2025 households (modelled central estimate, data/derived/population), and 2025 tanker
bookings (HMWSSB portal, Jan-Dec 2025) summed over the sections placed in the ward
(data/derived/crosswalk/section_to_ward_2016.csv, approximate). Wards without a placed
section cannot be screened. Every row carries input notes; a candidate only means "send
someone to check".
"""

from __future__ import annotations

import csv
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.services import hmwssb  # noqa: E402
from app.services.underserved import AreaEvidence, screen  # noqa: E402

INPUTS = (
    "data/derived/evidence/ward_evidence.csv",
    "data/derived/evidence/evidence_summary.json",
    "data/derived/growth/growth.csv",
    "data/derived/growth/summary.json",
    "data/derived/crosswalk/census_to_ghmc_2016.csv",
    "data/raw/geography/datameet/ghmc-wards.geojson",
    "data/verification/source_manifest.csv",
    "data/derived/population/ward_population_2025.csv",
    "data/derived/crosswalk/section_to_ward_2016.csv",
)
TANKERS = "data/raw/hmwssb_tankers_portal"
PERIOD_YEAR = 2025  # last complete year before the Feb/Mar 2026 section re-cut
INPUT_NOTES = (
    "APPROXIMATE_BOOKING_TRANSFER",
    "HISTORICAL_NEED_REFERENCE_2011",
    "MODELLED_HOUSEHOLDS_2025",
)
ROWS = "data/derived/underserved/field_checks.json"
SUMMARY = "data/derived/underserved/summary.json"
CHECKS = "data/verification/underserved_checks.json"


def ward_bookings(root: Path) -> tuple[dict[str, int], dict[str, set[int]], set[int]]:
    """PERIOD_YEAR bookings per ward over placed sections, the months each ward appears in,
    and the months the source publishes for the whole city.

    The portal never publishes zero rows (the smallest section-month value is 1), so a section
    missing from a month that exists for the city had no bookings that month; a whole missing
    month (e.g. Dec 2022) is still missing, not zero."""
    with (root / INPUTS[8]).open(encoding="utf-8", newline="") as handle:
        links = {r["section"]: r["ward_id"] for r in csv.DictReader(handle) if r["ward_id"]}
    totals: dict[str, int] = {}
    months: dict[str, set[int]] = {}
    city_months: set[int] = set()
    for row in hmwssb.read_rows(root / TANKERS):
        if row["year"] == PERIOD_YEAR:
            city_months.add(row["month"])
        ward = links.get(row["section"])
        if ward and row["year"] == PERIOD_YEAR:
            totals[ward] = totals.get(ward, 0) + row["bookings"]
            months.setdefault(ward, set()).add(row["month"])
    return totals, months, city_months


def optional_number(value: str | None) -> float | None:
    if value in (None, ""):
        return None
    return float(value)


def load_areas(root: Path = ROOT) -> list[AreaEvidence]:
    with (root / INPUTS[0]).open(encoding="utf-8-sig", newline="") as handle:
        evidence = list(csv.DictReader(handle))
    with (root / INPUTS[2]).open(encoding="utf-8-sig", newline="") as handle:
        growth = {row["ward_id"]: row for row in csv.DictReader(handle)}
    with (root / INPUTS[7]).open(encoding="utf-8-sig", newline="") as handle:
        population = {row["ward_id"]: row for row in csv.DictReader(handle)}
    bookings, months, city_months = ward_bookings(root)
    areas = []
    for row in evidence:
        growth_row = growth.get(row["ward_id"], {})
        # Exact geometry, or E2's approximate placement on the rebuilt 2009 ward map: enough
        # for a field-check screen, because a flag only sends someone to check.
        census_valid = (
            row["location_status"] in ("VERIFIED_EXACT_GEOMETRY", "APPROXIMATE_2009_MAP")
            and row["allocation_eligible"].strip().lower() == "true"
        )
        # Approximate transfer (sections placed by located point) is accepted for screening;
        # every row is labelled APPROXIMATE_BOOKING_TRANSFER.
        booking_valid = (
            growth_row.get("booking_validation")
            in (
                "VERIFIED_SECTION_TO_WARD_TRANSFER",
                "APPROXIMATE_SECTION_POINT_IN_WARD",
            )
            and row["ward_id"] in bookings
        )
        households_2025 = optional_number(
            population.get(row["ward_id"], {}).get("households_2025_central")
        )
        areas.append(
            AreaEvidence(
                ward_id=row["ward_id"],
                ward_name=row["ward_name"],
                households=households_2025,
                wad=optional_number(row["wad"]),
                non_tap_share=optional_number(row["non_tap_share"]),
                cad=optional_number(row["cad"]),
                hardship=optional_number(row["hardship"]),
                bookings=bookings.get(row["ward_id"]),
                period_year=PERIOD_YEAR,
                household_reference_year=PERIOD_YEAR if households_2025 else None,
                need_reference_year=int(row["census_year"]) if census_valid else None,
                census_location_validated=census_valid,
                booking_transfer_validated=booking_valid,
                booking_period_complete=len(city_months) == 12,
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
    _, months, _ = ward_bookings(root)
    for row in result["rows"] + result["field_check_list"] + result["data_review_queue"]:
        row["input_notes"] = list(INPUT_NOTES) + (
            ["ABSENT_SECTION_MONTH_COUNTED_AS_ZERO"]
            if 0 < len(months.get(row["ward_id"], ())) < 12
            else []
        )
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
        "e3_noisy_trend_review_flags": growth_summary["noisy_trend_review_flags"],
        "booking_transfer": "APPROXIMATE_SECTION_POINT_IN_WARD",
        "period": f"{PERIOD_YEAR} (12 months)",
        "household_exposure": "2025 modelled central estimate (data/derived/population)",
        "input_notes": list(INPUT_NOTES),
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
                "E2 Census values are approximate (2009 to 2016 ward crosswalk); they are "
                "accepted for field checks only, never as exact-geometry validation."
            ),
            (
                "Ward bookings sum the HMWSSB sections placed in the ward by located point "
                "(about 88% of bookings); a ward with an unplaced section may be undercounted "
                "and look under-served."
            ),
            (
                "Need shares are Census 2011 (structural, historical); households are a 2025 "
                "modelled estimate with a range."
            ),
            (
                "E3 building trends are stable after removing city-wide year shocks; growth is "
                "context only and not used for ranking."
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
        "schema_version": "E5-2",
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
