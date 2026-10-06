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
