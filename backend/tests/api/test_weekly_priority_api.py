from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

from app.config.env import REPO_ROOT
from app.main import app
from app.routers.common import get_now
from app.routers.stores import get_delivery_store
from app.services import section_plan
from app.services.service_models import NeedWeights


def test_review_delivery_credit_unknown_and_audit(client, monkeypatch):
    app.dependency_overrides[get_now] = lambda: datetime(2026, 10, 7, tzinfo=UTC)
    info = next(iter(section_plan.load_sections(REPO_ROOT).values()))
    ident = f"{info.division}:{info.section}"
    monkeypatch.setattr(section_plan, "section_of_point", lambda *args: info.group)
    loads = []
    store = SimpleNamespace(
        list_stops=lambda: [SimpleNamespace(stop_id="real", basis="REAL", lat=0, lon=0)],
        list_deliveries=lambda **kwargs: loads,
    )
    app.dependency_overrides[get_delivery_store] = lambda: store
    headers = {"Authorization": "Bearer t-officer"}
    url = f"/field-checks/weekly-priority?section_id={ident}"
    assert client.get(url, headers=headers).json()["items"][0]["status"] == "UNKNOWN"
    payload = {
        "id": str(uuid4()),
        "section_id": ident,
        "checked_on": "2026-10-06",
        "supply": "unavailable",
        "tanker_share": 1,
        "records_complete": True,
        "booking_reason": "access_difficulty",
        "note": "Verified records and no piped supply",
    }
    result = client.post("/field-checks/supply-reviews", json=payload, headers=headers)
    assert result.status_code == 200, result.text
    assert not result.json()["ledger_missing"]
    assert (
        client.post("/field-checks/supply-reviews", json=payload, headers=headers).status_code
        == 200
    )
    first = client.get(url, headers=headers).json()["items"][0]
    assert first["shortfall_litres"] == first["weekly_requirement_litres"]
    loads.append(
        SimpleNamespace(
            stop_id="real",
            started_at=datetime(2026, 10, 6, tzinfo=UTC),
            outcome=SimpleNamespace(outcome="Confirmed"),
        )
    )
    credited = client.get(url, headers=headers).json()["items"][0]
    assert credited["confirmed_litres"] == 5000
    assert credited["shortfall_litres"] == first["shortfall_litres"] - 5000
    loads.append(SimpleNamespace(stop_id="real", outcome=None))
    assert client.get(url, headers=headers).json()["items"][0]["status"] == "UNKNOWN"
    payload["note"] = "Changed"
    assert (
        client.post("/field-checks/supply-reviews", json=payload, headers=headers).status_code
        == 422
    )


def test_current_section_plan_uses_verified_priority_and_saved_snapshot(client, monkeypatch):
    app.dependency_overrides[get_now] = lambda: datetime(2026, 10, 7, tzinfo=UTC)
    info = section_plan.load_sections(REPO_ROOT)["ADIKMET"]
    headers = {"Authorization": "Bearer t-officer"}
    review = {
        "id": str(uuid4()),
        "section_id": "5:ADIKMET",
        "checked_on": "2026-10-06",
        "supply": "adequate",
        "tanker_share": 0,
        "records_complete": True,
        "booking_reason": "other_supply",
        "note": "Piped water adequate, records checked",
    }
    assert (
        client.post("/field-checks/supply-reviews", json=review, headers=headers).status_code == 200
    )
    body = {
        "day": "2026-10-07",
        "unit": "section",
        "scheduled": "f4",
        "bookings": [
            {
                "booking_id": "current-1",
                "section": "ADIKMET",
                "arrived_at": "2026-10-07T06:00:00+05:30",
            }
        ],
    }
    response = client.post("/plans", json=body, headers=headers)
    assert response.status_code == 201, response.text
    plan = response.json()
    assert (
        plan["effective_entitlement"][info.group] == info.entitlement(NeedWeights.default()) * 1.0
    )
    ident = plan["plan_id"]
    review.update(id=str(uuid4()), supply="unavailable", tanker_share=1, note="Supply failed")
    assert (
        client.post("/field-checks/supply-reviews", json=review, headers=headers).status_code == 200
    )
    # Reopening never applies newer assessments to an already saved plan.
    reopened = client.get(f"/plans/{ident}", headers=headers).json()
    assert reopened["digest"] == plan["digest"]
    assert reopened["effective_entitlement"] == plan["effective_entitlement"]
    updated = client.post("/plans", json=body, headers=headers).json()
    assert info.group in updated["scheduled"]
    assert updated["plan_id"] != ident
    assert updated["effective_entitlement"][info.group] > plan["effective_entitlement"][info.group]

    disabled = client.post("/plans", json={**body, "scheduled": "none"}, headers=headers).json()
    assert info.group not in disabled["scheduled"]


def test_review_rejects_future_invalid_share_and_unknown_section(client):
    app.dependency_overrides[get_now] = lambda: datetime(2026, 10, 7, tzinfo=UTC)
    payload = {
        "id": str(uuid4()),
        "section_id": "5:ADIKMET",
        "checked_on": "2026-10-07",
        "supply": "adequate",
        "tanker_share": 0,
        "records_complete": True,
        "booking_reason": "other_supply",
        "note": "Checked",
    }
    headers = {"Authorization": "Bearer t-officer"}
    for change in [
        {},
        {"checked_on": "2026-10-06", "tanker_share": 0.5},
        {"checked_on": "2026-10-06", "section_id": "nonexistent"},
    ]:
        assert (
            client.post(
                "/field-checks/supply-reviews", json={**payload, **change}, headers=headers
            ).status_code
            == 422
        )


def test_current_supplied_section_day_closes_from_supplied_counts_and_atlas_reads_debt(client):
    app.dependency_overrides[get_now] = lambda: datetime(2026, 10, 7, tzinfo=UTC)
    headers = {"Authorization": "Bearer t-officer"}
    body = {
        "day": "2026-10-07",
        "unit": "section",
        "scheduled": "none",
        "bookings": [
            {
                "booking_id": "debt-1",
                "section": "ADIKMET",
                "arrived_at": "2026-10-07T06:00:00+05:30",
            }
        ],
    }
    plan = client.post("/plans", json=body, headers=headers).json()
    ident = plan["plan_id"]
    for group in plan["flags"]:
        assert (
            client.post(
                f"/plans/{ident}/groups/{group}/check",
                headers=headers,
                json={"officer_id": "officer", "reason": "Checked"},
            ).status_code
            == 200
        )
    assert (
        client.post(
            f"/plans/{ident}/approve",
            headers=headers,
            json={"officer_id": "officer", "reason": "Reviewed"},
        ).status_code
        == 200
    )
    app.dependency_overrides[get_now] = lambda: datetime(2026, 10, 8, tzinfo=UTC)
    closed = client.post(
        "/debt/days/2026-10-07/close",
        headers=headers,
        json={"plan_id": ident, "officer_id": "officer", "reason": "Closed"},
    )
    assert closed.status_code == 200, closed.text
    accounts = client.get("/debt/accounts", headers=headers).json()["items"]
    account = next(a for a in accounts if a["account_id"] == "section:ADIKMET")
    assert account["debt_litres"] == 5000
    atlas = client.get("/atlas/live-sections", headers=headers).json()["wards"]
    section = next(s for s in atlas if s["name"] == "ADIKMET")
    assert section["owed_basis"] == "SECTION_ACCOUNT"
    assert section["clues"][0]["known"] and section["clues"][0]["value"] == 1
