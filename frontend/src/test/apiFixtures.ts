/** Rows shaped like the real T10 API answers (checked against a running API on 2026-10-04). */

export function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

const POINT_CITY = "DERIVED: sum of section points; section names are from before the Feb/Mar 2026 re-cut";
const NO_CITY_INTERVAL = "UNAVAILABLE: section intervals do not add up";
const POINT_SECTION = "DERIVED: seasonal_naive on noofbookings through 2026-01";
const INTERVAL = "DERIVED: split-conformal, section-scaled pooled residuals of the seasonal_naive backtest";

export function cityRow(month: string, point: number) {
  return {
    level: "city", section: null, month, model: "seasonal_naive", point, point_basis: POINT_CITY,
    lower_80: null, upper_80: null, lower_80_basis: NO_CITY_INTERVAL, upper_80_basis: NO_CITY_INTERVAL,
    lower_90: null, upper_90: null, lower_90_basis: NO_CITY_INTERVAL, upper_90_basis: NO_CITY_INTERVAL,
  };
}

export function sectionRow(section: string, month: string, point: number) {
  return {
    level: "section", section, month, model: "seasonal_naive", point, point_basis: POINT_SECTION,
    lower_80: point * 0.5, upper_80: point * 1.5, lower_80_basis: INTERVAL, upper_80_basis: INTERVAL,
    lower_90: 0, upper_90: point * 2, lower_90_basis: INTERVAL, upper_90_basis: INTERVAL,
  };
}

export function shortageRow(section: string, risk: string, overrides: Record<string, unknown> = {}) {
  const capacity = risk === "unknown" ? null : 24.3;
  return {
    section,
    section_basis: "REAL HMWSSB section; pre-re-cut section name (Feb/Mar 2026)",
    month: "2026-02",
    months_ahead: 1,
    forecast_bookings: 30,
    forecast_bookings_basis: "DERIVED: seasonal_naive on noofbookings through 2026-01",
    upper_80: 55.4,
    upper_80_basis: INTERVAL,
    capacity_trips: capacity,
    capacity_trips_basis: capacity === null ? "UNAVAILABLE" : "ASSUMED: A8 main_2025 fleet capacity of ST23",
    capacity_ratio: capacity === null ? null : 1.2331,
    capacity_ratio_basis: capacity === null ? "UNAVAILABLE" : "DERIVED: forecast / capacity",
    risk,
    risk_basis: "DERIVED: config rules",
    reason: `Forecast 30 bookings in 2026-02 for ${section}, risk ${risk}; groundwater data unavailable.`,
    reason_basis: "DERIVED: built from the numbers in this row",
    groundwater_status: "UNAVAILABLE",
    groundwater_status_basis: "UNAVAILABLE: D7 groundwater data not in the repo",
    reservoir_status: "NOT_USED",
    reservoir_status_basis: "flag off: reservoirs only if Q2 is approved",
    label: "DERIVED forecast vs ASSUMED capacity",
    ...overrides,
  };
}

const BT = "DERIVED: rolling-origin backtest on s2_2022-01_2024-02 (noofbookings), training before origin; origins shared by all models";

export function backtestRows() {
  const base = { interval: null, coverage: null, coverage_basis: null, note: null };
  return [
    { ...base, run: "s2_2022-01_2024-02", row_type: "origin", model: "seasonal_naive", origin: "2023-01", months: 1, section_months: 177, city_mape: 47.7567, city_mape_basis: BT, section_wape: 50.6258, section_wape_basis: BT },
    { ...base, run: "s2_2022-01_2024-02", row_type: "summary_common_origins", model: "naive_x_growth", origin: "2023-04..2024-02", months: 10, section_months: 1866, city_mape: 25.3185, city_mape_basis: BT, section_wape: 40.5941, section_wape_basis: BT },
    { ...base, run: "s2_2022-01_2024-02", row_type: "summary_common_origins", model: "seasonal_naive", origin: "2023-04..2024-02", months: 10, section_months: 1866, city_mape: 15.0943, city_mape_basis: BT, section_wape: 31.3821, section_wape_basis: BT },
    { ...base, run: "s2_2022-01_2024-02", row_type: "not_run", model: "global_gbm", origin: null, months: null, section_months: null, city_mape: null, city_mape_basis: null, section_wape: null, section_wape_basis: null, note: "not run: needs scikit-learn or lightgbm" },
    { ...base, run: "both", row_type: "selected", model: "seasonal_naive", origin: null, months: null, section_months: null, city_mape: null, city_mape_basis: null, section_wape: null, section_wape_basis: null, note: "no model beats seasonal naive on both metrics in both runs; baseline used" },
  ];
}

function metric(mean: number | null) {
  return { mean, min: mean === null ? null : mean - 0.01, max: mean === null ? null : mean + 0.01, seeds: 30, diff_vs_b1_mean: 0, diff_vs_b1_min: 0, diff_vs_b1_max: 0 };
}

export function impactResponse(replay = "main_2025", scenario = "tight") {
  const policy = (served: number) => ({
    served_share: metric(served),
    need_weighted_unmet_share: metric(0.1),
    mean_wait_days: metric(1.01),
    gini_fill_rate: metric(0.068),
    jain_fill_rate: metric(0.978),
    worst_group_fill_rate: metric(0.4),
    km_per_kl: metric(0.42),
  });
  return {
    label: "SIMULATION",
    seeds: 30,
    replay,
    scenario,
    scenario_basis: "Calibrated to the REAL Jun-Aug 2026 delivered share",
    policies: { B1: "FCFS at the nearest filling station (HMWSSB today)", JL: "JalLekha fair queue (A3) + scheduled-supply reserve (A4)" },
    results: { B1: policy(0.5), JL: policy(0.625) },
    jl_worse_than_b1: [],
    real_baselines: {
      booking_gini_basis: "DERIVED",
      booking_gini_sections: 0.780329296,
      delivered_share: { jun_aug_2026: 0.911032, main_2025: 0.99878, secondary_2023: 0.998957 },
      label: "REAL",
      source: "HMWSSB tanker bookings, Telangana Open Data Portal (D1); E4 equity summary",
    },
    duplicate_merge_share: { value: null, basis: "UNAVAILABLE", reason: "The booking replay has no complaints (live reason)." },
  };
}
