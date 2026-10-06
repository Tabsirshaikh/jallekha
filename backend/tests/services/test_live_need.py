from datetime import UTC, datetime

import pytest

from app.config.live_need import LIVE_NEED_CONFIG
from app.services import live_need as ln

NOW = datetime(2026, 10, 6, 12, tzinfo=UTC)


def _signals(**kw) -> ln.WardSignals:
    base = dict(
        ward_id="w1", owed_litres=0.0, bookings_window=0, usual_month=None, complaints=0,
        cuts=0, groundwater_m=None,
    )  # fmt: skip
    return ln.WardSignals(**(base | kw))


def test_a_ward_needs_two_bad_clues_to_be_flagged() -> None:
    one = ln.evaluate(_signals(owed_litres=5000.0))
    assert one["bad_count"] == 1 and one["rising"] is False
    two = ln.evaluate(_signals(owed_litres=5000.0, complaints=3))
    assert two["bad_count"] == 2 and two["rising"] is True
    codes = {c["code"]: c for c in two["clues"]}
    assert codes["owed"]["bad"] and codes["owed"]["value"] == 1.0  # loads owed
    assert codes["complaints"]["bad"] and not codes["cuts"]["bad"]


def test_bookings_jump_against_the_usual_month() -> None:
    jump = ln.evaluate(_signals(bookings_window=30, usual_month=20.0))
    assert {c["code"]: c["bad"] for c in jump["clues"]}["bookings"] is True
    small = ln.evaluate(_signals(bookings_window=6, usual_month=2.0))  # below the minimum
    assert {c["code"]: c["bad"] for c in small["clues"]}["bookings"] is False
    unknown = ln.evaluate(_signals(bookings_window=50, usual_month=None))
    clue = {c["code"]: c for c in unknown["clues"]}["bookings"]
    assert clue["bad"] is False and clue["known"] is False


def test_groundwater_is_background_not_a_warning() -> None:
    # Groundwater is low across most of the city in a dry year: shown, never counted.
    deeper = ln.evaluate(_signals(groundwater_m=4.4, owed_litres=5000.0))
    gw = {c["code"]: c for c in deeper["clues"]}["groundwater"]
    assert gw["bad"] is False and gw["counts"] is False and gw["value"] == 4.4
    assert deeper["bad_count"] == 1 and deeper["rising"] is False


def test_signs_with_no_data_entered_are_unknown_not_fine() -> None:
    blank = ln.evaluate(_signals(usual_month=20.0), owed_known=False, bookings_known=False)
    by = {c["code"]: c for c in blank["clues"]}
    assert by["owed"]["known"] is False and by["bookings"]["known"] is False
    assert blank["known_count"] == 2  # complaints and cuts are recorded live


def test_missing_groundwater_is_unknown() -> None:
    missing = {c["code"]: c for c in ln.evaluate(_signals())["clues"]}["groundwater"]
    assert missing["bad"] is False and missing["known"] is False


def test_live_bookings_are_counted_per_ward_in_the_window() -> None:
    bookings = [
        {"booking_id": "a", "section": "S1", "arrived_at": "2026-10-01T09:00:00+05:30"},
        {"booking_id": "a", "section": "S1", "arrived_at": "2026-10-01T09:00:00+05:30"},  # dup
        {"booking_id": "b", "section": "S2", "arrived_at": "2026-10-05T09:00:00+05:30"},
        {"booking_id": "c", "section": "S9", "arrived_at": "2026-10-05T09:00:00+05:30"},
        {"booking_id": "d", "section": "S1", "arrived_at": "2026-08-01T09:00:00+05:30"},  # old
    ]
    counts = ln.count_bookings(bookings, {"S1": "w1", "S2": "w2"}, NOW, days=30)
    assert counts.by_ward == {"w1": 1, "w2": 1}
    assert counts.by_section == {"S1": 1, "S2": 1, "S9": 1}
    assert counts.unplaced == 1 and counts.total == 3


def test_concentration() -> None:
    even = ln.concentration({f"S{i}": 10 for i in range(10)})
    assert even["gini"] == pytest.approx(0.0) and even["top_share"] == pytest.approx(0.1)
    skew = ln.concentration({"S0": 90, **{f"S{i}": 1 for i in range(1, 11)}})
    assert skew["top_sections"] == 2 and skew["top_share"] == pytest.approx(91 / 100)
    assert skew["gini"] > 0.7 and skew["bookings"] == 100 and skew["sections"] == 11
    assert ln.concentration({})["gini"] is None


def test_thresholds_are_in_config() -> None:
    assert LIVE_NEED_CONFIG.min_bad_clues == 2
    assert LIVE_NEED_CONFIG.bookings_window_days == 30
