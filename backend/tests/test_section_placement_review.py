"""The reviewed hand-off must preserve identities and never invent a section point."""

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CROSSWALK = ROOT / "data/derived/crosswalk"


def read(name):
    with (CROSSWALK / name).open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def test_review_preserves_every_source_identity_and_required_schema():
    reviewed = read("section_placement_reviewed.csv")
    original = read("section_placement_best.csv")
    assert list(reviewed[0]) == [
        "section",
        "division",
        "final_status",
        "lat",
        "lng",
        "reason",
        "basis",
    ]
    keys = [(r["section"], r["division"]) for r in reviewed]
    assert len(keys) == len(set(keys))
    assert set(keys) == {(r["section"], r["division"]) for r in original}
    assert all(r["basis"] == "DERIVED" and r["reason"].strip() for r in reviewed)


def test_accepted_points_exist_in_candidates_and_unplaced_points_are_empty():
    candidates = read("section_placement_candidates.csv")
    original = {(r["section"], r["division"]): r for r in read("section_placement_best.csv")}
    for row in read("section_placement_reviewed.csv"):
        assert row["final_status"] in {"ACCEPT_AUTO", "ACCEPT_REVIEWED", "UNPLACED"}
        if row["final_status"] == "UNPLACED":
            assert row["lat"] == row["lng"] == ""
            continue
        matches = [
            r
            for r in candidates
            if (r["section"], r["division"], r["lat"], r["lng"])
            == (row["section"], row["division"], row["lat"], row["lng"])
        ]
        assert matches, row["section"]
        prior = original[(row["section"], row["division"])]
        if row["final_status"] == "ACCEPT_AUTO":
            assert prior["status"] == "ACCEPT"
            assert (row["lat"], row["lng"]) == (prior["lat"], prior["lng"])
        else:
            assert prior["status"] in {"AMBIGUOUS", "REVIEW_FAR_FROM_DIVISION"}
            assert any(r["osm_class"] == "place" and r["plausible"] == "True" for r in matches)


def test_reviewed_points_are_logged_osm_places_not_business_search_results():
    raw = json.loads(
        (ROOT / "data/raw/geography/overpass/missing_sections_places.json").read_text(
            encoding="utf-8"
        )
    )
    nodes = {f"node/{r['id']}": r for r in raw["elements"] if r["type"] == "node"}
    candidates = read("section_placement_candidates.csv")
    for row in read("section_placement_reviewed.csv"):
        if row["final_status"] != "ACCEPT_REVIEWED":
            continue
        candidate = next(
            r
            for r in candidates
            if (r["section"], r["division"], r["lat"], r["lng"], r["source"])
            == (row["section"], row["division"], row["lat"], row["lng"], "overpass")
        )
        node = nodes[candidate["osm_ref"]]
        assert node["tags"]["place"] == candidate["osm_type"]
        assert abs(node["lat"] - float(row["lat"])) <= 0.000001
        assert abs(node["lon"] - float(row["lng"])) <= 0.000001


def test_unresolved_homonyms_and_wrong_division_candidates_stay_unplaced():
    rows = {r["section"]: r for r in read("section_placement_reviewed.csv")}
    for name in (
        "MARUTHINAGAR (DIV 10)",
        "Bhagatsingh Nagar",
        "MYSARAM",
        "VAJPAYEE NAGAR",
        "VAISHALINAGAR (DIV 10)",
        "ADARSHNAGAR",
    ):
        assert rows[name]["final_status"] == "UNPLACED"
