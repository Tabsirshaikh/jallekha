import csv
import importlib.util
import json
from pathlib import Path

import pytest

from app.services.coverage import BOOKING_COVERAGE, FIELD_CHECKS, WATER_ACCESS

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "coverage_builder", ROOT / "scripts/evidence/build_coverage.py"
)
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


def decoded_outputs():
    artifacts = builder.build()
    return artifacts, {
        path: json.loads(value) for path, value in artifacts.items() if path != builder.CHECKS
    }


def test_generated_layers_are_deterministic_and_match_reviewed_geography():
    artifacts, decoded = decoded_outputs()
    assert artifacts == builder.build()
    source = json.loads((ROOT / builder.INPUTS[0]).read_text(encoding="utf-8-sig"))
    source_geometry = {
        feature["properties"]["@id"]: feature["geometry"] for feature in source["features"]
    }
    for layer_id in (WATER_ACCESS, BOOKING_COVERAGE, FIELD_CHECKS):
        layer = decoded[f"{builder.OUTPUT_DIR}/{layer_id}.geojson"]
        assert layer["operational_use"] is False
        assert len(layer["features"]) == 145
        assert {
            feature["properties"]["ward_id"]: feature["geometry"] for feature in layer["features"]
        } == source_geometry


def test_unavailable_values_are_null_and_provisional_values_remain_review_only():
    _, decoded = decoded_outputs()
    water = decoded[f"{builder.OUTPUT_DIR}/{WATER_ACCESS}.geojson"]
    booking = decoded[f"{builder.OUTPUT_DIR}/{BOOKING_COVERAGE}.geojson"]
    field = decoded[f"{builder.OUTPUT_DIR}/{FIELD_CHECKS}.geojson"]
    assert (
        sum(
            feature["properties"]["water_access_deficit_share"] is not None
            for feature in water["features"]
        )
        == 143
    )
    # Water-access eligibility passes through from E2 (approximate 2009 -> 2016 crosswalk).
    e2_rows = list(
        csv.DictReader(
            (ROOT / "data/derived/evidence/ward_evidence.csv").open(encoding="utf-8", newline="")
        )
    )
    e2_eligible = {r["ward_id"] for r in e2_rows if r["allocation_eligible"] == "True"}
    assert {
        feature["properties"]["ward_id"]
        for feature in water["features"]
        if feature["properties"]["allocation_eligible"]
    } == e2_eligible
    assert all(
        feature["properties"]["display_status"].endswith("APPROXIMATE_2009_CROSSWALK")
        for feature in water["features"]
        if feature["properties"]["water_access_deficit_share"] is not None
    )
    assert all(
        not feature["properties"]["allocation_eligible"]
        for feature in booking["features"] + field["features"]
    )
    # Booking layer = E4's approximate ward bookings (sections placed by located point)
    e4 = {
        r["ward_id"]: r
        for r in csv.DictReader(
            (ROOT / "data/derived/equity/wards.csv").open(encoding="utf-8", newline="")
        )
    }
    for feature in booking["features"]:
        props = feature["properties"]
        row = e4[props["ward_id"]]
        if row["bookings"]:
            assert props["observed_bookings"] == float(row["bookings"])
            assert props["display_status"] == "APPROXIMATE_SECTION_POINT_IN_WARD"
            assert props["value_basis"] == "DERIVED_APPROXIMATE"
        else:
            assert props["observed_bookings"] is None and props["bookings_per_1000"] is None
            assert props["display_status"] == "UNAVAILABLE_NO_PLACED_SECTION"
    assert all(
        feature["properties"]["field_check_candidate"] is None
        and feature["properties"]["display_status"] == "DATA_REVIEW_REQUIRED"
        for feature in field["features"]
    )


def test_manifest_has_exactly_three_layers_and_excludes_unsupported_tap_claim():
    _, decoded = decoded_outputs()
    manifest = decoded[builder.MANIFEST]
    assert [item["layer_id"] for item in manifest["layers"]] == [
        WATER_ACCESS,
        BOOKING_COVERAGE,
        FIELD_CHECKS,
    ]
    e4_rates = sum(
        1
        for r in csv.DictReader(
            (ROOT / "data/derived/equity/wards.csv").open(encoding="utf-8", newline="")
        )
        if r["bookings_per_1000"]
    )
    assert e4_rates >= 85
    assert [item["non_null_value_count"] for item in manifest["layers"]] == [143, e4_rates, 0]
    assert manifest["excluded_layers"] == [
        {
            "layer_id": "people_within_500m_public_tap",
            "reason": "NO_VERIFIED_PUBLIC_TAP_LOCATION_OR_SERVICE_DATA",
        }
    ]


def test_builder_rejects_misaligned_dependency_rows():
    ward_geojson = json.loads((ROOT / builder.INPUTS[0]).read_text(encoding="utf-8-sig"))
    layers = builder.build()
    field = json.loads(layers[f"{builder.OUTPUT_DIR}/{FIELD_CHECKS}.geojson"])
    field["features"].pop()
    with pytest.raises(ValueError, match="do not exactly match"):
        from app.services.coverage import build_coverage_layers

        build_coverage_layers(
            ward_geojson,
            [
                {
                    "ward_id": feature["properties"]["@id"],
                    "ward_name": feature["properties"]["name"],
                }
                for feature in ward_geojson["features"]
            ],
            [
                {
                    "ward_id": feature["properties"]["ward_id"],
                }
                for feature in field["features"]
            ],
            {"ward_metrics_status": "BLOCKED_NO_VERIFIED_SECTION_WARD_CROSSWALK"},
        )
