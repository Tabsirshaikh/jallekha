/** Shaped like docs/api_examples/ward_report_card.get.json and ward_sms_summary.get.json (SYNTHETIC example). */
import type { ApiSmsSummary, ApiWardCard } from "../wardCardAdapter";

export function wardCard(overrides: Partial<ApiWardCard> = {}): ApiWardCard {
  return {
    ward_id: "relation/7848824",
    ward_name: "Ward 105 Gachibowli",
    geography_version: "GHMC_2016_150",
    quality_flags: ["HISTORICAL"],
    need: { service_class: "piped_regularity_unknown", need_weight: 1.716028, need_basis: "DERIVED", class_basis: "CENSUS_2011_RULE" },
    bookings: { period: { from: "2022-01", to: "2024-02", missing_months: ["2022-12"] }, bookings: 66431, bookings_per_1000: 1202.2, basis: "DERIVED_APPROXIMATE", mapping_status: "APPROXIMATE_SECTION_POINT_IN_WARD" },
    deliveries: {
      value: { window_days: 30, from: "2026-09-05T06:00:00+00:00", to: "2026-10-05T06:00:00+00:00", stops: [{ stop_id: "stop-g1", basis: "SYNTHETIC", ward_basis: "DERIVED" }], started: 3, by_outcome: { Confirmed: 2, Disputed: 1, Unconfirmed: 0, Failed: 0, open: 0 }, confirmed_litres: 10000 },
      basis: "SYNTHETIC",
      reason: null,
    },
    debt: {
      value: { debt_litres: 120000, debt_loads: 24, cap_litres: 910000, in_debt_since: "2026-10-03", days_in_debt: 1, alert_raised: false, settled_through: "2026-10-03", last_day: { day: "2026-10-03", alert: false } },
      basis: "DERIVED (A6: litres the approved plan gave the ward's stops minus one load per Confirmed delivery)",
      reason: null,
    },
    schedule: {
      value: { plan_id: "plan-2026-10-03-41c27fd9", day: "2026-10-03", status: "APPROVED", source: "supplied_bookings", booked: { group: "ward:relation/7848824", served: 4, waiting: 0 }, stops: [{ stop_id: "stop-g1", litres: 130000, loads: 26 }] },
      basis: "Plan from 12 bookings supplied for the day, not the replay",
      reason: null,
    },
    ...overrides,
  };
}

export const noValue = (reason: string) => ({ value: null, basis: "UNAVAILABLE", reason });

export function smsSummary(lang = "en", used = "en"): ApiSmsSummary {
  return {
    ward_id: "relation/7848824",
    lang_requested: lang,
    lang_used: used,
    text: "Ward 105 Gachibowli: 66431 tanker bookings 2022-01 to 2024-02; need class piped_regularity_unknown. Deliveries (last 30 days): 3 started, 2 confirmed.",
  };
}
