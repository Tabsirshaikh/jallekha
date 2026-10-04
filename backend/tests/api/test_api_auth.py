"""T10 auth, errors, paging, CORS and the exported OpenAPI file."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from conftest import GATEWAY_HEADERS, ROOT, auth
from fastapi.testclient import TestClient

from app.main import app


def _error(response) -> dict:  # type: ignore[no-untyped-def]
    body = response.json()
    assert set(body) == {"error"} and set(body["error"]) == {"code", "message", "details"}
    return body["error"]


def test_no_token_is_401_and_wrong_role_is_403(client: TestClient) -> None:
    response = client.get("/atlas/wards")
    assert response.status_code == 401 and _error(response)["code"] == "unauthorized"
    response = client.get("/atlas/wards", headers={"Authorization": "Bearer nope"})
    assert response.status_code == 401
    response = client.get("/atlas/wards", headers=auth("driver"))
    assert response.status_code == 403 and _error(response)["code"] == "forbidden"
    assert client.post("/notices", json={}, headers=auth("resident")).status_code == 403
    assert client.get("/ledger/entries", headers=auth("resident")).status_code == 403
    assert client.get("/health").status_code == 200


def test_gateway_routes_need_the_gateway_credential(client: TestClient) -> None:
    sms = {"from": "+919800000999", "text": "no water"}
    assert client.post("/intake/sms", json=sms).status_code == 401
    assert client.post("/intake/sms", json=sms, headers=auth("officer")).status_code == 401
    assert client.post("/intake/sms", json=sms, headers=GATEWAY_HEADERS).status_code == 200
    bad = client.post("/intake/sms", json={"text": "no sender"}, headers=GATEWAY_HEADERS)
    assert bad.status_code == 422 and _error(bad)["code"] == "validation_error"


def test_dev_token_comes_from_the_environment(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert (
        client.get("/atlas/wards", headers={"Authorization": "Bearer dev-123"}).status_code == 401
    )
    monkeypatch.setenv("API_DEV_TOKEN", "dev-123")
    assert (
        client.get("/atlas/wards", headers={"Authorization": "Bearer dev-123"}).status_code == 200
    )


def test_approval_without_a_reason_is_rejected(client: TestClient) -> None:
    officer = auth("officer")
    blank = client.post(
        "/plans/plan-test-1/approve", json={"officer_id": "o-1", "reason": "  "}, headers=officer
    )
    assert blank.status_code == 422 and _error(blank)["code"] == "validation_error"
    missing = client.post("/plans/plan-test-1/approve", json={"officer_id": "o-1"}, headers=officer)
    assert missing.status_code == 422 and _error(missing)["code"] == "validation_error"
    unknown = client.get("/plans/nope", headers=officer)
    assert unknown.status_code == 404 and _error(unknown)["code"] == "not_found"


def test_batch_intake_keeps_per_item_status_and_checks_areas(client: TestClient) -> None:
    items = [
        {"client_id": "a", "channel": "app", "category": "no_water", "area_id": "near the temple"},
        {"client_id": "b", "channel": "app", "category": "no_water", "ward_id": "relation/0"},
        {"client_id": "c", "channel": "app", "category": "no_water", "ward_id": "relation/7848824"},
    ]
    body = client.post("/intake/batch", json={"items": items}, headers=auth("field_worker"))
    assert body.status_code == 200
    statuses = [r["status"] for r in body.json()["results"]]
    assert statuses[:2] == ["invalid", "invalid"] and statuses[2] in ("created", "merged")
    assert (
        client.post("/intake/batch", json={"oops": []}, headers=auth("resident")).status_code == 422
    )


def test_invalid_notice_is_422(client: TestClient) -> None:
    response = client.post("/notices", json={"source": "fax"}, headers=auth("officer"))
    assert response.status_code == 422 and _error(response)["code"] == "validation_error"


def test_lists_page_with_offset_limit_total(client: TestClient) -> None:
    officer = auth("officer")
    first = client.get("/atlas/wards", params={"offset": 0, "limit": 3}, headers=officer).json()
    second = client.get("/atlas/wards", params={"offset": 3, "limit": 3}, headers=officer).json()
    assert first["total"] == second["total"] and len(first["items"]) == 3
    assert first["items"][-1]["ward_id"] != second["items"][0]["ward_id"]
    assert client.get("/atlas/wards", params={"limit": 0}, headers=officer).status_code == 422


def test_cors_allows_the_frontend_origin(client: TestClient) -> None:
    response = client.options(
        "/atlas/wards",
        headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET"},
    )
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"


def test_openapi_export_is_current() -> None:
    committed = json.loads((ROOT / "docs/openapi.json").read_text(encoding="utf-8"))
    assert committed == json.loads(json.dumps(app.openapi()))


def test_no_token_or_key_is_committed() -> None:
    for path in (ROOT / ".env.example", ROOT / "backend/app/config/api.py"):
        text = Path(path).read_text(encoding="utf-8")
        assert "t-officer" not in text and "dev-123" not in text
