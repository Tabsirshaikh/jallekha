"""Officer-only exact-section evidence, with typed pagination."""

from conftest import auth


def test_section_checks_route_and_pagination(client):
    response = client.get("/underserved/section-checks?limit=2", headers=auth("officer"))
    assert response.status_code == 200
    body = response.json()
    assert body["total"] > 2
    assert len(body["items"]) == 2
    assert body["validation"]["train_year"] == 2024
    assert body["validation"]["test_year"] == 2025
    assert body["items"][0]["bookings_basis"] == "REAL"
    assert isinstance(body["items"][0]["field_check_candidate"], bool)
    assert (
        client.get("/underserved/section-checks?limit=0", headers=auth("officer")).status_code
        == 422
    )


def test_section_checks_authorization(client):
    assert client.get("/underserved/section-checks").status_code == 401
    for role in ("resident", "driver", "field_worker"):
        assert client.get("/underserved/section-checks", headers=auth(role)).status_code == 403
