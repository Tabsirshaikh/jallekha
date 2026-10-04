"""Stops (register, list, read) and the delivery list over the database-backed delivery store.

The last test registers a stop as the officer and runs it as the driver through every route,
with a new store instance for each request (as after a restart). All data here is SYNTHETIC.
"""

from __future__ import annotations

import copy
import sqlite3
from pathlib import Path
from typing import Any

import pytest
from conftest import GATEWAY_HEADERS, auth, conforms, example
from fastapi.testclient import TestClient

from app.db import make_engine
from app.routers import deliveries
from app.routers.stores import DeliveryStore, get_delivery_store
from app.services import delivery as dl
from app.services.sms import FakeSmsSender

NEW_STOP: dict[str, Any] = {
    "stop_id": "stop-0100",
    "lat": 17.4500,
    "lon": 78.5000,
    "basis": "SYNTHETIC",
    "representatives": [
        {"id": "rep-11", "phone": "+919800001101", "language": "te"},
        {"id": "rep-12", "phone": "+919800001102", "language": "ur"},
    ],
    "residents": [
        {"id": f"res-1{i}", "phone": f"+91980000120{i}", "language": "hi"} for i in range(1, 6)
    ],
}
PHONES = [p["phone"] for p in NEW_STOP["representatives"] + NEW_STOP["residents"]]


def _no_phones(text: str) -> None:
    assert "+91" not in text  # conftest's stop uses +91 numbers too
    assert not any(phone[-10:] in text for phone in PHONES)


def _stop(**changes: Any) -> dict[str, Any]:
    body = copy.deepcopy(NEW_STOP)
    body.update(changes)
    return body


def _register(client: TestClient, body: dict[str, Any] | None = None) -> Any:
    return client.post("/stops", json=body or NEW_STOP, headers=auth("officer"))


# --- stops -----------------------------------------------------------------------------------


def test_officer_registers_a_stop_and_no_phone_comes_back(client: TestClient) -> None:
    created = _register(client)
    assert created.status_code == 200, created.text
    body = created.json()
    assert body["stop_id"] == "stop-0100" and body["basis"] == "SYNTHETIC"
    assert (body["lat"], body["lon"]) == (17.45, 78.5)
    assert (body["representatives_count"], body["residents_count"]) == (2, 5)
    assert body["representatives"] == [
        {"id": "rep-11", "language": "te", "phone_last2": "01"},
        {"id": "rep-12", "language": "ur", "phone_last2": "02"},
    ]
    _no_phones(created.text)
    for role in ("officer", "driver"):
        listed = client.get("/stops", headers=auth(role))
        assert listed.status_code == 200, listed.text
        assert listed.json()["total"] == 2
        assert [s["stop_id"] for s in listed.json()["items"]] == ["stop-0001", "stop-0100"]
        _no_phones(listed.text)
        one = client.get("/stops/stop-0100", headers=auth(role))
        assert one.status_code == 200 and one.json() == body
        _no_phones(one.text)


def test_stop_list_pages(client: TestClient) -> None:
    _register(client)
    page = client.get("/stops", params={"offset": 1, "limit": 1}, headers=auth("driver")).json()
    assert (page["total"], page["offset"], page["limit"]) == (2, 1, 1)
    assert [s["stop_id"] for s in page["items"]] == ["stop-0100"]
    assert client.get("/stops", params={"limit": 0}, headers=auth("driver")).status_code == 422


def test_stop_routes_check_roles(client: TestClient) -> None:
    assert client.post("/stops", json=NEW_STOP).status_code == 401
    for role in ("driver", "resident", "field_worker"):
        assert client.post("/stops", json=NEW_STOP, headers=auth(role)).status_code == 403
    assert client.get("/stops").status_code == 401
    assert client.get("/stops/stop-0001").status_code == 401
    for role in ("resident", "field_worker"):
        assert client.get("/stops", headers=auth(role)).status_code == 403
        assert client.get("/stops/stop-0001", headers=auth(role)).status_code == 403


def test_unknown_stop_is_404(client: TestClient) -> None:
    missing = client.get("/stops/stop-9999", headers=auth("officer"))
    assert missing.status_code == 404 and missing.json()["error"]["code"] == "not_found"


def _rep(i: int, **changes: Any) -> dict[str, Any]:
    return {"id": f"rep-x{i}", "phone": f"+91980000130{i}", "language": "te", **changes}


INVALID = {
    "one_representative": _stop(representatives=[_rep(1)]),
    "four_representatives": _stop(representatives=[_rep(i) for i in range(1, 5)]),
    "no_representatives": _stop(representatives=[]),
    "phone_not_e164": _stop(representatives=[_rep(1, phone="98000 01301"), _rep(2)]),
    "phone_letters": _stop(representatives=[_rep(1, phone="+91980000ABCD"), _rep(2)]),
    "phone_not_text": _stop(representatives=[_rep(1, phone=919800001301), _rep(2)]),
    "resident_phone_bad": _stop(
        residents=[*NEW_STOP["residents"][:4], {"id": "r9", "phone": "55555", "language": "te"}]
    ),
    "latitude_out_of_range": _stop(lat=91.0),
    "longitude_out_of_range": _stop(lon=-181.0),
    "latitude_missing": {k: v for k, v in NEW_STOP.items() if k != "lat"},
    "basis_unknown": _stop(basis="MAYBE"),
    "basis_missing": {k: v for k, v in NEW_STOP.items() if k != "basis"},
    "too_few_residents": _stop(residents=NEW_STOP["residents"][:2]),
    "duplicate_representative_ids": _stop(representatives=[_rep(1), _rep(2, id="rep-x1")]),
    "duplicate_resident_ids": _stop(
        residents=[
            *NEW_STOP["residents"][:4],
            {**NEW_STOP["residents"][0], "phone": "+919800001299"},
        ]
    ),
    "duplicate_resident_phones": _stop(
        residents=[*NEW_STOP["residents"][:4], {**NEW_STOP["residents"][0], "id": "res-99"}]
    ),
    "language_unsupported": _stop(representatives=[_rep(1, language="xx"), _rep(2)]),
    "stop_id_blank": _stop(stop_id=""),
    "stop_id_spaces": _stop(stop_id="stop 1"),
    "representative_id_too_long": _stop(representatives=[_rep(1, id="r" * 37), _rep(2)]),
    "unknown_field": _stop(note="extra"),
}


@pytest.mark.parametrize("case", sorted(INVALID))
def test_invalid_stop_is_422_and_echoes_no_phone(client: TestClient, case: str) -> None:
    response = _register(client, INVALID[case])
    assert response.status_code == 422, response.text
    assert response.json()["error"]["code"] == "validation_error"
    for person in INVALID[case]["representatives"] + INVALID[case]["residents"]:
        digits = "".join(ch for ch in str(person["phone"]) if ch.isdigit())
        assert digits not in response.text
    assert client.get("/stops/stop-0100", headers=auth("officer")).status_code == 404


def test_taken_stop_or_representative_id_is_409(client: TestClient) -> None:
    assert _register(client).status_code == 200
    again = _register(client)
    assert again.status_code == 409 and again.json()["error"]["code"] == "conflict"
    reused = _register(client, _stop(stop_id="stop-0101"))  # rep-11 / rep-12 belong to stop-0100
    assert reused.status_code == 409
    _no_phones(reused.text)
    assert client.get("/stops/stop-0101", headers=auth("officer")).status_code == 404


# --- delivery list ---------------------------------------------------------------------------


def _start(client: TestClient, delivery_id: str, stop_id: str, driver_id: str) -> None:
    started = client.post(
        "/deliveries",
        json={"delivery_id": delivery_id, "stop_id": stop_id, "driver_id": driver_id},
        headers=auth("driver"),
    )
    assert started.status_code == 200, started.text


def test_delivery_list_filters_and_pages(client: TestClient) -> None:
    _register(client)
    _start(client, "dlv-a", "stop-0001", "driver-1")
    _start(client, "dlv-b", "stop-0100", "driver-2")
    _start(client, "dlv-c", "stop-0100", "driver-1")

    def ids(**params: Any) -> list[str]:
        response = client.get("/deliveries", params=params, headers=auth("officer"))
        assert response.status_code == 200, response.text
        return [item["delivery_id"] for item in response.json()["items"]]

    assert ids() == ["dlv-a", "dlv-b", "dlv-c"]
    assert ids(driver_id="driver-1") == ["dlv-a", "dlv-c"]
    assert ids(stop_id="stop-0100") == ["dlv-b", "dlv-c"]
    assert ids(driver_id="driver-1", stop_id="stop-0100") == ["dlv-c"]
    assert ids(outcome_status="pending") == ["dlv-a", "dlv-b", "dlv-c"]
    assert ids(outcome_status="Confirmed") == []
    page = client.get("/deliveries", params={"offset": 1, "limit": 1}, headers=auth("driver"))
    assert page.status_code == 200
    body = page.json()
    assert (body["total"], body["offset"], body["limit"]) == (3, 1, 1)
    assert [item["delivery_id"] for item in body["items"]] == ["dlv-b"]
    conforms(body["items"][0], example("delivery_start.post")["response"])
    _no_phones(page.text)
    bad = client.get("/deliveries", params={"outcome_status": "Lost"}, headers=auth("officer"))
    assert bad.status_code == 422
    assert client.get("/deliveries").status_code == 401
    assert client.get("/deliveries", headers=auth("resident")).status_code == 403


# --- end to end: registered by the officer, run by the driver, across restarts ---------------


def _cells(path: Path) -> list[tuple[str, str, str]]:
    """Every non-empty cell of the database file as (table, column, text)."""
    out = []
    with sqlite3.connect(path) as db:
        tables = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        for table in tables:
            cursor = db.execute(f'SELECT * FROM "{table}"')  # names come from sqlite_master
            columns = [d[0] for d in cursor.description]
            for row in cursor:
                out.extend((table, c, str(v)) for c, v in zip(columns, row, strict=True) if v)
    return out


def test_registered_stop_runs_end_to_end_across_restarts(
    client: TestClient, tmp_path: Path
) -> None:
    db_file = tmp_path / "api.db"  # the client fixture's database
    engine = make_engine(f"sqlite:///{db_file.as_posix()}")
    sms = FakeSmsSender()
    # A brand-new store for every request: nothing may survive in memory between calls.
    client.app.dependency_overrides[get_delivery_store] = lambda: DeliveryStore(engine)
    client.app.dependency_overrides[deliveries.get_delivery_sms] = lambda: sms
    texts: list[str] = []
    driver = auth("driver")
    try:
        texts.append(_register(client).text)
        _start(client, "dlv-100", "stop-0100", "driver-07")
        otp = client.post(
            "/deliveries/dlv-100/otp", json={"representative_id": "rep-12"}, headers=driver
        )
        assert otp.status_code == 200, otp.text
        texts.append(otp.text)
        assert sms.sent[-1].to == "+919800001102" and sms.sent[-1].template_key == dl.OTP_TEMPLATE
        code = sms.sent[-1].params["code"]
        far = client.post(
            "/deliveries/dlv-100/otp/verify",
            json={"code": code, "lat": 17.4600, "lon": 78.5000},
            headers=driver,
        ).json()
        assert far["result"] == "outside_geofence" and far["delivery"]["outside_tries"] == 1
        near = client.post(
            "/deliveries/dlv-100/otp/verify",
            json={"code": code, "lat": 17.4501, "lon": 78.5001},
            headers=driver,
        )
        assert near.json()["result"] == "verified", near.text
        texts += [str(far), near.text]
        asked = [m.to for m in sms.sent if m.template_key == dl.RESIDENT_CHECK_TEMPLATE]
        assert 3 <= len(asked) <= 5 and set(asked) <= set(PHONES)
        stranger = client.post(
            "/deliveries/dlv-100/replies",
            json={"from": "+919899999999", "text": "2"},
            headers=GATEWAY_HEADERS,
        ).json()
        assert stranger["replies"][0]["counted"] is False  # not sampled: counts for nothing
        for i, phone in enumerate(asked):
            reply = client.post(
                "/deliveries/dlv-100/replies",
                json={"from": phone, "text": "2" if i == len(asked) - 1 else "1"},
                headers=GATEWAY_HEADERS,
            )
            assert reply.json()["replies"][0]["counted"] is True, reply.text
            texts.append(reply.text)
        final = client.get("/deliveries/dlv-100", headers=auth("officer"))
        assert final.json()["outcome_status"] == "Confirmed", final.text
        assert final.json()["counts_toward_debt"] is True
        listed = client.get(
            "/deliveries", params={"stop_id": "stop-0100"}, headers=auth("officer")
        ).json()
        assert [i["outcome_status"] for i in listed["items"]] == ["Confirmed"]
        texts += [final.text, str(listed)]

        state = DeliveryStore(engine).get_delivery("dlv-100")
        assert state is not None and state.otp is not None
        assert state.outcome is not None and state.outcome.outcome == "Confirmed"
        for text in texts:
            _no_phones(text)
            assert state.otp.nonce not in text and state.otp.code_hash not in text
        assert '"code"' not in otp.text and code not in otp.text

        cells = _cells(db_file)  # deliveries, stops and the ledger share this database

        def where(fragment: str) -> set[tuple[str, str]]:
            return {(t, c) for t, c, v in cells if fragment in v}

        assert where(code) == set()
        assert where(state.otp.nonce) == {("delivery", "otp_nonce")}
        assert where(state.otp.code_hash) == {("delivery", "otp_code_hash")}
        for phone in PHONES:
            assert where(phone[-10:]) <= {("representative", "phone"), ("resident", "phone")}
    finally:
        engine.dispose()
