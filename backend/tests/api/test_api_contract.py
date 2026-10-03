"""T10 contract tests: every route answers in the shape of its docs/api_examples/ file."""

from __future__ import annotations

from typing import Any

import pytest
from conftest import GATEWAY_HEADERS, OTP_KEY, STOP, auth, conforms, example
from fastapi.testclient import TestClient

from app.routers.stores import get_delivery_store
from app.services import delivery as dl

WARD = example("atlas_ward.get")["request"]["ward_id"]
CARD_WARD = example("ward_report_card.get")["request"]["ward_id"]

GETS = [
    ("health.get", "/health", None, {}),
    ("atlas_wards.get", "/atlas/wards", "officer", {"offset": 0, "limit": 2}),
    ("atlas_ward.get", f"/atlas/wards/{WARD}", "officer", {}),
    ("equity_summary.get", "/equity/summary", "officer", {}),
    ("equity_sections.get", "/equity/sections", "officer", {"offset": 0, "limit": 2}),
    ("equity_wards.get", "/equity/wards", "officer", {"offset": 0, "limit": 2}),
    ("underserved_field_checks.get", "/underserved/field-checks", "officer", {}),
    ("coverage_layers.get", "/coverage/layers", "officer", {}),
    ("coverage_layer.get", "/coverage/layers/water_access_evidence", "officer", {}),
    ("forecast.get", "/forecast", "officer", {"level": "city"}),
    ("forecast_backtest.get", "/forecast/backtest", "officer", {}),
    ("explain_ward.get", f"/explain/wards/{WARD}", "resident", {}),
    ("ward_report_card.get", f"/wards/{CARD_WARD}/report-card", "resident", {}),
    ("ward_sms_summary.get", f"/wards/{CARD_WARD}/sms-summary", "resident", {"lang": "te"}),
    ("impact.get", "/impact", "officer", {"replay": "main_2025", "scenario": "tight"}),
    ("ledger_verify.get", "/ledger/verify", "officer", {}),
]


@pytest.mark.parametrize(("name", "path", "role", "params"), GETS, ids=[g[0] for g in GETS])
def test_get_routes_match_their_examples(
    client: TestClient, name: str, path: str, role: str | None, params: dict[str, Any]
) -> None:
    response = client.get(path, params=params, headers=auth(role) if role else {})
    assert response.status_code == 200, response.text
    conforms(response.json(), example(name)["response"])


def test_explanation_for_a_missing_census_ward(client: TestClient) -> None:
    ward = example("explain_ward_no_census.get")["request"]["ward_id"]
    body = client.get(f"/explain/wards/{ward}", headers=auth("officer")).json()
    conforms(body, example("explain_ward_no_census.get")["response"])
    assert body["explanation"]["status"] == "no_census_data"


def test_intake_notices_and_ledger_match_their_examples(client: TestClient) -> None:
    batch = example("intake_batch.post")
    body = client.post("/intake/batch", json=batch["request"], headers=auth("resident")).json()
    conforms(body, batch["response"])
    for name, path in (
        ("intake_sms.post", "/intake/sms"),
        ("intake_missed_call.post", "/intake/missed-call"),
    ):
        request = {
            k: "+919800000999" if "number" in str(v) else v
            for k, v in example(name)["request"].items()
        }
        response = client.post(path, json=request, headers=GATEWAY_HEADERS)
        assert response.status_code == 200, response.text
        conforms(response.json(), example(name)["response"])
    notice = example("notices.post")
    response = client.post("/notices", json=notice["request"], headers=auth("officer"))
    assert response.status_code == 200, response.text
    conforms(response.json(), notice["response"])
    entries = client.get("/ledger/entries", params={"limit": 2}, headers=auth("officer")).json()
    conforms(entries, example("ledger_entries.get")["response"])


def test_plan_routes_match_their_examples(client: TestClient) -> None:
    officer = auth("officer")
    plan = client.get("/plans/plan-test-1", headers=officer).json()
    conforms(plan, example("plan.get")["response"])
    assert plan["flags"] and plan["flags_total"] == len(plan["flags"])
    conf = client.get("/plans/plan-test-1/confidence", headers=officer).json()
    conforms(conf, example("plan_confidence.get")["response"])
    assert {g["group"] for g in conf["groups"]} == {"ward:relation/7848824", "section:LOST"}
    blocked = client.post(
        "/plans/plan-test-1/approve",
        json={"officer_id": "officer-7", "reason": "ok"},
        headers=officer,
    )
    assert blocked.status_code == 409
    conforms(blocked.json(), example("plan_approve.post")["response"]["body"])
    group = sorted(plan["flags"])[0]
    checked = client.post(
        f"/plans/plan-test-1/groups/{group}/check",
        json={"officer_id": "officer-7", "reason": "Checked the section list on site"},
        headers=officer,
    )
    assert checked.status_code == 200, checked.text
    conforms(checked.json(), example("plan_check.post")["response"])
    assert checked.json()["ledger_event"] == "ward_reviewed"
    approved = client.post(
        "/plans/plan-test-1/approve",
        json={"officer_id": "officer-7", "reason": "All flagged groups checked"},
        headers=officer,
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "APPROVED"
    waiting = plan["stations"]["S1"]["waiting"][0]
    booking = client.get(f"/explain/bookings/{waiting}", headers=auth("resident")).json()
    conforms(booking, example("explain_booking.get")["response"])
    assert booking["explanation"]["status"] == "waiting"


def test_contest_routes_match_their_examples(client: TestClient) -> None:
    filed = client.post(
        "/contests", json=example("contests.post")["request"], headers=auth("resident")
    )
    assert filed.status_code == 200, filed.text
    conforms(filed.json(), example("contests.post")["response"])
    reply = {k: v for k, v in example("contest_reply.post")["request"].items() if k != "contest_id"}
    answered = client.post(
        f"/contests/{filed.json()['contest_id']}/reply", json=reply, headers=auth("officer")
    )
    assert answered.status_code == 200, answered.text
    conforms(answered.json(), example("contest_reply.post")["response"])
    again = client.post(
        f"/contests/{filed.json()['contest_id']}/reply", json=reply, headers=auth("officer")
    )
    assert again.status_code == 409


def test_delivery_routes_match_their_examples(client: TestClient) -> None:
    driver = auth("driver")
    started = client.post(
        "/deliveries",
        json={"delivery_id": "dlv-1", "stop_id": "stop-0001", "driver_id": "driver-03"},
        headers=driver,
    )
    assert started.status_code == 200, started.text
    conforms(started.json(), example("delivery_start.post")["response"])
    otp = client.post("/deliveries/dlv-1/otp", json={"representative_id": "rep-01"}, headers=driver)
    assert otp.status_code == 200, otp.text
    conforms(otp.json(), example("delivery_otp_request.post")["response"])
    assert "code" not in otp.text and "nonce" not in otp.text
    store = client.app.dependency_overrides[get_delivery_store]()
    code = dl.issued_code(store.deliveries["dlv-1"], OTP_KEY)
    verify_examples = example("delivery_otp_verify.post")["response"]
    far = client.post(
        "/deliveries/dlv-1/otp/verify",
        json={"code": code, "lat": STOP[0] + 0.01, "lon": STOP[1]},
        headers=driver,
    ).json()
    conforms(far, verify_examples[0])
    assert far["result"] == "outside_geofence"
    near = client.post(
        "/deliveries/dlv-1/otp/verify",
        json={"code": code, "lat": STOP[0], "lon": STOP[1]},
        headers=driver,
    ).json()
    conforms(near, verify_examples[1])
    assert near["result"] == "verified" and near["delivery"]["sampled_residents"] > 0
    pending = client.get("/deliveries/dlv-1", headers=auth("officer")).json()
    assert pending["outcome_status"] == "pending"
    state = store.deliveries["dlv-1"]
    phones = {r.id: r.phone for r in store.stops["stop-0001"].residents}
    for i, rid in enumerate(state.sampled_resident_ids):
        reply = client.post(
            "/deliveries/dlv-1/replies",
            json={"from": phones[rid], "text": "2" if i == 2 else "1"},
            headers=GATEWAY_HEADERS,
        )
        assert reply.status_code == 200, reply.text
        conforms(reply.json(), example("delivery_reply.post")["response"])
        assert reply.json()["replies"][0]["counted"] is True
    final = client.get("/deliveries/dlv-1", headers=auth("officer")).json()
    conforms(final, example("delivery_outcome.get")["response"])
    assert final["outcome_status"] == "Confirmed" and final["counts_toward_debt"] is True
    assert "+91" not in str(final)


def test_shortage_is_unavailable_until_t8_merges(client: TestClient) -> None:
    body = client.get("/shortage", headers=auth("officer")).json()
    assert body["total"] == len(body["items"])
    if body["total"] == 0:
        assert body["basis"] == "UNAVAILABLE" and body["reason"]
