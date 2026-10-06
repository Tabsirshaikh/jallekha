import pytest
from conftest import auth


def test_range_reliability_can_be_read_without_loading_every_backtest_row(client):
    result = client.get(
        "/forecast/backtest", params={"row_type": "city_coverage"}, headers=auth("officer")
    )
    assert result.status_code == 200
    assert result.json()["total"] == 2
    assert all(r["row_type"] == "city_coverage" for r in result.json()["items"])


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


def test_shortage_requested_window_excludes_past_months(client):
    result = client.get(
        "/shortage",
        params={"from_month": "2026-11", "through_month": "2027-01", "limit": 200},
        headers=auth("officer"),
    )
    assert result.status_code == 200
    assert result.json()["total"] == 273 * 3
    assert all("2026-11" <= r["month"] <= "2027-01" for r in result.json()["items"])
    assert (
        client.get(
            "/shortage", params={"from_month": "invalid"}, headers=auth("officer")
        ).status_code
        == 422
    )
