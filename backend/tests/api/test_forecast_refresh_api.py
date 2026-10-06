import pytest
from conftest import auth


@pytest.mark.parametrize("path", ["/forecast/history", "/forecast/accuracy"])
def test_refresh_routes_are_paged_and_officer_only(client, path):
    assert client.get(path, headers=auth("resident")).status_code == 403
    response = client.get(path, params={"level": "city", "limit": 2}, headers=auth("officer"))
    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 2
    assert body["total"] >= len(body["items"])
    assert all(row["level"] == "city" for row in body["items"])
    assert client.get(path, params={"limit": 201}, headers=auth("officer")).status_code == 422
