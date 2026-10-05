"""D9: OSM facilities classified and placed on the 2016 wards (item 15)."""

import csv
import importlib.util
import io
import json
from pathlib import Path

import pytest
from shapely.geometry import box

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "facilities", ROOT / "scripts/evidence/build_facilities.py"
)
facilities = importlib.util.module_from_spec(spec)
spec.loader.exec_module(facilities)


@pytest.mark.parametrize(
    "tags,category",
    [
        ({"amenity": "hospital"}, "hospitals"),
        ({"healthcare": "hospital"}, "hospitals"),
        ({"amenity": "clinic"}, "clinics"),
        ({"amenity": "doctors"}, "clinics"),
        ({"healthcare": "centre"}, "clinics"),
        # Named public primary care goes to its own column, whatever the amenity tag says.
        ({"amenity": "clinic", "name": "UPHC Golconda"}, "uphcs"),
        ({"amenity": "hospital", "name": "Urban Primary Health Centre, Amberpet"}, "uphcs"),
        ({"healthcare": "clinic", "name": "Basti Dawakhana Borabanda"}, "uphcs"),
        ({"amenity": "doctors", "name": "PHC Shaikpet"}, "uphcs"),
        ({"amenity": "school"}, "schools"),
        ({"amenity": "nursing_home"}, "care_homes"),
        ({"amenity": "social_facility", "social_facility": "nursing_home"}, "care_homes"),
        ({"amenity": "social_facility", "social_facility": "group_home"}, "care_homes"),
        ({"amenity": "social_facility", "social_facility": "food_bank"}, None),
        # A name match alone (no health tag) is not a health centre.
        ({"amenity": "school", "name": "PHC Colony School"}, "schools"),
        ({"amenity": "pharmacy"}, None),
        ({}, None),
    ],
)
def test_classify(tags, category):
    assert facilities.classify(tags) == category


def test_count_by_ward_places_points_and_reports_the_rest():
    wards = [("w1", box(0, 0, 1, 1)), ("w2", box(1, 0, 2, 1))]
    points = [
        ("hospitals", 0.5, 0.5),
        ("schools", 0.2, 0.9),
        ("schools", 1.5, 0.5),
        ("clinics", 5.0, 5.0),  # outside every ward
    ]
    counts, unplaced = facilities.count_by_ward(points, wards)
    assert counts["w1"] == {"hospitals": 1, "schools": 1}
    assert counts["w2"] == {"schools": 1}
    assert unplaced == {"clinics": 1}


def test_a_point_on_a_shared_edge_counts_once():
    wards = [("w1", box(0, 0, 1, 1)), ("w2", box(1, 0, 2, 1))]
    counts, unplaced = facilities.count_by_ward([("schools", 1.0, 0.5)], wards)
    assert sum(sum(c.values()) for c in counts.values()) + sum(unplaced.values()) == 1


@pytest.fixture(scope="module")
def built():
    return facilities.build()


def _rows(artifacts):
    return list(csv.DictReader(io.StringIO(artifacts[facilities.OUTPUT].decode())))


def test_real_artifacts_are_reproducible(built):
    assert built == facilities.build()
    for path, content in built.items():
        assert (ROOT / path).read_bytes() == content


def test_every_ward_has_counts_with_a_basis(built):
    rows = _rows(built)
    assert len(rows) == len({r["ward_id"] for r in rows}) == 145
    for row in rows:
        total = sum(int(row[c]) for c in facilities.CATEGORIES)
        assert int(row["critical_facilities"]) == total
        assert row["counts_basis"] == "REAL"
        assert row["placement_basis"] == "DERIVED"


def test_summary_reconciles_every_classified_feature(built):
    summary = json.loads(built[facilities.SUMMARY])
    rows = _rows(built)
    for category in facilities.CATEGORIES:
        placed = sum(int(r[category]) for r in rows)
        assert summary["placed_in_wards"][category] == placed
        assert (
            summary["placed_in_wards"][category] + summary["outside_wards"][category]
            == summary["classified_in_bbox"][category]
        )
    # The document's totals are kept beside ours so the difference is visible, never hidden.
    assert summary["solution_doc_totals"] == {
        "hospitals": 885,
        "clinics": 310,
        "uphcs": 350,
        "schools": 399,
        "care_homes": 59,
    }


def test_points_file_lists_every_classified_feature_with_its_ward(built):
    points = list(csv.DictReader(io.StringIO(built[facilities.POINTS].decode())))
    summary = json.loads(built[facilities.SUMMARY])
    assert len(points) == sum(summary["classified_in_bbox"].values())
    assert {p["category"] for p in points} <= set(facilities.CATEGORIES)
    per_ward = {}
    for point in points:
        if point["ward_id"]:
            per_ward[point["ward_id"]] = per_ward.get(point["ward_id"], 0) + 1
    for row in _rows(built):
        assert per_ward.get(row["ward_id"], 0) == int(row["critical_facilities"])
    assert sum(not p["ward_id"] for p in points) == sum(summary["outside_wards"].values())
