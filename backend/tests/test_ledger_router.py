"""T6 read-only ledger endpoints: list and verify. No update or delete."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.db import make_engine
from app.main import app
from app.models import LedgerEntryRecord
from app.routers.ledger import get_ledger_dependency
from app.services.ledger_store import StoredLedger

KEY = "test-ledger-key-1"


@pytest.fixture
def store(tmp_path: Path) -> Iterator[StoredLedger]:
    engine = make_engine(f"sqlite:///{(tmp_path / 'ledger.db').as_posix()}")
    stored = StoredLedger(engine, keyring={"k1": KEY}, key_id="k1")
    for i in range(4):
        stored.record("override", {"entity_type": "plan", "entity_id": f"p{i}", "i": i}, "o-1")
    app.dependency_overrides[get_ledger_dependency] = lambda: stored
    yield stored
    app.dependency_overrides.clear()
    engine.dispose()


def test_list_entries_in_order_with_paging(store: StoredLedger) -> None:
    client = TestClient(app)
    body = client.get("/ledger/entries").json()
    assert [e["seq"] for e in body["entries"]] == [1, 2, 3, 4]
    first = body["entries"][0]
    assert first["entity_type"] == "plan" and first["payload"]["key_id"] == "k1"
    assert set(first) >= {"seq", "event_type", "entity_id", "prev_hash", "hash", "signature"}
    page = client.get("/ledger/entries", params={"after_seq": 2, "limit": 1}).json()
    assert [e["seq"] for e in page["entries"]] == [3]
    assert client.get("/ledger/entries", params={"limit": 0}).status_code == 422


def test_verify_endpoint_reports_valid_and_broken(store: StoredLedger) -> None:
    client = TestClient(app)
    body = client.get("/ledger/verify").json()
    assert (body["valid"], body["checked"], body["head_seq"]) == (True, 4, 4)
    with Session(store.engine) as session, session.begin():
        session.execute(
            update(LedgerEntryRecord).where(LedgerEntryRecord.seq == 2).values(entity_id="x")
        )
    body = client.get("/ledger/verify").json()
    assert (body["valid"], body["broken_at"], body["reason"]) == (False, 2, "hash_mismatch")


@pytest.mark.parametrize("method", ["post", "put", "patch", "delete"])
def test_no_write_endpoints(store: StoredLedger, method: str) -> None:
    client = TestClient(app)
    assert getattr(client, method)("/ledger/entries").status_code == 405
    assert getattr(client, method)("/ledger/entries/1").status_code in (404, 405)
