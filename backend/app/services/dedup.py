"""F13 duplicate engine (T1): pure functions, no database.

Rule (docs/JALLEKHA_FINAL_SOLUTION.md F13): same household id matches first; otherwise the
same category within the radius (100 m) and the category's time window (48 h or 7 days).
Text similarity is recorded as a secondary signal only and never decides a merge.
The duplicate rate per area is a reporting-activity signal (Liu et al.), not a need measure.
"""

from __future__ import annotations

import logging
import math
from collections import defaultdict
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Literal, Protocol

from app.config.trust import TRUST_CONFIG

logger = logging.getLogger("jallekha.dedup")

# Mean Earth radius (IUGG), metres.
EARTH_RADIUS_M = 6_371_008.8
# Float tolerance for the inclusive radius check (1 micrometre).
_DISTANCE_TOLERANCE_M = 1e-6
_METRES_PER_DEGREE_LAT = EARTH_RADIUS_M * math.pi / 180

MatchRule = Literal["household", "location_time"]


@dataclass(frozen=True)
class ComplaintRecord:
    id: str
    category: str
    lat: float
    lon: float
    created_at: datetime
    household_id: str | None = None
    text: str | None = None
    area: str | None = None


@dataclass(frozen=True)
class DedupRule:
    radius_m: float
    window_hours: Mapping[str, float]
    default_window_hours: float | None = None

    @classmethod
    def from_config(cls) -> DedupRule:
        return cls(
            radius_m=TRUST_CONFIG.dedup_radius_metres,
            window_hours=TRUST_CONFIG.dedup_window_hours,
        )

    def window_for(self, category: str) -> timedelta:
        hours = self.window_hours.get(category, self.default_window_hours)
        if hours is None:
            raise ValueError(f"Unknown complaint category {category!r} for the duplicate rule")
        return timedelta(hours=hours)


@dataclass(frozen=True)
class Match:
    parent_id: str
    rule: MatchRule
    distance_m: float
    hours_apart: float
    text_score: float | None = None


@dataclass(frozen=True, order=True)
class DuplicateLinkRecord:
    child_id: str
    parent_id: str  # root of the cluster (the first report)
    matched_id: str  # the complaint the rule actually matched
    rule: MatchRule = field(compare=False)
    distance_m: float = field(compare=False)
    hours_apart: float = field(compare=False)
    text_score: float | None = field(default=None, compare=False)


class TextSimilarity(Protocol):
    def similarity(self, first: str, second: str) -> float | None: ...


class NullTextSimilarity:
    """Used when text similarity is off or the model is not installed."""

    def similarity(self, first: str, second: str) -> float | None:
        return None


class SentenceTransformerSimilarity:
    """Cosine similarity of multilingual sentence embeddings (optional `ml` extra)."""

    def __init__(self, model_name: str) -> None:
        from sentence_transformers import SentenceTransformer

        self._model = SentenceTransformer(model_name)

    def similarity(self, first: str, second: str) -> float | None:
        vectors = self._model.encode([first, second], normalize_embeddings=True)
        return float((vectors[0] * vectors[1]).sum())


def load_text_similarity(
    enabled: bool | None = None, model_name: str | None = None
) -> TextSimilarity:
    enabled = TRUST_CONFIG.dedup_text_similarity_enabled if enabled is None else enabled
    if not enabled:
        return NullTextSimilarity()
    try:
        return SentenceTransformerSimilarity(model_name or TRUST_CONFIG.dedup_text_model)
    except Exception as exc:  # missing extra, missing weights, no network
        logger.warning("Text similarity unavailable, continuing without it: %s", exc)
        return NullTextSimilarity()


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = phi2 - phi1
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlmb / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(min(1.0, math.sqrt(a)))


class GridIndex:
    """Square-degree grid; `nearby` returns a superset of points within `radius_m`."""

    def __init__(self, radius_m: float) -> None:
        self._cell_deg = radius_m / _METRES_PER_DEGREE_LAT
        self._cells: dict[tuple[int, int], list[ComplaintRecord]] = defaultdict(list)

    def _key(self, lat: float, lon: float) -> tuple[int, int]:
        return math.floor(lat / self._cell_deg), math.floor(lon / self._cell_deg)

    def add(self, item: ComplaintRecord) -> None:
        self._cells[self._key(item.lat, item.lon)].append(item)

    def nearby(self, lat: float, lon: float) -> list[ComplaintRecord]:
        row, col = self._key(lat, lon)
        # A cell is narrower east-west than north-south by cos(lat), so search wider in lon.
        cos_lat = max(math.cos(math.radians(abs(lat) + self._cell_deg)), 1e-6)
        span = math.ceil(1 / cos_lat)
        found: list[ComplaintRecord] = []
        for r in (row - 1, row, row + 1):
            for c in range(col - span, col + span + 1):
                found.extend(self._cells.get((r, c), ()))
        return found


def _check(item: ComplaintRecord) -> None:
    if item.created_at.tzinfo is None or item.created_at.utcoffset() is None:
        raise ValueError(f"Complaint {item.id} has a naive timestamp; use timezone-aware UTC")


def find_parent(
    new: ComplaintRecord,
    existing: Iterable[ComplaintRecord],
    rule: DedupRule | None = None,
    text_similarity: TextSimilarity | None = None,
) -> Match | None:
    """Return the complaint `new` duplicates, or None. Only earlier complaints qualify."""
    rule = rule or DedupRule.from_config()
    _check(new)
    window = rule.window_for(new.category)

    household: list[tuple[timedelta, str, ComplaintRecord]] = []
    location: list[tuple[float, timedelta, str, ComplaintRecord]] = []
    for old in existing:
        if old.id == new.id or old.category != new.category:
            continue
        _check(old)
        gap = new.created_at - old.created_at
        if gap < timedelta(0) or gap > window:
            continue
        if new.household_id and old.household_id == new.household_id:
            household.append((gap, old.id, old))
            continue
        distance = haversine_m(new.lat, new.lon, old.lat, old.lon)
        if distance <= rule.radius_m + _DISTANCE_TOLERANCE_M:
            location.append((distance, gap, old.id, old))

    if household:
        gap, _, parent = min(household, key=lambda c: (c[0], c[1]))
        kind: MatchRule = "household"
        distance = haversine_m(new.lat, new.lon, parent.lat, parent.lon)
    elif location:
        distance, gap, _, parent = min(location, key=lambda c: (c[0], c[1], c[2]))
        kind = "location_time"
    else:
        return None

    score = None
    if text_similarity is not None and new.text and parent.text:
        score = text_similarity.similarity(new.text, parent.text)
    return Match(
        parent_id=parent.id,
        rule=kind,
        distance_m=distance,
        hours_apart=gap.total_seconds() / 3600,
        text_score=score,
    )


def link_duplicates(
    complaints: Iterable[ComplaintRecord],
    rule: DedupRule | None = None,
    text_similarity: TextSimilarity | None = None,
) -> list[DuplicateLinkRecord]:
    """Link every complaint to its cluster root, processing in time order (then id)."""
    rule = rule or DedupRule.from_config()
    ordered = sorted(complaints, key=lambda c: (c.created_at, c.id))
    index = GridIndex(rule.radius_m)
    by_household: dict[str, list[ComplaintRecord]] = defaultdict(list)
    root: dict[str, str] = {}

    def find_root(cid: str) -> str:
        while root[cid] != cid:
            root[cid] = root[root[cid]]
            cid = root[cid]
        return cid

    links: list[DuplicateLinkRecord] = []
    for item in ordered:
        candidates = index.nearby(item.lat, item.lon)
        if item.household_id:
            candidates = candidates + by_household[item.household_id]
        match = find_parent(item, candidates, rule, text_similarity)
        root[item.id] = item.id
        if match is not None:
            parent_root = find_root(match.parent_id)
            root[item.id] = parent_root
            links.append(
                DuplicateLinkRecord(
                    child_id=item.id,
                    parent_id=parent_root,
                    matched_id=match.parent_id,
                    rule=match.rule,
                    distance_m=match.distance_m,
                    hours_apart=match.hours_apart,
                    text_score=match.text_score,
                )
            )
        index.add(item)
        if item.household_id:
            by_household[item.household_id].append(item)
    return links


_PERIODS: dict[str, Callable[[datetime], str]] = {
    "month": lambda t: t.strftime("%Y-%m"),
    "week": lambda t: "{}-W{:02d}".format(*t.isocalendar()[:2]),
}


def duplicate_rate_by_area(
    complaints: Iterable[ComplaintRecord],
    links: Iterable[DuplicateLinkRecord],
    area_key: Callable[[ComplaintRecord], str | None],
    period: str = "month",
) -> list[dict[str, object]]:
    """Share of complaints that are duplicates, per area and period (UTC)."""
    if period not in _PERIODS:
        raise ValueError(f"period must be one of {sorted(_PERIODS)}, got {period!r}")
    label = _PERIODS[period]
    duplicate_ids = {link.child_id for link in links}
    totals: dict[tuple[str, str], list[int]] = defaultdict(lambda: [0, 0])
    for item in complaints:
        key = (area_key(item) or "unassigned", label(item.created_at))
        totals[key][0] += 1
        totals[key][1] += item.id in duplicate_ids
    basis = (
        "DERIVED: duplicates / complaints per area and UTC "
        f"{period}; duplicates from the F13 rule (T1 dedup engine)"
    )
    return [
        {
            "area": area,
            "period": when,
            "complaints": total,
            "duplicates": dups,
            "duplicate_rate": dups / total,
            "duplicate_rate_basis": basis,
        }
        for (area, when), (total, dups) in sorted(totals.items())
    ]
