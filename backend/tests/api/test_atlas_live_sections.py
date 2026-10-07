"""GET /atlas/live-sections: the live clues per HMWSSB section, in the shape of /atlas/live."""

from conftest import auth


def test_live_sections_have_need_and_the_same_five_clues(client) -> None:
    body = client.get("/atlas/live-sections", headers=auth("officer")).json()
    assert body["unit"] == "section" and body["window_days"] == 30
    sections = body["wards"]
    assert len(sections) == 170  # sections with a building-weighted need estimate
    s = next(x for x in sections if x["name"] == "NALLAGANDLA (DIV 15)")
    n = s["need"]
    assert n["need_weight"] == round(1 + 2 * n["wad"] + n["cad"] + n["hardship"], 4)
    assert [c["code"] for c in s["clues"]] == [
        "owed",
        "bookings",
        "complaints",
        "cuts",
        "groundwater",
    ]
    assert s["usual_month_bookings"] > 0 and s["bookings_window"] == 0
    assert body["concentration"]["source"] == "history"


def test_live_sections_need_an_officer(client) -> None:
    assert client.get("/atlas/live-sections").status_code == 401
    assert client.get("/atlas/live-sections", headers=auth("resident")).status_code == 403


def test_complaints_with_a_ward_and_real_bookings_reach_the_section_signs(client) -> None:
    sections = client.get("/atlas/live-sections", headers=auth("officer")).json()["wards"]
    s = next(x for x in sections if x["name"] == "HAFEEZPET")
    ward = s["main_ward_id"]
    items = [
        {"client_id": f"c-{k}", "channel": "app", "category": "no_water", "text": "No water",
         "ward_id": ward, "lat": 17.48 + 0.002 * k, "lon": 78.36, "is_synthetic": True}
        for k in range(4)
    ]  # fmt: skip
    made = client.post("/intake/batch", json={"items": items}, headers=auth("resident")).json()
    assert {r["status"] for r in made["results"]} == {"created"}
    booked = {"lat": 17.483441, "lon": 78.361132, "category": "home", "water_at_home": "no",
              "phone": "+919800009999", "language": "en"}  # fmt: skip
    assert client.post("/bookings", json=booked, headers=auth("resident")).status_code == 201
    sections = client.get("/atlas/live-sections", headers=auth("officer")).json()["wards"]
    clues = {c["code"]: c for c in next(x for x in sections if x["name"] == "HAFEEZPET")["clues"]}
    # stored as "ward:<id>", counted for the ward (it was never counted before 2026-10-07)
    assert clues["complaints"]["value"] == 4 and clues["complaints"]["bad"] is True
    assert clues["bookings"]["value"] == 1  # a booking made through JalLekha counts
