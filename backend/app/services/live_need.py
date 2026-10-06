"""Live need clues and live booking concentration for the ward atlas (U5).

Census 2011 need is the baseline and changes only with a new survey. Five clues from data the
system records every day say where need may be rising now: water still owed (F11 debt), a jump in
bookings against the ward's usual month, "no water" complaints (F14), supply cuts (F15 notices)
and groundwater deeper than usual (D7). A ward is flagged when at least `min_bad_clues` are bad;
a clue with no data is "unknown", never bad. Pure functions; the route gathers the inputs.
"""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta

from app.config.allocation import ALLOCATION_CONFIG
from app.config.live_need import LIVE_NEED_CONFIG, LiveNeedConfig


@dataclass(frozen=True)
class WardSignals:
    ward_id: str
    owed_litres: float
    bookings_window: int
    usual_month: float | None  # None: no booking history for the ward
    complaints: int
    cuts: int
    groundwater_m: float | None  # None: no nearby wells


@dataclass(frozen=True)
class BookingCounts:
    by_ward: dict[str, int]
    by_section: dict[str, int]
    unplaced: int  # section not placed on a ward
    total: int


def _clue(code: str, bad: bool, value: float | None, reference: float, known: bool = True):
    return {
        "code": code,
        "bad": bad and known,
        "known": known,
        "value": value,
        "reference": reference,
    }


def evaluate(s: WardSignals, cfg: LiveNeedConfig = LIVE_NEED_CONFIG) -> dict:
    load = ALLOCATION_CONFIG.tanker_load_litres
    jump_at = None if s.usual_month is None else s.usual_month * cfg.bookings_jump_ratio
    clues = [
        _clue("owed", s.owed_litres >= cfg.owed_min_litres, round(s.owed_litres / load, 1), 0.0),
        _clue(
            "bookings",
            jump_at is not None and s.bookings_window >= max(jump_at, cfg.bookings_jump_min),
            s.bookings_window,
            round(jump_at, 1) if jump_at is not None else 0.0,
            known=jump_at is not None,
        ),
        _clue("complaints", s.complaints >= cfg.complaints_min, s.complaints, cfg.complaints_min),
        _clue("cuts", s.cuts >= 1, s.cuts, 1),
        _clue(
            "groundwater",
            s.groundwater_m is not None and s.groundwater_m >= cfg.groundwater_deeper_m,
            None if s.groundwater_m is None else round(s.groundwater_m, 2),
            cfg.groundwater_deeper_m,
            known=s.groundwater_m is not None,
        ),
    ]
    bad = sum(c["bad"] for c in clues)
    return {"clues": clues, "bad_count": bad, "rising": bad >= cfg.min_bad_clues}


def count_bookings(
    bookings: Iterable[Mapping[str, str]],
    section_ward: Mapping[str, str],
    now: datetime,
    days: int,
) -> BookingCounts:
    """Distinct bookings (by id) that arrived in the `days` before `now`, per ward and section."""
    start = now - timedelta(days=days)
    seen: set[str] = set()
    wards: Counter[str] = Counter()
    sections: Counter[str] = Counter()
    unplaced = 0
    for b in bookings:
        arrived = datetime.fromisoformat(str(b["arrived_at"]))
        if b["booking_id"] in seen or not (start <= arrived <= now):
            continue
        seen.add(b["booking_id"])
        sections[b["section"]] += 1
        ward = section_ward.get(b["section"])
        if ward is None:
            unplaced += 1
        else:
            wards[ward] += 1
    return BookingCounts(dict(wards), dict(sections), unplaced, len(seen))


def concentration(
    section_bookings: Mapping[str, int], cfg: LiveNeedConfig = LIVE_NEED_CONFIG
) -> dict:
    """Gini of bookings over sections and the share of the top `top_fraction` of sections."""
    values = sorted(v for v in section_bookings.values() if v >= 0)
    total, n = sum(values), len(values)
    if n == 0 or total == 0:
        return {"gini": None, "top_share": None, "top_sections": 0, "sections": n, "bookings": 0}
    gini = sum((2 * (i + 1) - n - 1) * v for i, v in enumerate(values)) / (n * total)
    top = max(1, math.ceil(n * cfg.top_fraction))
    ranked = sorted(section_bookings.items(), key=lambda kv: (-kv[1], kv[0]))
    return {
        "gini": round(gini, 4),
        "top_share": round(sum(values[-top:]) / total, 4),
        "top_sections": top,
        "sections": n,
        "bookings": total,
        "top": [
            {"section": s, "bookings": b, "share": round(b / total, 4)} for s, b in ranked[:10]
        ],
    }
