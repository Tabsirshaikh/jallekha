"""T1 duplicate engine (F13). Points are test fixtures placed by exact offsets, not data."""

import math
import random
from datetime import UTC, datetime, timedelta

import pytest

from app.config.trust import TRUST_CONFIG
from app.services.dedup import (
    EARTH_RADIUS_M,
    ComplaintRecord,
    DedupRule,
    GridIndex,
    NullTextSimilarity,
    duplicate_rate_by_area,
    find_parent,
    haversine_m,
    link_duplicates,
    load_text_similarity,
)

BASE_LAT, BASE_LON = 17.385, 78.4867  # a point in Hyderabad, used only as a test origin
T0 = datetime(2026, 4, 1, 9, 0, tzinfo=UTC)


def offset(north_m: float = 0.0, east_m: float = 0.0) -> tuple[float, float]:
    """Point `north_m` / `east_m` metres from the test origin (spherical Earth)."""
    lat = BASE_LAT + math.degrees(north_m / EARTH_RADIUS_M)
    lon = BASE_LON + math.degrees(east_m / (EARTH_RADIUS_M * math.cos(math.radians(BASE_LAT))))
    return lat, lon


def complaint(
    cid: str,
    category: str = "no_water",
    *,
    north_m: float = 0.0,
    east_m: float = 0.0,
    after: timedelta = timedelta(0),
    household_id: str | None = None,
    text: str | None = None,
    area: str | None = "ward-1",
) -> ComplaintRecord:
    lat, lon = offset(north_m, east_m)
    return ComplaintRecord(
        id=cid,
        category=category,
        lat=lat,
        lon=lon,
        created_at=T0 + after,
        household_id=household_id,
        text=text,
        area=area,
    )


# --- done-when (features.csv T1) -----------------------------------------------------------


def test_leak_5_days_apart_merges() -> None:
    first = complaint("a", "leak")
    second = complaint("b", "leak", after=timedelta(days=5))
    match = find_parent(second, [first])
    assert match is not None
    assert match.parent_id == "a"
    assert match.rule == "location_time"


def test_no_water_5_days_apart_does_not_merge() -> None:
    first = complaint("a", "no_water")
    second = complaint("b", "no_water", after=timedelta(days=5))
    assert find_parent(second, [first]) is None


def test_150_m_apart_does_not_merge() -> None:
    first = complaint("a", "no_water")
    second = complaint("b", "no_water", north_m=150, after=timedelta(hours=1))
    assert find_parent(second, [first]) is None


# --- rule details --------------------------------------------------------------------------


def test_config_matches_solution_f13() -> None:
    assert TRUST_CONFIG.dedup_radius_metres == 100
    assert dict(TRUST_CONFIG.dedup_window_hours) == {
        "no_water": 48,
        "tanker_missed": 48,
        "dirty_water": 48,
        "leak": 168,
        "other": 168,
    }
    assert TRUST_CONFIG.dedup_text_similarity_enabled is False


def test_household_matches_first() -> None:
    near_stranger = complaint("near", north_m=10, after=timedelta(hours=1))
    same_household_far = complaint("home", north_m=400, household_id="hh-7")
    new = complaint("new", after=timedelta(hours=2), household_id="hh-7")
    match = find_parent(new, [near_stranger, same_household_far])
    assert match is not None
    assert (match.parent_id, match.rule) == ("home", "household")


def test_household_outside_window_does_not_match() -> None:
    old = complaint("home", north_m=400, household_id="hh-7")
    new = complaint("new", after=timedelta(hours=49), household_id="hh-7")
    assert find_parent(new, [old]) is None


def test_exactly_100_m_merges_and_just_over_does_not() -> None:
    first = complaint("a")
    at_boundary = complaint("b", north_m=100, after=timedelta(hours=1))
    over = complaint("c", north_m=100.5, after=timedelta(hours=1))
    assert find_parent(at_boundary, [first]) is not None
    assert find_parent(over, [first]) is None


def test_window_boundary_is_inclusive() -> None:
    first = complaint("a", "dirty_water")
    at_48h = complaint("b", "dirty_water", after=timedelta(hours=48))
    after_48h = complaint("c", "dirty_water", after=timedelta(hours=48, seconds=1))
    assert find_parent(at_48h, [first]) is not None
    assert find_parent(after_48h, [first]) is None


def test_other_category_uses_7_day_window() -> None:
    first = complaint("a", "other")
    assert find_parent(complaint("b", "other", after=timedelta(days=7)), [first]) is not None
    assert find_parent(complaint("c", "other", after=timedelta(days=7, seconds=1)), [first]) is None


def test_different_category_not_merged() -> None:
    first = complaint("a", "leak")
    second = complaint("b", "no_water", after=timedelta(hours=1))
    assert find_parent(second, [first]) is None


def test_later_complaint_is_never_a_parent() -> None:
    later = complaint("later", after=timedelta(hours=3))
    new = complaint("new", after=timedelta(hours=1))
    assert find_parent(new, [later]) is None


def test_nearest_candidate_wins() -> None:
    far = complaint("far", north_m=90)
    near = complaint("near", north_m=20)
    new = complaint("new", after=timedelta(hours=1))
    match = find_parent(new, [far, near])
    assert match is not None
    assert match.parent_id == "near"
    assert match.distance_m == pytest.approx(20, abs=0.01)
    assert match.hours_apart == pytest.approx(1)


def test_unknown_category_rejected() -> None:
    with pytest.raises(ValueError, match="category"):
        find_parent(complaint("b", "flood"), [complaint("a", "flood")])


def test_naive_timestamp_rejected() -> None:
    lat, lon = offset()
    naive = ComplaintRecord(
        id="x", category="leak", lat=lat, lon=lon, created_at=datetime(2026, 1, 1)
    )
    with pytest.raises(ValueError, match="timezone"):
        find_parent(naive, [])


def test_custom_rule_with_default_window() -> None:
    rule = DedupRule(radius_m=300, window_hours={}, default_window_hours=168)
    first = complaint("a", "Any Chicago Type")
    second = complaint("b", "Any Chicago Type", north_m=250, after=timedelta(days=6))
    assert find_parent(second, [first], rule) is not None


# --- batch linking and clusters ------------------------------------------------------------


def test_chain_links_to_cluster_root() -> None:
    a = complaint("a")
    b = complaint("b", north_m=80, after=timedelta(hours=1))
    c = complaint("c", north_m=160, after=timedelta(hours=2))  # 80 m from b, 160 m from a
    links = {link.child_id: link for link in link_duplicates([c, a, b])}
    assert set(links) == {"b", "c"}
    assert (links["b"].parent_id, links["b"].matched_id) == ("a", "a")
    assert (links["c"].parent_id, links["c"].matched_id) == ("a", "b")


def test_link_duplicates_is_independent_of_input_order() -> None:
    items = [
        complaint("a", "leak"),
        complaint("b", "leak", north_m=40, after=timedelta(days=2)),
        complaint("c", "leak", east_m=500, after=timedelta(days=3)),
        complaint("d", "no_water", after=timedelta(hours=5)),
        complaint("e", "no_water", north_m=30, after=timedelta(hours=6)),
    ]
    expected = sorted(link_duplicates(items))
    shuffled = items[:]
    random.Random(7).shuffle(shuffled)
    assert sorted(link_duplicates(shuffled)) == expected
    assert [(link.child_id, link.parent_id) for link in expected] == [("b", "a"), ("e", "d")]


def test_grid_index_matches_brute_force() -> None:
    rng = random.Random(11)
    points = [
        complaint(str(i), north_m=rng.uniform(-400, 400), east_m=rng.uniform(-400, 400))
        for i in range(300)
    ]
    index = GridIndex(radius_m=100)
    for point in points:
        index.add(point)
    for probe in points[:50]:
        brute = {p.id for p in points if haversine_m(probe.lat, probe.lon, p.lat, p.lon) <= 100}
        found = {
            p.id
            for p in index.nearby(probe.lat, probe.lon)
            if haversine_m(probe.lat, probe.lon, p.lat, p.lon) <= 100
        }
        assert found == brute


def test_haversine_one_degree_latitude() -> None:
    expected = EARTH_RADIUS_M * math.pi / 180
    assert haversine_m(10.0, 78.0, 11.0, 78.0) == pytest.approx(expected, rel=1e-12)


# --- text similarity is secondary ----------------------------------------------------------


class FixedSimilarity:
    def __init__(self, score: float) -> None:
        self.score = score

    def similarity(self, first: str, second: str) -> float | None:
        return self.score


def test_text_score_recorded_but_never_decides() -> None:
    first = complaint("a", text="no water since morning")
    near = complaint("b", north_m=20, after=timedelta(hours=1), text="different words")
    far = complaint("c", north_m=500, after=timedelta(hours=1), text="no water since morning")
    match = find_parent(near, [first], text_similarity=FixedSimilarity(0.0))
    assert match is not None
    assert match.text_score == 0.0
    assert find_parent(far, [first], text_similarity=FixedSimilarity(1.0)) is None


def test_text_similarity_disabled_returns_null() -> None:
    assert isinstance(load_text_similarity(enabled=False), NullTextSimilarity)


def test_text_similarity_falls_back_when_model_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    import builtins

    real_import = builtins.__import__

    def fail_sentence_transformers(name: str, *args: object, **kwargs: object) -> object:
        if name.startswith("sentence_transformers"):
            raise ImportError("not installed")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fail_sentence_transformers)
    assert isinstance(load_text_similarity(enabled=True), NullTextSimilarity)


# --- duplicate rate per area ---------------------------------------------------------------


def test_duplicate_rate_by_area() -> None:
    items = [
        complaint("a", area="ward-1"),
        complaint("b", north_m=10, after=timedelta(hours=1), area="ward-1"),
        complaint("c", north_m=20, after=timedelta(hours=2), area="ward-1"),
        complaint("d", east_m=5000, area="ward-2"),
        complaint("e", east_m=9000, after=timedelta(hours=1), area=None),
    ]
    links = link_duplicates(items)
    rows = duplicate_rate_by_area(items, links, area_key=lambda c: c.area, period="month")
    by_area = {row["area"]: row for row in rows}
    assert by_area["ward-1"]["complaints"] == 3
    assert by_area["ward-1"]["duplicates"] == 2
    assert by_area["ward-1"]["duplicate_rate"] == pytest.approx(2 / 3)
    assert by_area["ward-2"]["duplicate_rate"] == 0
    assert by_area["unassigned"]["complaints"] == 1
    assert all(row["period"] == "2026-04" for row in rows)
    assert all(row["duplicate_rate_basis"].startswith("DERIVED") for row in rows)


def test_duplicate_rate_rejects_unknown_period() -> None:
    with pytest.raises(ValueError, match="period"):
        duplicate_rate_by_area([], [], area_key=lambda c: c.area, period="year")
