"""Observable mean of a Binomial-thinned negative-binomial latent demand model.

The observed likelihood is NB(mu * p, alpha); NB thinning leaves alpha unchanged. Demand
and probability are prior-dependent without field labels. Never publish them as identified.
"""

import numpy as np

from app.config.underreporting import UNDERREPORTING_CONFIG as CONFIG


def observed_mean(demand, probability):
    demand, probability = np.asarray(demand), np.asarray(probability)
    if (
        np.any(~np.isfinite(demand))
        or np.any(demand < 0)
        or np.any(~np.isfinite(probability))
        or np.any((probability < 0) | (probability > 1))
    ):
        raise ValueError("Invalid demand or reporting probability")
    return demand * probability


def retention(model, baseline, diagnostics, config=CONFIG):
    if diagnostics.get("fitting_method") == "MAP_POINT_ESTIMATE":
        valid = (
            diagnostics["successful_starts"] >= config.minimum_successful_starts
            and np.isfinite(diagnostics["prediction_relative_spread"])
            and diagnostics["prediction_relative_spread"]
            <= config.maximum_prediction_relative_spread
        )
    else:
        valid = (
            np.isfinite(diagnostics["max_rhat"])
            and diagnostics["max_rhat"] <= config.max_rhat
            and diagnostics["minimum_bulk_ess"] >= config.minimum_bulk_ess
            and diagnostics["divergences"] == 0
        )
    if not valid:
        return "REJECT_FAILED_DIAGNOSTICS"
    if not (
        model["spearman"] is not None
        and baseline["spearman"] is not None
        and model["spearman"] > baseline["spearman"]
        and model["median_miss"] < baseline["median_miss"]
        and model["mean_absolute_error"] < baseline["mean_absolute_error"]
    ):
        return "REJECT_BASELINE_NOT_BEATEN"
    return "RETAIN_OBSERVED_BOOKING_PREDICTOR"


def fit(exposure, access, observed, prior_mean, config=CONFIG):
    """Only caller-supplied training observations enter this new non-spatial PyMC model."""
    import sys

    import pymc as pm
    import pytensor

    if sys.platform == "win32":
        # The installed MinGW is 32-bit; use PyTensor's supported Python linker, as the
        # existing E5 non-spatial tests do. This never invokes the archived BYM2 fits.
        pytensor.config.cxx = ""

    exposure, access, observed = map(np.asarray, (exposure, access, observed))
    center = np.log(observed.sum() / exposure.sum() / prior_mean)
    with pm.Model():
        intercept = pm.Normal("demand_intercept", center, config.intercept_sd)
        reporting = pm.Beta(
            "reporting_anchor",
            prior_mean * config.reporting_prior_strength,
            (1 - prior_mean) * config.reporting_prior_strength,
        )
        coefficients = pm.HalfNormal(
            "access_coefficients", config.access_coefficient_sd, shape=access.shape[1]
        )
        probability = pm.math.sigmoid(
            pm.math.log(reporting / (1 - reporting)) - pm.math.dot(access, coefficients)
        )
        spread = pm.HalfNormal("inverse_sqrt_dispersion", 1)
        pm.NegativeBinomial(
            "bookings",
            mu=exposure * pm.math.exp(intercept) * probability,
            alpha=1 / spread**2,
            observed=observed,
        )
        rng = np.random.default_rng(config.seed)
        starts = []
        for index in range(config.map_starts):
            initial = {
                "demand_intercept": center + rng.normal(0, config.initial_jitter_sd),
                "reporting_anchor": prior_mean,
                "access_coefficients": np.exp(
                    rng.normal(0, config.initial_jitter_sd, access.shape[1])
                ),
                "inverse_sqrt_dispersion": np.exp(rng.normal(0, config.initial_jitter_sd)),
            }
            point, raw = pm.find_MAP(
                start=initial,
                method="L-BFGS-B",
                maxeval=config.map_max_evaluations,
                return_raw=True,
                progressbar=False,
            )
            logits = (
                np.log(point["reporting_anchor"] / (1 - point["reporting_anchor"]))
                - access @ point["access_coefficients"]
            )
            prediction = exposure * np.exp(point["demand_intercept"]) / (1 + np.exp(-logits))
            starts.append(
                {
                    "index": index,
                    "success": bool(raw.success),
                    "objective": float(raw.fun),
                    "prediction": prediction,
                }
            )
    finite = [
        s for s in starts if np.isfinite(s["objective"]) and np.all(np.isfinite(s["prediction"]))
    ]
    if not finite:
        raise ValueError("No finite MAP point estimate")
    successful = [s for s in finite if s["success"]]
    best = min(successful or finite, key=lambda s: s["objective"])
    spread = max(
        (
            float(
                np.max(
                    np.abs(s["prediction"] - best["prediction"]) / np.maximum(best["prediction"], 1)
                )
            )
            for s in successful
        ),
        default=1.0,
    )
    diagnostics = {
        "fitting_method": "MAP_POINT_ESTIMATE",
        "successful_starts": len(successful),
        "prediction_relative_spread": spread,
        "starts": [{k: v for k, v in s.items() if k != "prediction"} for s in starts],
        "posterior_diagnostics": None,
        "posterior_basis": "UNAVAILABLE: point estimates, no MCMC posterior or intervals",
    }
    return best["prediction"], diagnostics
