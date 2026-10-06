"""Approximate service cells and building shares conserve section totals."""

import pytest
from shapely.geometry import box

from app.services.booking_transfer import cells, split


def test_global_voronoi_clipped_to_division_and_city():
    sites = {"A": (2, 2, "1"), "B": (8, 2, "1"), "C": (8, 8, "2")}
    city = box(0, 0, 10, 10)
    areas = cells(sites, city, buffer_metres=1)
    assert areas["A"].covers(__import__("shapely").Point(2, 2))
    assert areas["A"].intersection(areas["B"]).area == pytest.approx(0)
    assert all(city.covers(g) for g in areas.values())
    assert areas["C"].area <= __import__("math").pi * 1.01


def test_building_weighting_not_polygon_area_and_mass_conserved():
    weights = {"A": {"W1": 9, "W2": 1}, "B": {"W2": 3}}
    totals, unplaced = split({"A": 100, "B": 20, "C": 50}, weights)
    assert totals == {"W1": 90, "W2": 30}
    assert unplaced == {"C": 50}
    assert sum(totals.values()) + sum(unplaced.values()) == 170


def test_zero_building_weight_remains_unplaced():
    totals, unplaced = split({"A": 20}, {"A": {"W1": 0}})
    assert totals == {}
    assert unplaced == {"A": 20}
    with pytest.raises(ValueError):
        split({"A": 20}, {"A": {"W1": -1}})
