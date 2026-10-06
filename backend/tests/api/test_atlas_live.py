"""GET /atlas/live: Census need plus the five live clues per ward, and live concentration."""

from conftest import auth


def test_live_atlas_lists_every_ward_with_need_and_clues(client) -> None:
    body = client.get("/atlas/live", headers=auth("officer")).json()
    assert body["window_days"] == 30 and body["min_bad_clues"] == 2
    wards = body["wards"]
    assert len(wards) == 145
    ward = next(w for w in wards if w["ward_id"] == "relation/7848824")  # Ward 105 Gachibowli
    assert ward["name"].startswith("Ward 105")
    assert {"wad", "cad", "hardship", "households", "need_weight"} <= set(ward["need"])
    n = ward["need"]
    assert n["need_weight"] == round(1 + 2 * n["wad"] + n["cad"] + n["hardship"], 4)
    assert [c["code"] for c in ward["clues"]] == [
        "owed", "bookings", "complaints", "cuts", "groundwater"
    ]  # fmt: skip
    assert ward["usual_month_bookings"] > 0  # 2022-24 history placed on this ward
    # no supplied bookings yet: concentration falls back to the 2022-24 history
    conc = body["concentration"]
    assert conc["source"] == "history" and conc["live_bookings"] == 0
    assert 0.6 < conc["top_share"] < 0.75 and conc["top_sections"] == 21


def test_live_atlas_needs_an_officer(client) -> None:
    assert client.get("/atlas/live").status_code == 401
    assert client.get("/atlas/live", headers=auth("resident")).status_code == 403


def test_no_water_complaints_turn_the_clue_bad(client) -> None:
    from sqlalchemy.orm import Session

    from app.main import app
    from app.models import Complaint
    from app.routers.intake import get_intake_service

    ward = "relation/7848824"
    engine = app.dependency_overrides[get_intake_service]().engine
    with Session(engine) as session:
        session.add_all(
            Complaint(category="no_water", channel="sms", basis="REAL", area_id=ward)
            for _ in range(3)
        )
        session.commit()
    body = client.get("/atlas/live", headers=auth("officer")).json()
    row = next(w for w in body["wards"] if w["ward_id"] == ward)
    clue = next(c for c in row["clues"] if c["code"] == "complaints")
    assert clue["bad"] is True and clue["value"] == 3
