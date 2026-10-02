"""Synthetic geometry fixtures test code, never establish real geographic truth."""

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "location_validation", ROOT / "scripts/evidence/location_validation.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
POLYGON = {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]]}
ROW = dict(zip(module.KEY_FIELDS, ["28", "536", "04496", "802918", "0104"], strict=True))
ROW.update(target_ward_id="test/1", target_ward_num="104")
TARGET = {
    "type": "Feature",
    "properties": {"@id": "test/1", "name": "Ward 104 Test"},
    "geometry": POLYGON,
}


def layer(**changes):
    props = {
        **ROW,
        "source_url": "https://censusindia.gov.in/example",
        "census_year": 2011,
        "reviewer_status": "approved",
        "reviewed_by": "synthetic-fixture",
        "reviewed_at": "2026-10-02",
    }
    props.update(changes)
    return {
        "type": "FeatureCollection",
        "features": [{"type": "Feature", "properties": props, "geometry": POLYGON}],
    }


def status(rows=None, targets=None, source=None):
    return module.validate(rows or [ROW], targets or [TARGET], source)[0]["location_status"]


def test_missing_source_and_centroids_cannot_validate():
    assert status() == "MISSING_CENSUS2011_WARD_POLYGON"
    assert module.geometry_status({"type": "Point", "coordinates": [0, 0]}, POLYGON) == (
        "INVALID_OR_NON_POLYGON"
    )


def test_same_number_different_geometry_requires_transfer():
    shifted = {"type": "Polygon", "coordinates": [[[2, 0], [3, 0], [3, 1], [2, 1], [2, 0]]]}
    assert module.geometry_status(shifted, POLYGON) == "BOUNDARY_TRANSFER_REQUIRED"
    assert status(source=layer()) == "VERIFIED_EXACT_GEOMETRY"


@pytest.mark.parametrize(
    "change",
    [
        {"census_year": 2026},
        {"reviewer_status": "pending"},
        {"reviewed_by": ""},
        {"source_url": "https://gov.in.example.org/fake"},
    ],
)
def test_wrong_vintage_or_unreviewed_source_is_rejected(change):
    assert status(source=layer(**change)) == "UNREVIEWED_OR_WRONG_VINTAGE_SOURCE"


def test_duplicates_and_composite_key_fail_closed():
    assert status(rows=[ROW, ROW], source=layer()) == "AMBIGUOUS_SOURCE_ASSIGNMENT"
    other = {**TARGET, "properties": {"@id": "test/2", "name": "Ward 104 Other"}}
    assert status(targets=[TARGET, other], source=layer()) == "AMBIGUOUS_TARGET_NUMBER"
    assert status(source=layer(source_subdistt_code="04497")) == ("MISSING_CENSUS2011_WARD_POLYGON")


def test_malformed_layers_and_duplicate_target_ids_rejected():
    with pytest.raises(ValueError, match="Duplicate target"):
        status(targets=[TARGET, TARGET])
    with pytest.raises(ValueError, match="FeatureCollection"):
        status(source={"type": "Point", "features": []})
    with pytest.raises(ValueError, match="CRS"):
        status(source={**layer(), "crs": {"name": "EPSG:3857"}})
    assert module.source_key({**ROW, "source_district_code": "123456"}) == ""


def test_real_e1_audit_contract():
    import csv
    import json

    with (ROOT / "data/derived/crosswalk/census_to_ghmc_2016.csv").open(
        encoding="utf-8", newline=""
    ) as handle:
        rows = list(csv.DictReader(handle))
    assert all(module.source_key(r) for r in rows)
    assert len({module.source_key(r) for r in rows}) == len(rows)
    hyd = [r for r in rows if r["source_district"] == "Hyderabad"]
    assert {r["source_original_district_code"] for r in hyd} == {"22"}
    assert {r["source_district_code"] for r in hyd} == {"536"}
    assert len({r["source_subdistt_code"] for r in hyd}) == 16
    assert sum(int(r["source_tot_p"]) for r in hyd) == 3943323
    assert all(r["reviewer_status"] != "verified" for r in rows)
    assert all(r["match_confidence"] != "high" for r in rows)
    assert all(float(r["one_to_many_weight"]) == 0 for r in rows)
    assert all(not r["target_ward_id"] for r in rows if r["source_ward_num"] == "37")
    summary = json.loads((ROOT / "data/derived/crosswalk/crosswalk_summary.json").read_text())
    assert summary["validated_location_count"] == 0
    assert summary["candidate_target_polygon_count"] == 139
    assert summary["unmatched_target_polygon_count"] == 6
    assert sum(summary["location_status_counts"].values()) == 162
    with (ROOT / "data/derived/crosswalk/census_mandal_context.csv").open(
        encoding="utf-8", newline=""
    ) as handle:
        context = list(csv.DictReader(handle))
    assert len([r for r in context if r["district"] == "Hyderabad"]) == 16
    assert all(
        r["target_ward_id"] == "" and r["target_mapping_status"] == "NOT_JOINED" for r in context
    )


def test_pca_counts_and_zone_table(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "scripts/evidence"))
    import build_crosswalk as crosswalk

    for invalid in ("", None, -1, "3.5", "nan", "NA"):
        with pytest.raises(ValueError):
            crosswalk.required_count(invalid, "TOT_P")
    assert crosswalk.required_count("0", "TOT_P") == 0
    assert crosswalk.required_count("123.0", "TOT_P") == 123
    zones = crosswalk.parse_readme_zone_map()
    assert zones[1]["zone"] == "East Zone"
    assert zones[91]["zone"] == "Central Zone"
    assert len(zones) == 149  # README includes names for several missing polygons.


def test_invalid_and_duplicate_source_geometry():
    bowtie = {"type": "Polygon", "coordinates": [[[0, 0], [1, 1], [0, 1], [1, 0], [0, 0]]]}
    assert module.geometry_status(bowtie, POLYGON) == "INVALID_OR_NON_POLYGON"
    duplicate = layer()
    duplicate["features"] *= 2
    assert status(source=duplicate) == "AMBIGUOUS_SOURCE_POLYGONS"
