"""A1: booking replay. Daily arrivals are SYNTHETIC; section-month totals equal REAL HMWSSB data."""

from __future__ import annotations

from collections import Counter
from datetime import date, timedelta
from pathlib import Path

import pytest

from app.config.allocation import ALLOCATION_CONFIG
from app.services import hmwssb, replay

ROOT = Path(__file__).resolve().parents[2]
PORTAL_DIR = ROOT / "data" / "raw" / "hmwssb_tankers_portal"


@pytest.fixture(scope="module")
def rows() -> list[dict]:
    return hmwssb.read_rows(PORTAL_DIR)


def real_totals(rows: list[dict], months: tuple[tuple[int, int], ...]) -> Counter:
    return Counter(
        {
            (r["year"], r["month"], r["section"]): r["bookings"]
            for r in rows
            if (r["year"], r["month"]) in months and r["bookings"]
        }
    )


def replay_totals(days: list[replay.DailyCount]) -> Counter:
    totals: Counter = Counter()
    for day in days:
        totals[(day.day.year, day.day.month, day.section)] += day.bookings
    return totals


@pytest.mark.parametrize(
    "months", [ALLOCATION_CONFIG.replay_months_main, ALLOCATION_CONFIG.replay_months_secondary]
)
def test_section_month_totals_equal_real_data_exactly(rows: list[dict], months) -> None:
    days = replay.daily_counts(rows, months, seed=1)
    assert replay_totals(days) == real_totals(rows, months)


def test_main_window_is_summer_2025_with_real_total(rows: list[dict]) -> None:
    months = ALLOCATION_CONFIG.replay_months_main
    assert months == ((2025, 3), (2025, 4), (2025, 5), (2025, 6), (2025, 7))
    assert sum(d.bookings for d in replay.daily_counts(rows, months, seed=1)) == 977_933


def test_same_seed_same_replay_different_seed_different(rows: list[dict]) -> None:
    months = ((2023, 5),)
    first = replay.daily_counts(rows, months, seed=7)
    assert first == replay.daily_counts(rows, months, seed=7)
    assert first != replay.daily_counts(rows, months, seed=8)


def test_days_stay_inside_their_month_and_are_positive(rows: list[dict]) -> None:
    days = replay.daily_counts(rows, ((2025, 2), (2025, 4)), seed=3)
    assert all(d.bookings > 0 for d in days)
    assert {(d.day.year, d.day.month) for d in days} == {(2025, 2), (2025, 4)}
    assert max(d.day for d in days if d.day.month == 2) <= date(2025, 2, 28)


def test_every_row_is_labelled(rows: list[dict]) -> None:
    day = replay.daily_counts(rows, ((2023, 3),), seed=1)[0]
    assert day.basis == "SYNTHETIC"
    assert day.total_basis == "REAL"


def test_month_without_data_is_refused(rows: list[dict]) -> None:
    with pytest.raises(ValueError, match="2022-12"):
        replay.daily_counts(rows, ((2022, 11), (2022, 12)), seed=1)
    with pytest.raises(ValueError, match="2030-01"):
        replay.daily_counts(rows, ((2030, 1),), seed=1)


def test_arrivals_match_daily_counts_and_are_in_time_order(rows: list[dict]) -> None:
    days = [d for d in replay.daily_counts(rows, ((2023, 6),), seed=2) if d.day.day == 15]
    bookings = replay.arrivals(days, seed=2)
    assert len(bookings) == sum(d.bookings for d in days)
    assert len({b.booking_id for b in bookings}) == len(bookings)
    times = [b.arrived_at for b in bookings]
    assert times == sorted(times)
    start = min(times).replace(hour=0, minute=0, second=0)
    assert all(start <= t < start + timedelta(days=1) for t in times)
    per_section = Counter(b.section for b in bookings)
    assert per_section == Counter({d.section: d.bookings for d in days})
    assert bookings == replay.arrivals(days, seed=2)
