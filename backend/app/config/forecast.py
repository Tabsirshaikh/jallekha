from dataclasses import dataclass


@dataclass(frozen=True)
class ForecastConfig:
    # Source: docs/JALLEKHA_FINAL_SOLUTION.md F5 ("Monthly bookings per section and city,
    # 12 months ahead").
    horizon_months: int = 12
    # Source: F5 (seasonal-naive baseline; lag-12 feature). Monthly data, yearly season.
    seasonal_period_months: int = 12
    # Source: F5 ("measured: 21.9% city MAPE, 35.1% section WAPE") and docs/features.csv T2
    # done-when ("reproduces 21.9% / 35.1% within 0.1 pp"). Basis: DERIVED (earlier backtest);
    # the exact protocol is not yet documented in the repo.
    baseline_city_mape_pct: float = 21.9
    baseline_section_wape_pct: float = 35.1
    baseline_tolerance_pp: float = 0.1
    # Source: docs/research/P3.md F5 (13 scorable months per section: 80% and 90% only).
    interval_levels: tuple[float, ...] = (0.8, 0.9)
    # Source: docs/JALLEKHA_FINAL_SOLUTION.md D17 ("577 tankers early 2024; 1,123 in 2026,
    # news"). Basis: ASSUMED; label on screen.
    fleet_tankers_early_2024: int = 577
    fleet_tankers_2026: int = 1123
    # Trips per tanker per day (F5 capacity, "ASSUMED, labelled") has no source in the
    # solution doc yet; T2 must add one with its source before using capacity.


FORECAST_CONFIG = ForecastConfig()
