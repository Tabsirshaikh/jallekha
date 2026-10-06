"""Leave-target-out section connection-rate screen and temporal validation.

Bookings and connections are section observations. Ward need is approximate context only.
Missing months are never imputed as zero; no model infers unreported demand.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from statistics import median

import numpy as np
from scipy.stats import spearmanr

from app.config.section_checks import SECTION_CHECK_CONFIG, SectionCheckConfig


@dataclass(frozen=True)
class AnnualSection:
    section: str
    division: str
    year: int
    bookings: int
    connections: float | None
    flats_share: float | None
    booking_months: int
    billing_months: int

    def __post_init__(self):
        if self.bookings < 0 or (
            self.connections is not None
            and (not math.isfinite(self.connections) or self.connections < 0)
        ):
            raise ValueError("Invalid section counts")

    def status(self, config=SECTION_CHECK_CONFIG):
        if not self.connections or self.flats_share is None:
            return "MISSING_DOMESTIC_CONNECTIONS"
        if (
            self.booking_months != config.months_per_year
            or self.billing_months != config.months_per_year
        ):
            return "INCOMPLETE_SOURCE_YEAR"
        return "COMPLETE"

    @property
    def rate(self):
        return 1000 * self.bookings / self.connections if self.connections else None


def reference(target, cohort, config):
    peers = [
        s
        for s in cohort
        if s.section != target.section
        and s.division == target.division
        and s.status(config) == "COMPLETE"
    ]
    peers.sort(
        key=lambda s: (
            abs(math.log(s.connections / target.connections))
            + config.flats_distance_weight * abs(s.flats_share - target.flats_share),
            s.section,
        )
    )
    peers = peers[: config.peer_count]
    if len(peers) < config.minimum_peers:
        return None, []
    return median(s.rate for s in peers), [s.section for s in peers]


def screen(current, training, needs, config: SectionCheckConfig = SECTION_CHECK_CONFIG):
    """Threshold learned from train-year ratios; current peer rates are descriptive only."""
    ratios = []
    for target in training:
        if target.status(config) != "COMPLETE":
            continue
        rate, _ = reference(target, training, config)
        if rate and rate > 0:
            ratios.append(target.rate / rate)
    cutoff = float(np.quantile(ratios, config.ratio_quantile)) if ratios else None
    # Caller supplies one need value per section. Duplicate ward values must not inflate the
    # threshold; the builder passes its unique-ward cohort median explicitly via NEED_MEDIAN.
    need_median = needs.get("NEED_MEDIAN")
    if need_median is None and needs:
        need_median = float(np.quantile(list(needs.values()), config.need_quantile))
    output = []
    for target in sorted(current, key=lambda s: s.section):
        status = target.status(config)
        rate, peers = reference(target, current, config) if status == "COMPLETE" else (None, [])
        identity = f"{target.division}:{target.section}"
        need = needs.get(identity, needs.get(target.section))
        if status == "COMPLETE" and rate is None:
            status = "INSUFFICIENT_COMPARABLE_SECTIONS"
        ratio = target.rate / rate if rate and target.rate is not None else None
        flag = bool(
            ratio is not None
            and cutoff is not None
            and ratio < cutoff
            and need is not None
            and need_median is not None
            and need > need_median
        )
        output.append(
            {
                "section_id": identity,
                "section": target.section,
                "division": target.division,
                "period_year": target.year,
                "bookings": target.bookings,
                "bookings_basis": "REAL",
                "booking_months": target.booking_months,
                "billing_months": target.billing_months,
                "domestic_connections": target.connections,
                "connections_basis": "DERIVED" if target.connections else "UNAVAILABLE",
                "flats_connection_share": target.flats_share,
                "flats_share_basis": "DERIVED" if target.flats_share is not None else "UNAVAILABLE",
                "rate": target.rate if target.status(config) == "COMPLETE" else None,
                "rate_basis": "DERIVED" if target.status(config) == "COMPLETE" else "UNAVAILABLE",
                "reference_rate": rate,
                "reference_basis": "DERIVED" if rate is not None else "UNAVAILABLE",
                "peer_sections": peers,
                "ratio": ratio,
                "ratio_basis": "DERIVED" if ratio is not None else "UNAVAILABLE",
                "ratio_threshold": cutoff,
                "threshold_basis": "ASSUMED",
                "wad_context": need,
                "wad_cohort_median": need_median,
                "need_basis": "DERIVED_APPROXIMATE" if need is not None else "UNAVAILABLE",
                "field_check_candidate": flag,
                "status": "FIELD_CHECK_CANDIDATE" if flag else status,
                "ground_truth_status": "NOT_YET_CHECKED_ON_GROUND",
                "basis": "DERIVED",
            }
        )
    return output


def metrics(predicted, observed):
    positive = [(p, o) for p, o in zip(predicted, observed, strict=True) if p > 0 and o > 0]
    misses = [max(p / o, o / p) for p, o in positive]
    correlation = (
        float(spearmanr(predicted, observed).statistic)
        if len(set(predicted)) > 1 and len(set(observed)) > 1
        else None
    )
    return {
        "mean_absolute_error": (
            sum(abs(p - o) for p, o in zip(predicted, observed, strict=True)) / len(observed)
            if observed
            else None
        ),
        "spearman": correlation,
        "median_miss": median(misses) if misses else None,
        "within_2x": sum(m <= 2 for m in misses) / len(misses) if misses else None,
        "count": len(observed),
        "positive_pairs": len(positive),
        "zero_pairs_excluded_from_miss": len(observed) - len(positive),
        "basis": "DERIVED",
    }


def backtest(training, testing, config=SECTION_CHECK_CONFIG):
    """2024-only predictions; both candidates use train-year connection exposure."""
    if any(s.year != config.train_year for s in training) or any(
        s.year != config.period_year for s in testing
    ):
        raise ValueError("Backtest years differ from configured temporal split")
    complete = [s for s in training if s.status(config) == "COMPLETE"]
    actual = {(s.division, s.section): s for s in testing if s.status(config) == "COMPLETE"}
    city_rate = sum(s.bookings for s in complete) / sum(s.connections for s in complete)
    predictions = []
    for target in sorted(complete, key=lambda s: s.section):
        rate, peers = reference(target, complete, config)
        identity = (target.division, target.section)
        if rate is None or identity not in actual:
            continue
        predictions.append(
            {
                "section": target.section,
                "expected": rate * target.connections / 1000,
                "baseline": city_rate * target.connections,
                "observed": actual[identity].bookings,
                "peers": peers,
                "basis": "DERIVED",
            }
        )
    observed = [r["observed"] for r in predictions]
    return {
        "train_year": config.train_year,
        "test_year": config.period_year,
        "exposure_year": config.train_year,
        "peer": metrics([r["expected"] for r in predictions], observed),
        "baseline": metrics([r["baseline"] for r in predictions], observed),
        "predictions": predictions,
        "basis": "DERIVED",
    }
