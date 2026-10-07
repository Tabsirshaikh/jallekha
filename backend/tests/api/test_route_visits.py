"""Driver route test mode: three resident codes per stop of the approved plan (SIMULATION)."""

from __future__ import annotations

from conftest import auth
from test_bookings import _approve_section_plan, _today

from app.services import route_visits as rv


def test_every_code_must_be_right() -> None:
    assert rv.check_codes(["000000", "000000", "000000"]) == [True, True, True]
    assert rv.check_codes(["000000", "123456", " 000000 "]) == [True, False, True]
    assert rv.check_codes(["000000"]) == [True, False, False]


def _test_mode(client, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from app.main import app
    from app.routers import sms_outbox
    from app.services.sms import OutboxSmsSender

    box = OutboxSmsSender()
    app.dependency_overrides[sms_outbox.get_outbox] = lambda: box
    monkeypatch.delenv("AUTH_REQUIRED", raising=False)


def test_a_stop_is_visited_when_all_three_residents_give_the_code(client, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    day = _today()
    plan = _approve_section_plan(client, day)
    route = client.get(f"/plans/{plan['plan_id']}/routes?compact=true", headers=auth("officer"))
    tanker = route.json()["paths"][0]["tanker_id"]
    body = {"day": day, "tanker_id": tanker, "n": 1, "codes": ["000000"] * 3}
    # refused outside local test mode (a real deployment)
    assert client.post("/driver/route/visits", json=body, headers=auth("driver")).status_code == 404

    _test_mode(client, monkeypatch)
    wrong = client.post("/driver/route/visits", json={**body, "codes": ["000000", "1", "000000"]})
    assert wrong.status_code == 200
    assert wrong.json()["accepted"] is False and wrong.json()["codes"] == [True, False, True]
    trip = client.get(f"/driver/route?day={day}&tanker_id={tanker}").json()["trips"][0]
    assert trip["visited_at"] is None and trip["unloaded"]

    ok = client.post("/driver/route/visits", json=body).json()
    assert ok["accepted"] is True and ok["visited_at"] and ok["basis"] == "SIMULATION"
    trip = client.get(f"/driver/route?day={day}&tanker_id={tanker}").json()["trips"][0]
    assert trip["visited_at"] == ok["visited_at"]
    # the officer sees which stops each tanker visited
    seen = client.get(f"/driver/visits?day={day}").json()
    assert seen["plan_id"] == plan["plan_id"]
    assert seen["items"] == [{"tanker_id": tanker, "n": 1, "visited_at": ok["visited_at"]}]
    # a trip the tanker does not have is refused
    missing = client.post("/driver/route/visits", json={**body, "n": 999})
    assert missing.status_code == 404
