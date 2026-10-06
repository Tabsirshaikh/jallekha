"""Thinned-count predictions are observable; latent reporting rates are not ground truth."""

import numpy as np
import pytest

from app.services.underreporting import observed_mean, retention


def test_binomial_thinning_uses_need_times_access_probability():
    demand = np.array([100, 200])
    assert observed_mean(demand, np.array([0.5, 0.25])).tolist() == [50, 50]
    with pytest.raises(ValueError):
        observed_mean(demand, np.array([1.1, 0.25]))


def test_only_out_of_sample_improvement_and_sampler_diagnostics_can_retain_model():
    model = {"spearman": 0.6, "median_miss": 2, "mean_absolute_error": 10}
    baseline = {"spearman": 0.5, "median_miss": 3, "mean_absolute_error": 20}
    good = {"max_rhat": 1.005, "minimum_bulk_ess": 300, "divergences": 0}
    assert retention(model, baseline, good) == "RETAIN_OBSERVED_BOOKING_PREDICTOR"
    assert retention(model, baseline, {**good, "divergences": 1}) == "REJECT_FAILED_DIAGNOSTICS"
    assert retention({**model, "median_miss": 4}, baseline, good) == "REJECT_BASELINE_NOT_BEATEN"


def test_map_requires_successful_starts_and_agreeing_observable_predictions():
    model = {"spearman": 0.6, "median_miss": 2, "mean_absolute_error": 10}
    baseline = {"spearman": 0.5, "median_miss": 3, "mean_absolute_error": 20}
    diagnostics = {
        "fitting_method": "MAP_POINT_ESTIMATE",
        "successful_starts": 3,
        "prediction_relative_spread": 0.001,
    }
    assert retention(model, baseline, diagnostics) == "RETAIN_OBSERVED_BOOKING_PREDICTOR"
    assert (
        retention(model, baseline, {**diagnostics, "successful_starts": 0})
        == "REJECT_FAILED_DIAGNOSTICS"
    )
    assert (
        retention(model, baseline, {**diagnostics, "prediction_relative_spread": 0.5})
        == "REJECT_FAILED_DIAGNOSTICS"
    )
