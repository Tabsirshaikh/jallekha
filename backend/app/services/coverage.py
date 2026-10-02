"""Build auditable map views from E2, E4, and E5 without inventing ward metrics."""

from __future__ import annotations

from copy import deepcopy

from app.config.coverage import COVERAGE_CONFIG, CoverageConfig

WATER_ACCESS = "water_access_evidence"
BOOKING_COVERAGE = "booking_coverage"
FIELD_CHECKS = "field_check_status"
LAYER_IDS = (WATER_ACCESS, BOOKING_COVERAGE, FIELD_CHECKS)


def _index(rows: list[dict], name: str) -> dict[str, dict]:
    indexed = {}
    for row in rows:
        ward_id = row.get("ward_id")
        if not isinstance(ward_id, str) or not ward_id:
            raise ValueError(f"{name} row has no ward_id")
        if ward_id in indexed:
            raise ValueError(f"{name} contains duplicate ward_id {ward_id}")
        indexed[ward_id] = row
    return indexed


def _source_features(geojson: dict, config: CoverageConfig) -> list[dict]:
    if geojson.get("type") != "FeatureCollection":
        raise ValueError("Ward geography must be a GeoJSON FeatureCollection")
    features = geojson.get("features")
    if not isinstance(features, list) or len(features) != config.expected_feature_count:
        raise ValueError("Ward geography feature count differs from the reviewed contract")
    ward_ids = []
    for feature in features:
        if feature.get("type") != "Feature" or not feature.get("geometry"):
            raise ValueError("Ward geography contains an invalid feature")
        ward_id = feature.get("properties", {}).get("@id")
        if not isinstance(ward_id, str) or not ward_id:
            raise ValueError("Ward geography feature has no stable @id")
        ward_ids.append(ward_id)
    if len(set(ward_ids)) != len(ward_ids):
        raise ValueError("Ward geography contains duplicate @id values")
    return features


def _collection(layer_id: str, title: str, features: list[dict], **metadata) -> dict:
    return {
        "type": "FeatureCollection",
        "schema_version": COVERAGE_CONFIG.schema_version,
        "layer_id": layer_id,
        "title": title,
        "geography_version": COVERAGE_CONFIG.geography_version,
        "operational_use": False,
        **metadata,
        "features": features,
    }


def build_coverage_layers(
    ward_geojson: dict,
    evidence_rows: list[dict],
    underserved_rows: list[dict],
    equity_summary: dict,
    config: CoverageConfig = COVERAGE_CONFIG,
) -> tuple[dict[str, dict], dict]:
    """Return three ward layers and a manifest while preserving unavailable values."""
    source_features = _source_features(ward_geojson, config)
    evidence = _index(evidence_rows, "E2 evidence")
    underserved = _index(underserved_rows, "E5 screen")
    ward_ids = {feature["properties"]["@id"] for feature in source_features}
    if set(evidence) != ward_ids or set(underserved) != ward_ids:
        raise ValueError("E2/E5 ward identifiers do not exactly match the reviewed geography")
    if equity_summary.get("ward_metrics_status") != ("BLOCKED_NO_VERIFIED_SECTION_WARD_CROSSWALK"):
        raise ValueError("E4 ward-metric gate differs from the reviewed contract")

    water_features = []
    booking_features = []
    field_features = []
    for source in source_features:
        ward_id = source["properties"]["@id"]
        ward_name = source["properties"].get("name") or evidence[ward_id]["ward_name"]
        geometry = deepcopy(source["geometry"])
        e2 = evidence[ward_id]
        e5 = underserved[ward_id]
        wad = e2.get("wad")
        if wad in (None, ""):
            wad_value = None
            wad_basis = "UNAVAILABLE"
            wad_status = "UNAVAILABLE_MISSING_EVIDENCE"
        else:
            wad_value = float(wad)
            # E2 moves Census 2011 values from 2009 wards to 2016 wards by building share.
            wad_basis = "DERIVED_HISTORICAL_APPROXIMATE"
            wad_status = (
                "REVIEW_REQUIRED_APPROXIMATE_2009_CROSSWALK"
                if str(e2.get("review_required", "True")).lower() == "true"
                else "APPROXIMATE_2009_CROSSWALK"
            )

        water_features.append(
            {
                "type": "Feature",
                "geometry": geometry,
                "properties": {
                    "ward_id": ward_id,
                    "ward_name": ward_name,
                    "layer_id": WATER_ACCESS,
                    "water_access_deficit_share": wad_value,
                    "value_basis": wad_basis,
                    "display_status": wad_status,
                    "reference_year": config.census_reference_year,
                    "location_status": e2["location_status"],
                    "allocation_eligible": str(e2.get("allocation_eligible", "")).lower() == "true",
                },
            }
        )
        booking_features.append(
            {
                "type": "Feature",
                "geometry": deepcopy(geometry),
                "properties": {
                    "ward_id": ward_id,
                    "ward_name": ward_name,
                    "layer_id": BOOKING_COVERAGE,
                    "observed_bookings": None,
                    "bookings_per_1000": None,
                    "value_basis": "UNAVAILABLE",
                    "display_status": "UNAVAILABLE_NO_VERIFIED_SECTION_TO_WARD_TRANSFER",
                    "allocation_eligible": False,
                },
            }
        )
        field_features.append(
            {
                "type": "Feature",
                "geometry": deepcopy(geometry),
                "properties": {
                    "ward_id": ward_id,
                    "ward_name": ward_name,
                    "layer_id": FIELD_CHECKS,
                    "field_check_candidate": e5["field_check_candidate"],
                    "observed_bookings": e5["observed_bookings"],
                    "display_status": e5["status"],
                    "reason_codes": [reason["code"] for reason in e5["reasons"]],
                    "value_basis": e5["field_check_candidate_basis"],
                    "allocation_eligible": False,
                },
            }
        )

    layers = {
        WATER_ACCESS: _collection(
            WATER_ACCESS,
            "Historical water-access evidence (Census 2011 via 2009-to-2016 ward crosswalk)",
            water_features,
            value_field="water_access_deficit_share",
            value_status="PROVISIONAL_NOT_FOR_ALLOCATION",
            source_task="E2",
        ),
        BOOKING_COVERAGE: _collection(
            BOOKING_COVERAGE,
            "Ward booking coverage (unavailable pending verified transfer)",
            booking_features,
            value_field="bookings_per_1000",
            value_status="UNAVAILABLE",
            source_task="E4",
            exact_section_metrics={
                "section_count": equity_summary["section_count"],
                "bookings": equity_summary["bookings"],
                "gini": equity_summary["gini"],
                "top_section_count": equity_summary["top_section_count"],
                "top_booking_share": equity_summary["top_booking_share"],
                "interpretation": equity_summary["interpretation"],
            },
        ),
        FIELD_CHECKS: _collection(
            FIELD_CHECKS,
            "Field-check screening status",
            field_features,
            value_field="field_check_candidate",
            value_status="DATA_REVIEW_REQUIRED",
            source_task="E5",
        ),
    }
    manifest = {
        "schema_version": config.schema_version,
        "geography_version": config.geography_version,
        "feature_count": len(source_features),
        "layers": [
            {
                "layer_id": layer_id,
                "file": f"{layer_id}.geojson",
                "feature_count": len(layers[layer_id]["features"]),
                "non_null_value_count": sum(
                    feature["properties"].get(layers[layer_id]["value_field"]) is not None
                    for feature in layers[layer_id]["features"]
                ),
                "operational_use": False,
            }
            for layer_id in LAYER_IDS
        ],
        "excluded_layers": [
            {
                "layer_id": "people_within_500m_public_tap",
                "reason": "NO_VERIFIED_PUBLIC_TAP_LOCATION_OR_SERVICE_DATA",
            }
        ],
        "interpretation": (
            "These are evidence-status views. Null means unavailable and must never be "
            "rendered as zero. No layer establishes entitlement, neglect, or allocation priority."
        ),
    }
    return layers, manifest
