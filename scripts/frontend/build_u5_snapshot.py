"""Build the local, derived U5 frontend snapshot from reviewed E2-E6 outputs."""

from __future__ import annotations

import csv
import json
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "frontend" / "src" / "data"


def csv_rows(relative_path: str) -> list[dict[str, str]]:
    with (ROOT / relative_path).open(encoding="utf-8-sig", newline="") as source:
        return list(csv.DictReader(source))


def optional_float(value: str | None) -> float | None:
    if value in (None, ""):
        return None
    return float(value)


def optional_int(value: str | None) -> int | None:
    number = optional_float(value)
    return int(number) if number is not None else None


def read_json(relative_path: str) -> dict:
    return json.loads((ROOT / relative_path).read_text(encoding="utf-8"))


def main() -> None:
    evidence_rows = csv_rows("data/derived/evidence/ward_evidence.csv")
    growth_by_id = {row["ward_id"]: row for row in csv_rows("data/derived/growth/growth.csv")}
    equity_by_id = {row["ward_id"]: row for row in csv_rows("data/derived/equity/wards.csv")}
    e5 = read_json("data/derived/underserved/field_checks.json")
    field_by_id = {row["ward_id"]: row for row in e5["rows"]}
    geojson = read_json("data/derived/coverage/water_access_evidence.geojson")
    geometry_by_id = {feature["properties"]["ward_id"]: feature for feature in geojson["features"]}

    ids = [row["ward_id"] for row in evidence_rows]
    expected = set(ids)
    for label, indexed in (
        ("growth", growth_by_id),
        ("equity", equity_by_id),
        ("field-check", field_by_id),
        ("geometry", geometry_by_id),
    ):
        if set(indexed) != expected:
            raise ValueError(f"{label} ward ids do not match E2 evidence")

    wards = []
    for row in evidence_rows:
        ward_id = row["ward_id"]
        growth = growth_by_id[ward_id]
        equity = equity_by_id[ward_id]
        field = field_by_id[ward_id]
        wards.append(
            {
                "id": ward_id,
                "name": row["ward_name"],
                "geographyVersion": row["geo_version"],
                "censusYear": optional_int(row["census_year"]),
                "sourceDistrict": row["source_district"],
                "joinStatus": row["join_status"],
                "locationStatus": row["location_status"],
                "reviewRequired": row["review_required"].lower() == "true",
                "allocationEligible": row["allocation_eligible"].lower() == "true",
                "censusCoverage": optional_float(row["census_coverage"]),
                "population2011": optional_int(row["population"]),
                "households2011": optional_int(row["households"]),
                "nonTapShare": optional_float(row["non_tap_share"]),
                "waterAccessDeficitShare": optional_float(row["wad"]),
                "hardshipShare": optional_float(row["hardship"]),
                "constrainedAccessShare": optional_float(row["cad"]),
                "criticalFacilities": optional_int(row["critical_facilities"]),
                "growthRatio": optional_float(growth["building_growth_ratio"]),
                "annualGrowth": optional_float(growth["adjusted_annual_growth"]),
                "growthQuality": growth["growth_stability"],
                "growthBasis": growth["basis"],
                "bookings": optional_int(equity["bookings"]),
                "bookingsPer1000": optional_float(equity["bookings_per_1000"]),
                "bookingStatus": equity["mapping_status"],
                "fieldStatus": field["status"],
                "fieldCandidate": field["field_check_candidate"],
                "fieldReasons": field["reasons"],
                "observedBookings": field.get("observed_bookings"),
                "peerExpected": (field.get("model_scores") or {}).get("PEER_MEDIAN", {}).get("expected"),
                "modelExpected": (field.get("model_scores") or {}).get("NB", {}).get("expected"),
                "fieldNotes": field["input_notes"],
                "fieldAction": field["action"],
            }
        )

    equity_summary = read_json("data/derived/equity/summary.json")
    evidence_summary = read_json("data/derived/evidence/evidence_summary.json")
    snapshot = {
        "snapshotDate": date.today().isoformat(),
        "basis": "DERIVED",
        "geographyVersion": geojson["geography_version"],
        "sourceNotes": {
            "access": (
                "Census 2011 values reweighted from the rebuilt 2009 ward map to the "
                "historical 2016 ward geography; approximate, not current observations."
            ),
            "growth": (
                "Google Open Buildings Temporal 2016-2023 building-change signal; "
                "not a population or household estimate."
            ),
            "equity": (
                "HMWSSB monthly section booking/delivery records; section metrics are exact, "
                "ward placement is approximate."
            ),
            "fieldChecks": (
                "E5 screening: the peer median and a negative-binomial model must both flag a "
                "ward (the spatial models did not converge); flags are hypotheses for field "
                "review and do not establish unmet need or entitlement."
            ),
        },
        "summary": {
            "wardCount": len(wards),
            "censusMappedCount": sum(ward["population2011"] is not None for ward in wards),
            "censusReviewCount": evidence_summary["review_required_count"],
            "fieldCheckCount": e5["summary"]["field_check_count"],
            "eligibleCount": e5["summary"]["eligible_count"],
            "dataReviewCount": e5["summary"]["data_review_count"],
            "equity": {
                key: equity_summary[key]
                for key in (
                    "bookings",
                    "delivered",
                    "gini",
                    "top_section_count",
                    "top_booking_share",
                    "bottom_section_count",
                    "bottom_booking_share",
                    "section_count",
                    "missing_source_months",
                    "ward_booking_share_placed",
                    "ward_metrics_status",
                    "interpretation",
                )
            },
        },
        "wards": wards,
        "fieldCheckLimitations": e5["limitations"],
    }
    slim_geometry = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": feature["type"],
                "geometry": feature["geometry"],
                "properties": {
                    "ward_id": feature["properties"]["ward_id"],
                    "ward_name": feature["properties"]["ward_name"],
                },
            }
            for feature in geojson["features"]
        ],
    }
    if len(wards) != 145:
        raise ValueError(f"Expected 145 historical ward records, found {len(wards)}")

    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "u5Evidence.json").write_text(
        json.dumps(snapshot, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    (OUTPUT / "u5Geometry.json").write_text(
        json.dumps(slim_geometry, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {len(wards)} derived ward records to {OUTPUT}")


if __name__ == "__main__":
    main()
