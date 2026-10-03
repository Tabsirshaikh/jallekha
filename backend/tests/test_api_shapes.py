"""docs/api_shapes.md examples: valid JSON, labelled, and true to the routes and files on main."""

from __future__ import annotations

import csv
import json
import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.auth import get_api_config
from app.config.api import ApiConfig
from app.db import create_all, make_engine
from app.main import app
from app.routers.intake import get_intake_service
from app.routers.ledger import get_ledger_dependency
from app.routers.notices import get_notice_service
from app.services import intake_pipeline as ip
from app.services import notices as nt
from app.services.ledger_store import StoredLedger
from app.services.sms import FakeSmsSender

ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = ROOT / "docs/api_examples"
STATUSES = ("ROUTE_ON_MAIN", "FROM_MAIN", "PROPOSED", "NOT DESIGNED")
PLACEHOLDER = "<sender's number; never stored or echoed>"


def _load(name: str) -> dict[str, Any]:
    return json.loads((EXAMPLES / f"{name}.json").read_text(encoding="utf-8"))


def _shape(value: Any) -> Any:
    """Keys at every level; a list is described by the union of its items' shapes. A ledger
    `payload` is an object whose keys depend on the event type, so only its presence counts."""
    if isinstance(value, dict):
        return {key: "object" if key == "payload" else _shape(item) for key, item in value.items()}
    if isinstance(value, list):
        merged: dict[str, Any] = {}
        for item in value:
            shape = _shape(item)
            if isinstance(shape, dict):
                merged.update(shape)
        return [merged] if merged else []
    return None


def test_every_example_is_valid_labelled_json_without_phone_numbers() -> None:
    files = sorted(EXAMPLES.glob("*.json"))
    assert files
    for path in files:
        text = path.read_text(encoding="utf-8")
        body = json.loads(text)
        meta = body["_example"]
        assert meta["endpoint"] and meta["status"].startswith(STATUSES), path.name
        assert set(body) == {"_example", "request", "response"}, path.name
        if meta["status"] == "NOT DESIGNED":
            assert body["response"] is None and meta["basis"] is None, path.name
        else:
            assert meta["basis"] and meta["built_from"], path.name
        # An Indian mobile number, not digits inside a decimal or a longer number.
        phone = r"(?<![\d.])(?:\+?91)?[6-9]\d{9}(?![\d.])"
        assert not re.search(phone, text), path.name


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    engine = make_engine(f"sqlite:///{(tmp_path / 'shapes.db').as_posix()}")
    create_all(engine)
    ledger = StoredLedger(engine, keyring={"k1": "test-key"}, key_id="k1")
    intake = ip.IntakeService(
        engine,
        sms=FakeSmsSender(),
        transcriber=ip.FallbackTranscriber(),
        audio_store=ip.LocalAudioStore(tmp_path / "audio"),
        phone_hash_key="test-phone-key",
        ledger=ledger,
    )
    app.dependency_overrides[get_intake_service] = lambda: intake
    app.dependency_overrides[get_notice_service] = lambda: nt.NoticeService(engine, ledger=ledger)
    app.dependency_overrides[get_ledger_dependency] = lambda: ledger
    app.dependency_overrides[get_api_config] = lambda: ApiConfig(
        tokens={"t-officer": "officer", "t-resident": "resident"}, gateway_token="t-gateway"
    )
    yield TestClient(app)
    app.dependency_overrides.clear()
    engine.dispose()


def _real(value: Any) -> Any:
    """Swap the documented placeholder for a placeholder number the service accepts."""
    if isinstance(value, dict):
        return {k: ("+910000000000" if v == PLACEHOLDER else _real(v)) for k, v in value.items()}
    return value


def test_documented_fields_of_merged_routes_match_what_they_return(client: TestClient) -> None:
    officer = {"Authorization": "Bearer t-officer"}
    calls = [
        ("health.get", "GET", "/health", {}),
        ("intake_batch.post", "POST", "/intake/batch", {"Authorization": "Bearer t-resident"}),
        ("intake_sms.post", "POST", "/intake/sms", {"X-Gateway-Token": "t-gateway"}),
        (
            "intake_missed_call.post",
            "POST",
            "/intake/missed-call",
            {"X-Gateway-Token": "t-gateway"},
        ),
        ("notices.post", "POST", "/notices", officer),
        ("ledger_entries.get", "GET", "/ledger/entries", officer),
        ("ledger_verify.get", "GET", "/ledger/verify", officer),
    ]
    for name, method, path, headers in calls:
        example = _load(name)
        assert example["_example"]["status"] == "ROUTE_ON_MAIN", name
        if method == "POST":
            response = client.post(path, json=_real(example["request"]), headers=headers)
        else:
            response = client.get(path, params=example["request"] or {}, headers=headers)
        assert response.status_code == 200, (name, response.text)
        assert _shape(response.json()) == _shape(example["response"]), name


def _typed(row: dict[str, str]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in row.items():
        if value == "":
            out[key] = None
        elif value in ("True", "False"):
            out[key] = value == "True"
        else:
            try:
                out[key] = int(value)
            except ValueError:
                try:
                    out[key] = float(value)
                except ValueError:
                    out[key] = value
    return out


def test_examples_built_from_files_on_main_equal_their_source_rows() -> None:
    checked = 0
    for path in sorted(EXAMPLES.glob("*.json")):
        body = json.loads(path.read_text(encoding="utf-8"))
        source = body["_example"].get("source")
        if not source:
            continue
        with (ROOT / source["file"]).open(encoding="utf-8-sig", newline="") as handle:
            rows = {r[source["key_column"]]: _typed(r) for r in csv.DictReader(handle)}
        response = body["response"]
        shown = response.get("items") or [response.get("evidence") or response.get("explanation")]
        for key in source["keys"]:
            item = next(i for i in shown if i.get(source["key_column"]) == key)
            expected = rows[key]
            common = set(item) & set(expected)
            assert common, (path.name, key)
            assert {k: item[k] for k in common} == {k: expected[k] for k in common}, path.name
            checked += 1
    assert checked >= 5
