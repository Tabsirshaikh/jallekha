from dataclasses import dataclass


@dataclass(frozen=True)
class ForecastConfig:
    # Source: docs/JALLEKHA_FINAL_SOLUTION.md F5 ("Monthly bookings per section and city,
    # 12 months ahead").
    horizon_months: int = 12
    # Source: F5 (seasonal-naive baseline; lag-12 feature). Monthly data, yearly season.
    seasonal_period_months: int = 12
    # Source: F5 ("measured: 21.9% city MAPE, 35.1% section WAPE") and docs/features.csv T2
    # done-when ("reproduces 21.9% / 35.1% within 0.1 pp"). Basis: DERIVED.
    baseline_city_mape_pct: float = 21.9
    baseline_section_wape_pct: float = 35.1
    baseline_tolerance_pp: float = 0.1
    # The protocol behind 21.9% / 35.1%. V-VERIFY_REVIEW.md, which recorded it, was never
    # found (data/verification/SOURCES.md). The protocol was recovered by reproduction on
    # 2026-10-03 (21.89% / 35.12% on the S2 files) and confirmed by Padmaja the same day.
    baseline_column: str = "noofbookings"
    baseline_recovered_on: str = "2026-10-03"
    baseline_protocol: str = (
        "Recovered by reproduction on 2026-10-03 (V-VERIFY_REVIEW.md was never found): "
        "forecast noofbookings; seasonal naive = same month one year earlier; Dec 2022 is "
        "missing, not zero, so Dec 2023 is not scored (13 scored months, Jan 2023 - Feb 2024); "
        "all sections present in either month, a missing section value counted as 0; city "
        "MAPE = mean of monthly absolute percentage errors of city totals; section WAPE = sum "
        "of absolute errors / sum of actuals, pooled over all section-months. 'delivered' "
        "instead of noofbookings, and only sections present in both years, also land within "
        "0.1 pp, so the data does not distinguish them."
    )
    # Source: docs/research/P3.md F5 (13 scorable months per section: 80% and 90% only).
    interval_levels: tuple[float, ...] = (0.8, 0.9)
    # Split-conformal on the rolling backtest: the first half of the scored origins calibrate,
    # the rest test. Below these month counts no coverage is reported. Basis: ASSUMED.
    min_calibration_months: int = 6
    min_test_months: int = 6
    # Seasonal naive x year-on-year growth: growth = city total of the most recent N months
    # (each with a value a year earlier) / the same months a year earlier. Basis: ASSUMED.
    growth_window_months: int = 3
    # Source: docs/JALLEKHA_FINAL_SOLUTION.md D17 ("577 tankers early 2024; 1,123 in 2026,
    # news"). Basis: ASSUMED; label on screen.
    fleet_tankers_early_2024: int = 577
    fleet_tankers_2026: int = 1123
    # Trips per tanker per day: no source. OPEN, owner to confirm. No default: the capacity
    # planner refuses to run until a sourced value is given.
    trips_per_tanker_per_day: float | None = None
    # Portal data (D1b) is used up to the month before the Feb/Mar 2026 section re-cut.
    portal_through: tuple[int, int] = (2026, 1)
    # Label on the 12-month forecast built from the portal data through Jan 2026.
    # OPEN, owner to confirm: where the published forecast should start.
    forecast_table_note: str = (
        "section names are from before the Feb/Mar 2026 re-cut, so Feb 2026 onwards cannot "
        "be compared section by section with current HMWSSB sections"
    )
    # Model choice. docs/P3_BUILD_PLAN.md T2 says only that a model must beat the baseline; it
    # does not say which metric decides. OPEN, owner to confirm. Rule applied: a model is used
    # only if it beats seasonal naive on both city MAPE and section WAPE in both backtest runs
    # (S2 and portal); otherwise seasonal naive is used.
    model_selection_rule: str = (
        "a model is used only if it beats seasonal naive on both city MAPE and section WAPE in "
        "both backtest runs (S2 and portal); otherwise seasonal naive (OPEN)"
    )
    # Covariates for a later model (weather D8, groundwater D7): not in the repo yet.
    covariates: tuple[str, ...] = ()


FORECAST_CONFIG = ForecastConfig()
