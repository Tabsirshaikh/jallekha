"""F10 candidate critical stops from D9 (item 15): OSM facilities in a ward, for an officer to
confirm. The route only reads committed data; nothing becomes a stop without the officer."""

from __future__ import annotations

import csv
from pathlib import Path

from conftest import auth, conforms, example
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[3]
WARD = example("facility_candidates.get")["request"]["ward_id"]
CATEGORIES = {"hospitals", "clinics", "uphcs", "schools", "care_homes"}


def _counts(ward_id: str) -> dict[str, str]:
    with (ROOT / "data/derived/evidence/ward_facilities.csv").open(encoding="utf-8") as handle:
        return next(r for r in csv.DictReader(handle) if r["ward_id"] == ward_id)


def test_officer_sees_every_mapped_facility_of_the_ward_as_a_candidate(client: TestClient) -> None:
    response = client.get(
        "/facilities/candidates", params={"ward_id": WARD, "limit": 200}, headers=auth("officer")
    )
    assert response.status_code == 200, response.text
    body = response.json()
    counts = _counts(WARD)
    assert body["total"] == int(counts["critical_facilities"]) == len(body["items"])
    assert body["counts"] == {c: int(counts[c]) for c in CATEGORIES}
    assert body["status"] == "CANDIDATE_OFFICER_CONFIRMATION_REQUIRED"
    assert (body["counts_basis"], body["placement_basis"]) == ("REAL", "DERIVED")
    for item in body["items"]:
        assert item["category"] in CATEGORIES
        assert item["ward_id"] == WARD
        assert item["osm_ref"] == f"{item['osm_type']}/{item['osm_id']}"
        assert item["osm_url"] == f"https://www.openstreetmap.org/{item['osm_ref']}"
        assert (item["basis"], item["ward_basis"]) == ("REAL", "DERIVED")
    # Hospitals first, then the other categories, so the likeliest tier-0 stops lead.
    order = ["hospitals", "uphcs", "clinics", "care_homes", "schools"]
    ranks = [order.index(i["category"]) for i in body["items"]]
    assert ranks == sorted(ranks)


def test_route_matches_its_example(client: TestClient) -> None:
    params = {"ward_id": WARD, "offset": 0, "limit": 2}
    body = client.get("/facilities/candidates", params=params, headers=auth("officer")).json()
    conforms(body, example("facility_candidates.get")["response"])


def test_a_name_that_looks_like_a_number_stays_text(client: TestClient) -> None:
    body = client.get(
        "/facilities/candidates", params={"ward_id": WARD, "limit": 200}, headers=auth("officer")
    ).json()
    assert all(item["name"] is None or isinstance(item["name"], str) for item in body["items"])


def test_only_officers_and_only_known_wards(client: TestClient) -> None:
    params = {"ward_id": WARD}
    for role in ("resident", "driver", "field_worker"):
        assert (
            client.get("/facilities/candidates", params=params, headers=auth(role)).status_code
            == 403
        )
    missing = client.get(
        "/facilities/candidates", params={"ward_id": "relation/0"}, headers=auth("officer")
    )
    assert missing.status_code == 404
