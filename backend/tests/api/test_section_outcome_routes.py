"""Field/officer access and durable observations through the ground-truth API."""

from uuid import uuid4

from conftest import auth


def test_flagged_list_and_record_round_trip(client):
    response = client.get("/field-checks/sections", headers=auth("field_worker"))
    assert response.status_code == 200
    row = response.json()["items"][0]
    payload = {
        "id": str(uuid4()),
        "section_id": row["section_id"],
        "could_not_book": "yes",
        "checked_on": "2026-10-02",
        "note": "People could not book",
    }
    response = client.post("/field-checks/outcomes", json=payload, headers=auth("field_worker"))
    assert response.status_code == 200, response.text
    assert response.json()["ledger_missing"] is False
    assert response.json()["recorded_by"] == "field_worker"
    summary = client.get("/field-checks/summary", headers=auth("officer")).json()
    assert summary["decisive_sections"] == 1
    assert summary["precision"] is None
    assert (
        client.post("/field-checks/outcomes", json=payload, headers=auth("field_worker")).json()
        == response.json()
    )
    assert client.get("/field-checks/outcomes", headers=auth("officer")).json()["total"] == 1


def test_authorization_and_validation(client):
    for path in ("/field-checks/sections", "/field-checks/outcomes", "/field-checks/summary"):
        assert client.get(path).status_code == 401
        assert client.get(path, headers=auth("resident")).status_code == 403
        assert client.get(path, headers=auth("driver")).status_code == 403
    payload = {
        "id": str(uuid4()),
        "section_id": "not-flagged",
        "could_not_book": "yes",
        "checked_on": "2026-10-02",
        "note": "",
    }
    assert (
        client.post("/field-checks/outcomes", json=payload, headers=auth("officer")).status_code
        == 422
    )
    assert (
        client.post("/field-checks/outcomes", json=payload, headers=auth("resident")).status_code
        == 403
    )
