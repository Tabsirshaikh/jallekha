"""T9 confidence gate (F17): score each group's data quality, flag low confidence for an officer.

Pure: no database, no clock, no LLM. Each signal scores a planner group ("ward:<id>" or
"section:<name>", A3) from 0 to 1 with a basis, or is marked unavailable. A missing signal is
excluded and listed, never scored 0. The combination is the minimum of the available signals
(OPEN, owner to confirm); the reason names the weakest signal and its value.

`T9Gate` implements A7's `planner.ConfidenceGate`: `build_plan` keeps flagged groups in the plan
and `approve_plan` refuses them until an officer's `mark_checked` (ledger `ward_reviewed`).
`calibrate` picks the threshold on the A7 replay (scripts/trust/calibrate_confidence.py).
"""

from __future__ import annotations

import csv
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Protocol

from app.config.confidence import CONFIDENCE_CONFIG, ConfidenceConfig
from app.services.planner import Assessment

CENSUS = "census_join_quality"
LOCATION = "section_location"
DATA_AGE = "data_age"
INTERVAL = "forecast_interval_width"
EVIDENCE_AGE = "evidence_age"
SIGNALS: tuple[str, ...] = (CENSUS, LOCATION, DATA_AGE, INTERVAL, EVIDENCE_AGE)

WARD_PREFIX, SECTION_PREFIX = "ward:", "section:"


@dataclass(frozen=True)
class SignalScore:
    name: str
    available: bool
    score: float | None  # 0-1 when available, None otherwise
    basis: str


@dataclass(frozen=True)
class Combined:
    confidence: float
    used: tuple[str, ...]
    unavailable: tuple[str, ...]
    reason: str
    signals: tuple[SignalScore, ...] = ()


@dataclass(frozen=True)
class SignalTables:
    """P1's tables: ward_evidence.csv rows by ward_id, and section_to_ward_2016.csv rows."""

    evidence: Mapping[str, Mapping[str, str]]
    sections: Sequence[Mapping[str, str]]

    @classmethod
    def from_files(cls, root: Path, config: ConfidenceConfig = CONFIDENCE_CONFIG) -> SignalTables:
        with (root / config.evidence_path).open(encoding="utf-8", newline="") as handle:
            evidence = {row["ward_id"]: row for row in csv.DictReader(handle)}
        with (root / config.sections_path).open(encoding="utf-8", newline="") as handle:
            sections = list(csv.DictReader(handle))
        return cls(evidence, sections)


def _clip(value: float, decimals: int) -> float:
    return round(min(1.0, max(0.0, value)), decimals)


def _ward_id(group: str) -> str | None:
    return group[len(WARD_PREFIX) :] if group.startswith(WARD_PREFIX) else None


# --- signal 1: Census join quality ---------------------------------------------------------


def score_census(
    group: str, tables: SignalTables, config: ConfidenceConfig = CONFIDENCE_CONFIG
) -> SignalScore:
    ward = _ward_id(group)
    if ward is None:
        return SignalScore(
            CENSUS, True, 0.0, "section not placed on a ward: need is the A3 fallback"
        )
    row = tables.evidence.get(ward)
    if row is None:
        return SignalScore(
            CENSUS, True, 0.0, "ward not in ward_evidence.csv: need is the A3 fallback"
        )
    status = row.get("join_status", "")
    if row.get("allocation_eligible") != "True" or status not in config.census_ok_join_status:
        return SignalScore(
            CENSUS, True, 0.0,
            f"join_status {status}, allocation_eligible {row.get('allocation_eligible')}: "
            "no usable Census need (A3 fallback)",
        )  # fmt: skip
    coverage = float(row["census_coverage"])
    dominant = float(row["dominant_source_share"])
    score = min(coverage, dominant)
    basis = f"min(census_coverage {coverage:.4f}, dominant_source_share {dominant:.4f})"
    if row.get("review_required") == "True" and score > config.census_review_cap:
        score = config.census_review_cap
        basis += f", capped at {config.census_review_cap} (review_required)"
    return SignalScore(CENSUS, True, _clip(score, config.confidence_decimals), basis)


# --- signal 2: section-location uncertainty -----------------------------------------------


def _section_score(row: Mapping[str, str], config: ConfidenceConfig) -> tuple[float, str]:
    name = row["section"]
    if row.get("status") != "MAPPED" or not row.get("ward_id"):
        return 0.0, f"{name}: {row.get('status')} (not placed)"
    methods = dict(config.location_method_scores)
    method = row.get("ward_method", "")
    score = methods.get(method, 0.0)
    basis = f"{name}: {method or 'no method'} {score}"
    distance = row.get("division_distance_km") or ""
    if (
        distance
        and float(distance) > config.location_outlier_km
        and score > config.location_outlier_cap
    ):
        score = config.location_outlier_cap
        basis += f", {float(distance):.2f} km from division > {config.location_outlier_km} km cap"
    return score, basis


def score_location(
    group: str, tables: SignalTables, config: ConfidenceConfig = CONFIDENCE_CONFIG
) -> SignalScore:
    ward = _ward_id(group)
    if ward is None:
        section = group[len(SECTION_PREFIX) :] if group.startswith(SECTION_PREFIX) else group
        rows = [r for r in tables.sections if r["section"] == section]
    else:
        rows = [r for r in tables.sections if r.get("ward_id") == ward]
    if not rows:
        return SignalScore(LOCATION, True, 0.0, f"{group}: no section in section_to_ward_2016.csv")
    scored = sorted((_section_score(r, config) for r in rows), key=lambda s: (s[0], s[1]))
    score, basis = scored[0]
    return SignalScore(
        LOCATION, True, _clip(score, config.confidence_decimals),
        f"weakest of {len(rows)} section(s): {basis}",
    )  # fmt: skip


# --- signal 3: data age -------------------------------------------------------------------


def score_data_age(
    group: str,
    tables: SignalTables,
    today: date,
    config: ConfidenceConfig = CONFIDENCE_CONFIG,
) -> SignalScore:
    """Age of the Census year behind the group's need. Computed, but excluded from the
    combination: Census 2011 is the same for every ward, so it does not separate wards."""
    ward = _ward_id(group)
    row = tables.evidence.get(ward) if ward else None
    year = (row or {}).get("census_year") or "2011"
    age = today.year - int(year)
    score = _clip(1.0 - age / config.data_age_zero_at_years, config.confidence_decimals)
    basis = (
        f"Census {year}, {age} years old (score {score}); the same year for every ward, so it "
        "does not separate wards and is excluded. OPEN, owner to confirm: a per-group rule"
    )
    if config.data_age_include:
        return SignalScore(DATA_AGE, True, score, basis)
    return SignalScore(DATA_AGE, False, None, basis)


# --- signal 4: forecast interval width (T2) -----------------------------------------------


class IntervalWidthSource(Protocol):
    def relative_width(self, group: str) -> float | None: ...


@dataclass(frozen=True)
class UnavailableIntervalWidth:
    """Decision (b): the T2 forecast is not on main, so the width is unavailable."""

    available: bool = False

    def relative_width(self, group: str) -> float | None:
        return None


def score_interval_width(
    group: str, source: IntervalWidthSource, config: ConfidenceConfig = CONFIDENCE_CONFIG
) -> SignalScore:
    if not getattr(source, "available", True):
        return SignalScore(INTERVAL, False, None, "T2 forecast not merged: no interval width")
    width = source.relative_width(group)
    if width is None:
        return SignalScore(INTERVAL, False, None, f"{group}: no forecast interval")
    score = _clip(1.0 - width / config.interval_width_zero_at, config.confidence_decimals)
    return SignalScore(INTERVAL, True, score, f"relative 80% interval width {width:.4f}")


# --- signal 5: evidence age ---------------------------------------------------------------


def score_evidence_age(group: str) -> SignalScore:
    return SignalScore(
        EVIDENCE_AGE, False, None, "no dated evidence in the repo (E5 field checks carry no dates)"
    )


# --- gate ---------------------------------------------------------------------------------


@dataclass(frozen=True)
class T9Gate:
    """A7 ConfidenceGate: confidence = minimum of the available signals; below the threshold
    the group stays in the plan but needs an officer's check."""

    tables: SignalTables
    threshold: float = CONFIDENCE_CONFIG.threshold
    interval: IntervalWidthSource = field(default_factory=UnavailableIntervalWidth)
    today: date = date(2026, 10, 3)  # only the data-age basis uses it; excluded from scoring
    config: ConfidenceConfig = CONFIDENCE_CONFIG

    def signals(self, group: str) -> tuple[SignalScore, ...]:
        return (
            score_census(group, self.tables, self.config),
            score_location(group, self.tables, self.config),
            score_data_age(group, self.tables, self.today, self.config),
            score_interval_width(group, self.interval, self.config),
            score_evidence_age(group),
        )

    def combine(self, signals: Iterable[SignalScore]) -> Combined:
        signals = tuple(signals)
        used = tuple(s for s in signals if s.available and s.score is not None)
        unavailable = tuple(sorted(s.name for s in signals if s not in used))
        missing = f"unavailable: {', '.join(unavailable) or 'none'}"
        if not used:
            return Combined(0.0, (), unavailable, f"no signal available; {missing}", signals)
        weakest = min(used, key=lambda s: s.score)  # first in order on a tie
        assert weakest.score is not None
        reason = (
            f"weakest {weakest.name}={weakest.score:.4f} ({weakest.basis}); "
            f"used: {', '.join(s.name for s in used)}; {missing}"
        )
        return Combined(weakest.score, tuple(s.name for s in used), unavailable, reason, signals)

    def explain(self, group: str) -> Combined:
        return self.combine(self.signals(group))

    def assess(self, groups: Iterable[str]) -> dict[str, Assessment]:
        basis = f"DERIVED; min of available signals; threshold {self.threshold:.2f}"
        out = {}
        for group in sorted(set(groups)):
            result = self.explain(group)
            out[group] = Assessment(
                result.confidence, result.confidence < self.threshold, result.reason, basis
            )
        return out


# --- calibration on the replay ------------------------------------------------------------


@dataclass(frozen=True)
class GroupDay:
    group: str
    day: object  # a date in the replay; any hashable in fixtures
    match: bool  # same served and waiting counts as the full-information plan


@dataclass(frozen=True)
class CalibrationRow:
    threshold: float
    group_days: int
    unflagged_group_days: int
    matched_unflagged: int
    match_share: float | None  # None when every group-day is flagged
    groups: int
    flagged_groups: int
    flagged_share: float


@dataclass(frozen=True)
class Calibration:
    rows: tuple[CalibrationRow, ...]
    target: float
    status: str  # chosen | unreachable | not_separable
    chosen: float | None


def calibrate(
    days: Sequence[GroupDay],
    confidences: Mapping[str, float],
    thresholds: Sequence[float],
    target: float,
) -> Calibration:
    """For each threshold: the share of unflagged group-days whose decision matches the
    full-information plan, and the share of groups flagged. Choose the lowest threshold that
    meets the target. If none does ("unreachable"), or the target is already met with nothing
    flagged ("not_separable"), say so and choose nothing."""
    groups = sorted({d.group for d in days})
    rows = []
    for t in sorted(thresholds):
        flagged = {g for g in groups if confidences.get(g, 0.0) < t}
        kept = [d for d in days if d.group not in flagged]
        matched = sum(d.match for d in kept)
        rows.append(
            CalibrationRow(
                threshold=t,
                group_days=len(days),
                unflagged_group_days=len(kept),
                matched_unflagged=matched,
                match_share=matched / len(kept) if kept else None,
                groups=len(groups),
                flagged_groups=len(flagged),
                flagged_share=len(flagged) / len(groups) if groups else 0.0,
            )
        )
    meets = [r for r in rows if r.match_share is not None and r.match_share >= target - 1e-12]
    if not meets:
        return Calibration(tuple(rows), target, "unreachable", None)
    if rows and rows[0].flagged_groups == 0 and meets[0] is rows[0]:
        # The target is met with nothing flagged: the replay cannot tell thresholds apart, so
        # no threshold is chosen (the gate would never flag anything).
        return Calibration(tuple(rows), target, "not_separable", None)
    return Calibration(tuple(rows), target, "chosen", meets[0].threshold)
