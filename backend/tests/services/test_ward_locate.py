"""Placing a point on the 2016 ward polygons (F20: which ward a delivery stop serves)."""

from __future__ import annotations

from app.services import ward_locate

GACHIBOWLI = (17.44437, 78.31387)  # inside Ward 105 Gachibowli (relation/7848824)
MONDA_MARKET = (17.4400, 78.4983)  # inside Ward 150 Monda Market (relation/7857838)


def test_a_point_inside_a_ward_is_placed_in_that_ward() -> None:
    assert ward_locate.locate(*GACHIBOWLI) == "relation/7848824"
    assert ward_locate.locate(*MONDA_MARKET) == "relation/7857838"


def test_a_point_outside_every_ward_is_not_placed() -> None:
    assert ward_locate.locate(17.0, 78.0) is None


def test_known_wards_are_the_evidence_table_wards() -> None:
    known = ward_locate.known_wards()
    assert "relation/7848824" in known and "relation/7857838" in known
    assert "relation/0" not in known
    assert len(known) == 145


def test_place_stop_prefers_the_officer_ward_and_says_where_the_ward_came_from() -> None:
    assert ward_locate.place(*MONDA_MARKET, ward_id="relation/7848824") == (
        "relation/7848824",
        "OFFICER",
    )
    assert ward_locate.place(*MONDA_MARKET) == ("relation/7857838", "DERIVED")
    assert ward_locate.place(17.0, 78.0) == (None, "UNPLACED")


def test_an_unknown_officer_ward_is_refused() -> None:
    try:
        ward_locate.place(*MONDA_MARKET, ward_id="relation/0")
    except ValueError as exc:
        assert "relation/0" in str(exc)
    else:
        raise AssertionError("an unknown ward was accepted")
