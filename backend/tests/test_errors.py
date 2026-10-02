from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.errors import install_error_handlers
from app.main import app


def _probe_app() -> FastAPI:
    probe = FastAPI()
    install_error_handlers(probe)

    @probe.get("/items/{item_id}")
    def get_item(item_id: int) -> dict[str, int]:
        if item_id == 0:
            raise HTTPException(status_code=409, detail="Item is locked")
        return {"item_id": item_id}

    @probe.get("/boom")
    def boom() -> None:
        raise RuntimeError("unexpected")

    return probe


def test_unknown_route_uses_error_shape() -> None:
    response = TestClient(app).get("/does-not-exist")
    assert response.status_code == 404
    assert response.json() == {
        "error": {"code": "not_found", "message": "Not Found", "details": None}
    }


def test_http_exception_keeps_message() -> None:
    response = TestClient(_probe_app()).get("/items/0")
    assert response.status_code == 409
    assert response.json()["error"] == {
        "code": "conflict",
        "message": "Item is locked",
        "details": None,
    }


def test_validation_error_lists_details() -> None:
    response = TestClient(_probe_app()).get("/items/not-a-number")
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "validation_error"
    assert error["details"][0]["loc"] == ["path", "item_id"]


def test_unhandled_error_hides_internals() -> None:
    response = TestClient(_probe_app(), raise_server_exceptions=False).get("/boom")
    assert response.status_code == 500
    assert response.json() == {
        "error": {"code": "internal_error", "message": "Internal server error", "details": None}
    }
