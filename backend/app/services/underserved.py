"""Need-side screening. Missing reports cannot establish unreported water need."""

from __future__ import annotations

import math
import statistics
from dataclasses import asdict, dataclass

from app.config.underserved import UNDERSERVED_CONFIG, UnderservedConfig


@dataclass(frozen=True)
class AreaEvidence:
    ward_id: str
    ward_name: str
    households: float | None = None
    wad: float | None = None
    non_tap_share: float | None = None
    cad: float | None = None
    hardship: float | None = None
    bookings: int | None = None
    period_year: int | None = None
    period_months: int = 12
    household_reference_year: int | None = None
    need_reference_year: int | None = None
    census_location_validated: bool = False
    booking_transfer_validated: bool = False
    booking_period_complete: bool = False
    basis: str = "REAL"
    geography_version: str = "GHMC_2016_150"
    growth_ratio: float | None = None
    growth_quality: str = "UNAVAILABLE"


def finite(value):
    return isinstance(value, int | float) and not isinstance(value, bool) and math.isfinite(value)


def validate_config(config: UnderservedConfig) -> None:
    if config.minimum_areas < 2 or config.peer_count < 1:
        raise ValueError("Minimum cohort and peer counts must be positive")
    if not 0 <= config.ratio_quantile <= 1 or not 0 <= config.wad_quantile <= 1:
        raise ValueError("Configured quantiles must lie in [0, 1]")
    if not 0 < config.credible_mass < 1:
        raise ValueError("Credible mass must lie strictly between 0 and 1")
    if config.max_reference_age_years < 0 or config.max_model_areas < config.minimum_areas:
        raise ValueError("Invalid reference age or model cohort bounds")
    if config.chains < 2 or config.draws < 1 or config.tune < 0:
        raise ValueError("Bayesian sampling requires at least two chains and positive draws")
    if config.minimum_bulk_ess <= 0 or config.max_rhat < 1:
        raise ValueError("Invalid posterior diagnostic thresholds")


def blockers(area: AreaEvidence, config=UNDERSERVED_CONFIG) -> list[str]:
    reasons = []
    if not isinstance(area.ward_id, str) or not area.ward_id.strip():
        reasons.append("WARD_ID_UNAVAILABLE")
    if not isinstance(area.ward_name, str) or not area.ward_name.strip():
        reasons.append("WARD_NAME_UNAVAILABLE")
    if not isinstance(area.census_location_validated, bool):
        reasons.append("INVALID_CENSUS_VALIDATION_STATE")
    elif not area.census_location_validated:
        reasons.append("UNVALIDATED_CENSUS_LOCATION")
    if not isinstance(area.booking_transfer_validated, bool):
        reasons.append("INVALID_BOOKING_TRANSFER_STATE")
    elif not area.booking_transfer_validated:
        reasons.append("UNVALIDATED_BOOKING_TRANSFER")
    if not isinstance(area.booking_period_complete, bool):
        reasons.append("INVALID_BOOKING_PERIOD_STATE")
    elif not area.booking_period_complete:
        reasons.append("INCOMPLETE_BOOKING_PERIOD")
    if not finite(area.households) or area.households <= 0:
        reasons.append("HOUSEHOLD_EXPOSURE_UNAVAILABLE")
    if not isinstance(area.bookings, int) or isinstance(area.bookings, bool) or area.bookings < 0:
        reasons.append("WARD_BOOKINGS_UNAVAILABLE")
    for key in ("wad", "non_tap_share"):
        value = getattr(area, key)
        if not finite(value) or not 0 <= value <= 1:
            reasons.append(f"INVALID_OR_MISSING_{key.upper()}")
    if not any(finite(v) and 0 <= v <= 1 for v in (area.cad, area.hardship)):
        reasons.append("CAD_AND_HARDSHIP_UNAVAILABLE")
    if any(v is not None and (not finite(v) or not 0 <= v <= 1) for v in (area.cad, area.hardship)):
        reasons.append("INVALID_CONTEXT_SHARE")
    if not isinstance(area.period_year, int) or isinstance(area.period_year, bool):
        reasons.append("BOOKING_PERIOD_UNAVAILABLE")
    else:
        for field, code in (
            ("household_reference_year", "HOUSEHOLD_REFERENCE"),
            ("need_reference_year", "NEED_REFERENCE"),
        ):
            reference = getattr(area, field)
            if (
                not isinstance(reference, int)
                or isinstance(reference, bool)
                or not 0 <= area.period_year - reference <= config.max_reference_age_years
            ):
                reasons.append(f"STALE_OR_MISSING_{code}")
    if (
        not isinstance(area.period_months, int)
        or isinstance(area.period_months, bool)
        or not 1 <= area.period_months <= 12
    ):
        reasons.append("INVALID_PERIOD_EXPOSURE")
    if area.basis not in ("REAL", "SIMULATED"):
        reasons.append("INVALID_INPUT_BASIS")
    if area.geography_version != config.geography_version:
        reasons.append("UNSUPPORTED_GEOGRAPHY_VERSION")
    return reasons


def quantile(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def validate_cohort(areas, config=UNDERSERVED_CONFIG):
    validate_config(config)
    if len({a.ward_id for a in areas}) != len(areas):
        raise ValueError("Duplicate ward identifiers")
    if any(blockers(a, config) for a in areas):
        raise ValueError("Model input failed evidence gates")
    cohorts = {(a.basis, a.period_year, a.period_months, a.geography_version) for a in areas}
    if len(cohorts) > 1:
        raise ValueError("Do not mix periods, geography versions, or real/simulated cohorts")


def peer_median(areas, config=UNDERSERVED_CONFIG):
    """Leave-one-area-out neighbours selected exclusively from need-side covariates."""
    validate_cohort(areas, config)
    if len(areas) <= config.peer_count:
        return {}
    vectors = {a.ward_id: (math.log(a.households), a.wad, a.non_tap_share) for a in areas}
    scales = [statistics.pstdev(v[k] for v in vectors.values()) or 1.0 for k in range(3)]
    result = {}
    for area in areas:
        vector = vectors[area.ward_id]
        peers = sorted(
            (a for a in areas if a.ward_id != area.ward_id),
            key=lambda a: (
                sum(((vector[k] - vectors[a.ward_id][k]) / scales[k]) ** 2 for k in range(3)),
                a.ward_id,
            ),
        )[: config.peer_count]
        rate = statistics.median(a.bookings / (a.households * a.period_months) for a in peers)
        expected = rate * area.households * area.period_months
        result[area.ward_id] = {
            "expected": expected,
            "ratio": area.bookings / expected if expected > 0 else None,
            "ratio_lower": None,
            "ratio_upper": None,
            "peers": [a.ward_id for a in peers],
            "interval_kind": "UNAVAILABLE_PEER_MEDIAN_HAS_NO_POSTERIOR",
        }
    return result


def candidate_flags(areas, scores, config=UNDERSERVED_CONFIG):
    """Strict need-side thresholds; quantile ties can exceed the nominal bottom fraction."""
    valid_ratios = [r["ratio"] for r in scores.values() if finite(r.get("ratio"))]
    if not valid_ratios:
        return set(), {}
    threshold = {
        "ratio": quantile(valid_ratios, config.ratio_quantile),
        "wad": quantile([a.wad for a in areas], config.wad_quantile),
        "cad": statistics.median([a.cad for a in areas if a.cad is not None])
        if any(a.cad is not None for a in areas)
        else None,
        "hardship": statistics.median([a.hardship for a in areas if a.hardship is not None])
        if any(a.hardship is not None for a in areas)
        else None,
    }
    flagged = set()
    for area in areas:
        score = scores.get(area.ward_id, {})
        ratio = score.get("ratio")
        context = any(
            value is not None and threshold[key] is not None and value > threshold[key]
            for key, value in (("cad", area.cad), ("hardship", area.hardship))
        )
        interval_ok = score.get("ratio_upper") is None or score["ratio_upper"] < 1
        if (
            finite(ratio)
            and ratio <= threshold["ratio"]
            and ratio < 1
            and area.wad > threshold["wad"]
            and context
            and interval_ok
        ):
            flagged.add(area.ward_id)
    return flagged, threshold


def screen(areas, model_results=None, config: UnderservedConfig = UNDERSERVED_CONFIG):
    areas = sorted(areas, key=lambda a: a.ward_id)
    if len({a.ward_id for a in areas}) != len(areas):
        raise ValueError("Duplicate ward identifiers")
    eligible = [a for a in areas if not blockers(a, config)]
    validate_cohort(eligible, config)
    enough = len(eligible) >= config.minimum_areas
    peer = peer_median(eligible, config) if enough else {}
    models = model_results or {}
    scores = {"PEER_MEDIAN": peer} if peer else {}
    for name, result in models.items():
        if (
            enough
            and result.get("status") == "COMPLETE"
            and result.get("prediction_scope") == "OUT_OF_FOLD"
        ):
            if set(result["scores"]) != {a.ward_id for a in eligible}:
                raise ValueError("Model scores do not match the gated cohort")
            scores[name] = result["scores"]
    flags, thresholds = {}, {}
    for name, values in scores.items():
        flags[name], thresholds[name] = candidate_flags(eligible, values, config)
    required = {"PEER_MEDIAN", "NB", "BYM2", "BYM2_SHRINKAGE"}
    stability_available = required <= flags.keys()
    pairwise = {}
    if stability_available:
        names = sorted(required)
        for i, first in enumerate(names):
            for second in names[i + 1 :]:
                union = flags[first] | flags[second]
                pairwise[f"{first}:{second}"] = (
                    len(flags[first] & flags[second]) / len(union) if union else 1.0
                )
    rows, field_checks, data_review = [], [], []
    for area in areas:
        missing = blockers(area, config)
        if not missing and not enough:
            missing = ["INSUFFICIENT_COMPARABLE_AREAS"]
        voted = [name for name, values in flags.items() if area.ward_id in values]
        if missing:
            status, candidate = "DATA_REVIEW_REQUIRED", None
        elif stability_available:
            candidate = required <= set(voted)
            status = (
                "STABLE_FIELD_CHECK_CANDIDATE"
                if candidate
                else ("MODEL_SENSITIVE_REVIEW" if voted else "NO_SCREENING_FLAG")
            )
        else:
            candidate = area.ward_id in flags.get("PEER_MEDIAN", set())
            status = "PEER_ONLY_FIELD_CHECK" if candidate else "NO_PEER_SCREENING_FLAG"
        per_model = {name: values[area.ward_id] for name, values in scores.items()}
        reasons = [{"code": code, "value": None, "basis": "UNAVAILABLE"} for code in missing]
        if candidate:
            for name in voted:
                reasons.extend(
                    [
                        {
                            "code": "LOW_OBSERVED_REFERENCE_RATIO",
                            "model": name,
                            "value": per_model[name]["ratio"],
                            "threshold": thresholds[name]["ratio"],
                            "basis": "SIMULATED" if area.basis == "SIMULATED" else "DERIVED",
                        },
                        {
                            "code": "WAD_ABOVE_COHORT_QUANTILE",
                            "value": area.wad,
                            "threshold": thresholds[name]["wad"],
                            "basis": area.basis,
                        },
                    ]
                )
            for key in ("cad", "hardship"):
                value = getattr(area, key)
                medians = [t[key] for t in thresholds.values() if t[key] is not None]
                if value is not None and medians and value > medians[0]:
                    reasons.append(
                        {
                            "code": f"{key.upper()}_ABOVE_COHORT_MEDIAN",
                            "value": value,
                            "threshold": medians[0],
                            "basis": area.basis,
                        }
                    )
        row = {
            "ward_id": area.ward_id,
            "ward_name": area.ward_name,
            "status": status,
            "field_check_candidate": candidate,
            "field_check_candidate_basis": "UNAVAILABLE"
            if candidate is None
            else ("SIMULATED" if area.basis == "SIMULATED" else "DERIVED"),
            "input_basis": area.basis,
            "geography_version": area.geography_version,
            "observed_bookings": area.bookings,
            "observed_bookings_basis": (area.basis if area.bookings is not None else "UNAVAILABLE"),
            "model_scores": per_model,
            "model_scores_basis": ("SIMULATED" if area.basis == "SIMULATED" else "DERIVED")
            if per_model
            else "UNAVAILABLE",
            "flagged_variants": voted,
            "stability_evaluated": stability_available,
            "growth_ratio_context_only": area.growth_ratio,
            "growth_ratio_basis": "DERIVED" if area.growth_ratio is not None else "UNAVAILABLE",
            "growth_quality": area.growth_quality,
            "reasons": reasons,
            "action": "Send someone to check; no allocation or entitlement change"
            if candidate
            else "Review missing evidence"
            if missing
            else "No automatic service decision",
        }
        rows.append(row)
        if candidate:
            field_checks.append(row)
        if missing:
            data_review.append(row)
    return {
        "schema_version": "E5-1",
        "rows": rows,
        "field_check_list": field_checks,
        "data_review_queue": data_review,
        "config": asdict(config),
        "model_diagnostics": {
            name: {k: v for k, v in result.items() if k != "scores"}
            for name, result in models.items()
        },
        "thresholds": thresholds,
        "pairwise_flag_jaccard": pairwise if stability_available else None,
        "summary": {
            "area_count": len(rows),
            "eligible_count": len(eligible),
            "screened_count": len(eligible) if enough else 0,
            "data_review_count": len(data_review),
            "field_check_count": len(field_checks),
            "stability_evaluated": stability_available,
            "real_world_accuracy": None,
            "ground_truth_count": 0,
        },
        "limitations": [
            "Low bookings cannot identify unmet need or a reporting probability.",
            "Reference mean is a need-covariate model benchmark; interval covers that mean only.",
            (
                "Peer matching excludes each target; Bayesian reference fits are in-sample "
                "unless held out."
            ),
            "Only officer field observations supply empirical labels; model flags are hypotheses.",
            (
                "Configured quantiles/priors are engineering choices; ties can exceed "
                "the nominal fraction."
            ),
            "Growth signals are context only; they never scale household exposure.",
        ],
    }
