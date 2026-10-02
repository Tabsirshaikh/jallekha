"""Station trip sharing (A8 follow-up, used by A7): a station lends only the trips it has
left after its own queue, to stations within a distance limit; the most trips move at the
least extra km (OR-Tools min-cost max-flow)."""

from __future__ import annotations

import pytest

from app.services import station_sharing
from app.services.station_sharing import Transfer

# Round-trip km between stations (symmetric): A-B 4, A-C 10, B-C 6.
KM = {("A", "B"): 4.0, ("A", "C"): 10.0, ("B", "C"): 6.0}


def share(spare, shortfall, max_km=8.0):
    return station_sharing.share_spare_trips(spare, shortfall, KM, max_km)


def test_spare_trips_go_to_a_short_neighbour() -> None:
    assert share({"B": 3}, {"A": 2}) == [Transfer("B", "A", 2, 4.0)]


def test_never_beyond_the_distance_limit() -> None:
    assert share({"C": 5}, {"A": 2}) == []  # 10 km > 8 km
    assert share({"C": 5}, {"A": 2}, max_km=10.0) == [Transfer("C", "A", 2, 10.0)]


def test_the_nearest_lender_is_used_first() -> None:
    transfers = share({"B": 1, "C": 5}, {"A": 2}, max_km=12.0)
    assert transfers == [Transfer("B", "A", 1, 4.0), Transfer("C", "A", 1, 10.0)]


def test_as_many_trips_as_possible_move_then_least_km() -> None:
    """B's 2 spare trips cover A (4 km) and C (6 km); moving the most trips comes before
    saving km. Two lenders can together cover one short station."""
    transfers = share({"B": 2}, {"A": 1, "C": 1})
    assert sorted(transfers) == [Transfer("B", "A", 1, 4.0), Transfer("B", "C", 1, 6.0)]
    assert sum(t.trips for t in share({"A": 1, "B": 1}, {"C": 2}, max_km=12.0)) == 2


def test_nothing_to_share() -> None:
    assert share({}, {"A": 3}) == []
    assert share({"B": 3}, {}) == []
    assert share({"A": 3}, {"A": 2}) == []  # a station never lends to itself


def test_bad_input_is_rejected() -> None:
    with pytest.raises(ValueError, match="negative"):
        share({"B": -1}, {"A": 1})
    with pytest.raises(ValueError, match="max_km"):
        share({"B": 1}, {"A": 1}, max_km=-1)
