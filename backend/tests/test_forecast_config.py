import dataclasses

import pytest

from app.config.forecast import FORECAST_CONFIG, ForecastConfig


def test_forecast_config_values_match_solution_doc() -> None:
    assert FORECAST_CONFIG.horizon_months == 12
    assert FORECAST_CONFIG.seasonal_period_months == 12
    assert FORECAST_CONFIG.baseline_city_mape_pct == 21.9
    assert FORECAST_CONFIG.baseline_section_wape_pct == 35.1
    assert FORECAST_CONFIG.fleet_tankers_early_2024 == 577
    assert FORECAST_CONFIG.fleet_tankers_2026 == 1123


def test_interval_levels_are_valid_probabilities() -> None:
    assert all(0 < level < 1 for level in FORECAST_CONFIG.interval_levels)
    assert 0.95 not in FORECAST_CONFIG.interval_levels


def test_forecast_config_is_frozen() -> None:
    with pytest.raises(dataclasses.FrozenInstanceError):
        FORECAST_CONFIG.horizon_months = 6  # type: ignore[misc]
    assert isinstance(FORECAST_CONFIG, ForecastConfig)
