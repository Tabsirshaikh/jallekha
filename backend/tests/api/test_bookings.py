"""Bookings made through JalLekha (services/bookings.py, routers/bookings.py)."""

from __future__ import annotations

from conftest import auth

KONDAPUR = (17.458791, 78.373056)  # the section point of KONDAPUR (DIV 15)
HAFEEZPET = (17.483441, 78.361132)


def book(client, where=KONDAPUR, phone="+919800001111", **extra):  # type: ignore[no-untyped-def]
    body = {"lat": where[0], "lon": where[1], "category": "home", "water_at_home": "no",
            "phone": phone, "language": "te", **extra}  # fmt: skip
    return client.post("/bookings", json=body, headers=auth("resident"))


def test_the_location_decides_the_section(client) -> None:  # type: ignore[no-untyped-def]
    found = client.get(
        f"/bookings/locate?lat={KONDAPUR[0]}&lon={KONDAPUR[1]}", headers=auth("resident")
    ).json()
    assert found["inside"] and found["section"] == "section:KONDAPUR (DIV 15)"
    outside = client.get("/bookings/locate?lat=12.97&lon=77.59", headers=auth("resident")).json()
    assert outside["inside"] is False
    refused = book(client, where=(12.97, 77.59))
    assert refused.status_code == 422 and "outside every HMWSSB section" in refused.text


def test_a_booking_is_saved_with_its_priority_and_without_the_phone_number(client) -> None:  # type: ignore[no-untyped-def]
    made = book(client)
    assert made.status_code == 201, made.text
    b = made.json()
    assert b["section_name"] == "KONDAPUR (DIV 15)" and b["status"] == "WAITING"
    assert b["tier"] == 1 and b["priority"].startswith("Second")  # no water at home
    assert "+91" not in made.text and b["phone_last2"] == "11"
    again = client.get(f"/bookings/{b['booking_id']}", headers=auth("resident")).json()
    assert again["booking_id"] == b["booking_id"]
    # one open booking per phone number
    assert book(client).status_code == 409
    # a home with water is in the fair turns
    other = book(client, phone="+919800002222", water_at_home="yes").json()
    assert other["tier"] == 2


def test_a_hospital_is_first_only_after_an_officer_verifies_it(client) -> None:  # type: ignore[no-untyped-def]
    no_name = book(client, category="hospital", water_at_home="yes")
    assert no_name.status_code == 422
    made = book(client, category="hospital", water_at_home="yes", facility_name="Care Clinic")
    b = made.json()
    assert b["claim_status"] == "CLAIMED" and b["tier"] == 2  # a claim is not priority yet
    listed = client.get("/bookings?claim=CLAIMED", headers=auth("officer")).json()
    assert listed["claims_to_check"] == 1 and listed["items"][0]["booking_id"] == b["booking_id"]
    assert client.get("/bookings", headers=auth("resident")).status_code == 403
    check = {"decision": "VERIFIED", "officer_id": "officer-01", "reason": "On the hospital list"}
    checked = client.post(
        f"/bookings/{b['booking_id']}/claim", json=check, headers=auth("officer")
    ).json()
    assert checked["claim_status"] == "VERIFIED" and checked["tier"] == 0
    entries = client.get("/ledger/entries?limit=200", headers=auth("officer")).json()["entries"]
    kinds = [e["event_type"] for e in entries]
    assert "booking_created" in kinds and "booking_claim_checked" in kinds
    assert "+91" not in str(entries)


def _today() -> str:
    from datetime import UTC, datetime

    from app.services.bookings import local_day

    return local_day(datetime.now(UTC)).isoformat()


def test_a_plan_for_the_day_uses_the_real_bookings_of_a_section(client) -> None:  # type: ignore[no-untyped-def]
    mine = book(client).json()
    hosp = book(client, where=HAFEEZPET, phone="+919800003333", category="hospital",
                water_at_home="yes", facility_name="Hafeezpet Clinic").json()  # fmt: skip
    check = {"decision": "VERIFIED", "officer_id": "officer-01", "reason": "Listed"}
    client.post(f"/bookings/{hosp['booking_id']}/claim", json=check, headers=auth("officer"))
    body = {"day": _today(), "unit": "section", "capacity": "tight"}
    made = client.post("/plans", json=body, headers=auth("officer"))
    assert made.status_code == 201, made.text
    plan = made.json()
    # the two sections with real bookings are planned from them alone
    totals = plan["group_totals"]
    assert (
        totals["section:KONDAPUR (DIV 15)"]["served"]
        + totals["section:KONDAPUR (DIV 15)"]["waiting"]
        == 1
    )
    assert sum(totals["section:HAFEEZPET"].values()) == 1
    served = {b["booking_id"]: b for st in plan["stations"].values() for b in st["served"]}
    assert served[hosp["booking_id"]]["reason"] == "TIER_0"  # the verified clinic goes first
    assert served[mine["booking_id"]]["reason"] == "TIER_1"  # no water at home
    facts = plan["overview"]["facts"]
    assert facts["live_bookings"] == 2 and facts["live_sections"] == 2
    assert "2 REAL bookings made through JalLekha" in plan["basis"]["plan"]
    assert "same month of 2025 stands in" in plan["basis"]["plan"]
    # every other section keeps its estimate from the monthly totals
    assert facts["bookings"] > 1000
    # a new booking makes a new plan (its id hashes the real bookings)
    book(client, phone="+919800004444")
    again = client.post("/plans", json=body, headers=auth("officer")).json()
    assert again["plan_id"] != plan["plan_id"]


def _approve_section_plan(client, day: str) -> dict:  # type: ignore[no-untyped-def]
    plan = client.post(
        "/plans", json={"day": day, "unit": "section", "capacity": "tight"}, headers=auth("officer")
    ).json()
    for group in plan["flags"]:
        client.post(
            f"/plans/{plan['plan_id']}/groups/{group}/check",
            json={"officer_id": "officer-01", "reason": "Checked"},
            headers=auth("officer"),
        )
    approved = client.post(
        f"/plans/{plan['plan_id']}/approve",
        json={"officer_id": "officer-01", "reason": "Approved for the test"},
        headers=auth("officer"),
    )
    assert approved.status_code == 200, approved.text
    return plan


def test_one_booking_from_the_form_to_the_closed_day(client) -> None:  # type: ignore[no-untyped-def]
    from conftest import GATEWAY_HEADERS, OTP_KEY

    from app.main import app
    from app.routers.stores import get_delivery_store
    from app.services import delivery as dl

    day = _today()
    phone = "+919800005555"
    booking = book(client, phone=phone).json()
    plan = _approve_section_plan(client, day)

    # the approved plan gave the booking a tanker, a trip and a stop at the booker's location
    b = client.get(f"/bookings/{booking['booking_id']}", headers=auth("resident")).json()
    assert b["status"] == "ASSIGNED" and b["plan_id"] == plan["plan_id"]
    tanker, stop_id = b["tanker_id"], f"bk-{booking['booking_id']}"
    listed = client.get(f"/driver/tankers?day={day}", headers=auth("driver")).json()
    assert tanker in {t["tanker_id"] for t in listed["items"]}
    route = client.get(f"/driver/route?day={day}&tanker_id={tanker}", headers=auth("driver"))
    body = route.json()
    # the driver's map: the filling station, and where every trip goes (the booker's own place
    # for a booking made through JalLekha)
    assert body["station"]["station_id"] == body["station_id"]
    assert body["station"]["lat"] and body["station"]["lng"]
    trip = next(t for t in body["trips"] if t["booking"])
    assert trip["group"] and trip["lat"] is not None and trip["lng"] is not None
    assert trip["stop_id"] == stop_id and trip["booking"]["booking_id"] == booking["booking_id"]

    # the driver starts the delivery; the code goes to the booker's phone
    start = {"delivery_id": "d-e2e-1", "stop_id": stop_id, "driver_id": tanker}
    assert client.post("/deliveries", json=start, headers=auth("driver")).status_code == 200
    otp = client.post(
        "/deliveries/d-e2e-1/otp", json={"representative_id": f"{stop_id}-rep"},
        headers=auth("driver"),
    )  # fmt: skip
    assert otp.status_code == 200, otp.text
    store = app.dependency_overrides[get_delivery_store]()
    code = dl.issued_code(store.get_delivery("d-e2e-1"), OTP_KEY)
    # at the door: right code, inside the geofence
    verified = client.post(
        "/deliveries/d-e2e-1/otp/verify",
        json={"code": code, "lat": booking["lat"], "lon": booking["lon"]},
        headers=auth("driver"),
    ).json()
    assert verified["result"] == "verified" and verified["delivery"]["sampled_residents"] == 1
    b = client.get(f"/bookings/{booking['booking_id']}", headers=auth("resident")).json()
    assert b["status"] == "CHECKING"
    # the booker answers "1" (yes): Confirmed, which pays water debt
    replied = client.post(
        "/deliveries/d-e2e-1/replies", json={"from": phone, "text": "1"}, headers=GATEWAY_HEADERS
    )
    assert replied.json()["replies"][0]["counted"] is True  # decided on the next read
    b = client.get(f"/bookings/{booking['booking_id']}", headers=auth("resident")).json()
    assert b["status"] == "DELIVERED" and b["delivery"]["counts_toward_debt"] is True

    # closing the day (the next morning): the section owed its one real booking and was paid
    from datetime import UTC, datetime, timedelta

    from app.routers.common import get_now

    app.dependency_overrides[get_now] = lambda: datetime.now(UTC) + timedelta(days=1)
    closed = client.post(
        f"/debt/days/{day}/close",
        json={"plan_id": plan["plan_id"], "officer_id": "officer-01", "reason": "Day over"},
        headers=auth("officer"),
    )
    assert closed.status_code == 200, closed.text
    kondapur = next(w for w in closed.json()["wards"] if w["ward_id"] == booking["section"])
    assert kondapur["planned_litres"] == 5000 and kondapur["credited_litres"] == 5000
    assert kondapur["debt_after"] == 0


def test_sms_test_mode_shows_the_code_and_takes_the_answer(client, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from app.main import app
    from app.routers import deliveries, sms_outbox
    from app.services.sms import OutboxSmsSender

    box = OutboxSmsSender()
    app.dependency_overrides[sms_outbox.get_outbox] = lambda: box
    app.dependency_overrides[deliveries.get_delivery_sms] = lambda: box
    # refused while sign-in is required (a real deployment)
    assert client.get("/sms/outbox?phone=+919800006666").status_code == 404
    monkeypatch.delenv("AUTH_REQUIRED")
    assert client.get("/sms/test-mode").json() == {"test_mode": True}

    day = _today()
    phone = "+919800006666"
    booking = book(client, phone=phone).json()
    _approve_section_plan(client, day)
    b = client.get(f"/bookings/{booking['booking_id']}").json()
    stop_id = f"bk-{booking['booking_id']}"
    client.post("/deliveries", json={"delivery_id": "d-tm-1", "stop_id": stop_id,
                                     "driver_id": b["tanker_id"]})  # fmt: skip
    client.post("/deliveries/d-tm-1/otp", json={"representative_id": f"{stop_id}-rep"})
    msgs = client.get(f"/sms/outbox?phone={phone}").json()["items"]
    code = msgs[0]["code"]
    assert code and code in msgs[0]["text"]
    client.post(
        "/deliveries/d-tm-1/otp/verify",
        json={"code": code, "lat": booking["lat"], "lon": booking["lon"]},
    )
    question = client.get(f"/sms/outbox?phone={phone}").json()["items"][0]
    assert "did you get water" in question["text"]
    answered = client.post("/sms/outbox/reply", json={"phone": phone, "text": "1"}).json()
    assert answered["counted"] and answered["delivery"]["outcome_status"] == "Confirmed"
