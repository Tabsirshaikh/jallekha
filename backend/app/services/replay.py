"""Booking replay (A1, F19): daily tanker bookings rebuilt from real HMWSSB monthly totals.

HMWSSB publishes bookings per section per month only. The replay spreads each section-month
total over the days of that month at random (every day equally likely) and gives each booking
a random time of day (bookings come in around the clock by IVRS and app). The split is
SYNTHETIC; every section-month total stays exactly REAL.

Randomness is seeded per section and month, so a replay does not change when other months or
sections are added. Times are local Hyderabad time (IST).
"""

from __future__ import annotations

import calendar
import random
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any

IST = timezone(timedelta(hours=5, minutes=30))
SECONDS_PER_DAY = 86_400


@dataclass(frozen=True)
class DailyCount:
    day: date
    division: str
    section: str
    bookings: int
    basis: str = "SYNTHETIC"  # the split over days
    total_basis: str = "REAL"  # the section-month total it adds up to


@dataclass(frozen=True)
class Booking:
    booking_id: str
    section: str
    division: str
    arrived_at: datetime
    basis: str = "SYNTHETIC"


def _month_rows(
    rows: list[dict[str, Any]], months: tuple[tuple[int, int], ...]
) -> list[dict[str, Any]]:
    selected = []
    for year, month in months:
        found = [r for r in rows if r["year"] == year and r["month"] == month and r["bookings"]]
        if not found:
            raise ValueError(f"{year}-{month:02d} has no HMWSSB bookings to replay")
        selected.extend(sorted(found, key=lambda r: r["section"]))
    return selected


def daily_counts(
    rows: list[dict[str, Any]], months: tuple[tuple[int, int], ...], seed: int
) -> list[DailyCount]:
    """Split each section-month booking total over its days; totals are preserved exactly."""
    out: list[DailyCount] = []
    for row in _month_rows(rows, months):
        year, month, section = row["year"], row["month"], row["section"]
        n_days = calendar.monthrange(year, month)[1]
        rng = random.Random(f"{seed}:{year}-{month:02d}:{section}")
        per_day = [0] * n_days
        for _ in range(row["bookings"]):
            per_day[rng.randrange(n_days)] += 1
        out.extend(
            DailyCount(date(year, month, i + 1), row["division"], section, count)
            for i, count in enumerate(per_day)
            if count
        )
    return out


def arrivals(days: list[DailyCount], seed: int) -> list[Booking]:
    """One booking per count, at a random second of its day, in arrival (FCFS) order."""
    bookings: list[Booking] = []
    for day in days:
        rng = random.Random(f"{seed}:{day.day.isoformat()}:{day.section}:arrivals")
        start = datetime(day.day.year, day.day.month, day.day.day, tzinfo=IST)
        seconds = sorted(rng.randrange(SECONDS_PER_DAY) for _ in range(day.bookings))
        bookings.extend(
            Booking(
                booking_id=f"{day.day.isoformat()}:{day.section}:{i + 1:05d}",
                section=day.section,
                division=day.division,
                arrived_at=start + timedelta(seconds=s),
            )
            for i, s in enumerate(seconds)
        )
    bookings.sort(key=lambda b: (b.arrived_at, b.booking_id))
    return bookings
