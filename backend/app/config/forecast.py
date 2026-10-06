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
    # Model choice (docs/REMAINING_WORK.md "Research follow-ups" A; applied at the owner's
    # request on 2026-10-06). Judged on the longest rolling-origin backtest (portal run, origins
    # every model shares with at least selection_min_yoy_months of year-on-year training data);
    # the S2 run only checks that the documented 21.9% / 35.1% baseline reproduces. A candidate
    # replaces seasonal naive when it is better on city MAPE and section WAPE AND the one-sided
    # Diebold-Mariano test with the Harvey-Leybourne-Newbold correction on the monthly section
    # absolute errors rejects equal accuracy at selection_alpha (Hyndman & Athanasopoulos, FPP3
    # time-series cross-validation; statsmodels diebold_mariano_test). The published forecast
    # must have the same minimum history. On a statistical tie the simpler model wins.
    model_selection_rule: str = (
        "longest backtest (portal), shared origins with >= 12 year-on-year training months: a "
        "candidate is used if it beats seasonal naive on city MAPE and section WAPE and the HLN "
        "Diebold-Mariano test (one-sided, 5%) rejects equal accuracy; simplest model on a tie"
    )
    selection_alpha: float = 0.05
    selection_min_yoy_months: int = 12
    # Covariates of the gradient-boosting candidate: weather D8 (Open-Meteo, REAL reanalysis).
    # Groundwater D7: Telangana Ground Water Department wells (data/raw/d7_groundwater, item 17);
    # a candidate model adds each section's anomaly (global_gbm_groundwater).
    covariates: tuple[str, ...] = ("weather_d8",)
    weather_file: str = "data/raw/d8_weather/open_meteo_hyderabad_daily.csv"
    # D8b: monthly weather per section from the TGDPS stations of its nearest mandal
    # (scripts/forecast/build_section_weather.py; research follow-up B).
    section_weather_file: str = "data/derived/weather/section_monthly.csv"
    # D7: groundwater anomaly per section and month (scripts/forecast/build_groundwater.py).
    groundwater_file: str = "data/derived/groundwater/section_anomaly.csv"
    # Normal weather per calendar month: 2019-2021, the three years before the first booking
    # month (Jan 2022), so the normal never contains a month that is forecast or scored.
    weather_normal_years: tuple[int, int] = (2019, 2021)
    # Recent weather before the forecast origin: rainfall over 6 months (one monsoon season
    # feeds next summer's groundwater), maximum temperature over 3 months. Basis: ASSUMED.
    recent_rain_months: int = 6
    recent_heat_months: int = 3
    # Global gradient-boosting candidate (F5: "one global gradient-boosting model pooled over all
    # sections with month, lag-12, trend, weather"). scikit-learn HistGradientBoostingRegressor
    # on log(bookings + 1) - log(same month last year + 1), so it learns a correction to seasonal
    # naive (Grinsztajn et al. 2022: tree models suit small tabular data). Absolute-error loss
    # because WAPE is an absolute-error measure. Settings fixed before any backtest was run and
    # never tuned on it (so the backtest stays an honest test); strong regularisation for about
    # 200 sections x 1-3 years. Basis: ASSUMED.
    gbm_learning_rate: float = 0.05
    gbm_max_iter: int = 200
    gbm_max_leaf_nodes: int = 15
    gbm_min_samples_leaf: int = 20
    gbm_l2_regularization: float = 1.0
    gbm_random_state: int = 0
    # Least training data: year-on-year months and section-months. Basis: ASSUMED.
    gbm_min_training_months: int = 2
    gbm_min_training_rows: int = 100


FORECAST_CONFIG = ForecastConfig()


@dataclass(frozen=True)
class ShortageConfig:
    """T8 shortage early warning (F6): T2 forecast versus capacity, per section and month."""

    # Source: docs/features.csv T8 done-when ("Risk list 1-3 months ahead with reasons").
    months_ahead: tuple[int, ...] = (1, 2, 3)
    # Risk rules, on bookings forecast / capacity trips (one booking = one trip, ASSUMED as in
    # T2). high: the point forecast reaches risk_high_ratio x capacity; medium: the point
    # reaches risk_medium_ratio x capacity, or the upper 80% bound reaches capacity; low
    # otherwise; unknown without a capacity. Ratios ASSUMED, OPEN, owner to confirm.
    risk_high_ratio: float = 1.0
    risk_medium_ratio: float = 0.85
    # Capacity: A8's fleet scenario on main (P2), reused: 1,150 tankers (REAL, news) x 9 trips
    # per tanker per day (DERIVED) split over 90 stand-in stations in proportion to their
    # bookings (data/verification/sandbox_checks.json); each station's trips are shared over
    # its home sections in proportion to their Mar-Jul 2025 bookings (section_points.csv).
    # The split and its use for 2026 months are ASSUMED.
    a8_checks_path: str = "data/verification/sandbox_checks.json"
    a8_sections_path: str = "data/derived/sandbox/section_points.csv"
    a8_replay: str = "main_2025"
    a8_scenario: str = "fleet"
    # Groundwater (D7, item 17): each section's anomaly (median of TGGWD wells within the radius,
    # data/derived/groundwater/section_anomaly.csv) is given in the reason; it does not change
    # the risk level (a groundwater rule would be OPEN, owner to confirm). The radius must match
    # scripts/forecast/build_groundwater.py RADIUS_KM. Without the file the note below is used.
    groundwater_path: str = "data/derived/groundwater/section_anomaly.csv"
    groundwater_radius_km: float = 5.0
    groundwater_note: str = "groundwater data unavailable"
    # Reservoir levels: only if Q2 is approved (docs/features.csv T8 note). Off; no data.
    reservoirs_enabled: bool = False
    # T2's label: section names are from before the Feb/Mar 2026 re-cut.
    section_label: str = "pre-re-cut section name (Feb/Mar 2026)"
    forecast_table_path: str = "data/derived/forecast_table.csv"
    output_path: str = "data/derived/shortage_risk.csv"


SHORTAGE_CONFIG = ShortageConfig()
