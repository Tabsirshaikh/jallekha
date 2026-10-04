/** Explain and contest answers shaped like the real T10 API (checked against a running API on 2026-10-04). Synthetic ids. */

const NO_DEBT = { available: false, account_id: null, debt_litres: null, cap_litres: null, in_debt_since: null };

export function wardResponse() {
  return {
    explanation: {
      ward_id: "relation/7848799", ward_name: "Ward 91 Khairatabad", status: "census",
      service_class: "piped_regularity_unknown", class_basis: "CENSUS_2011_RULE", join_status: "AREAL_2009_CROSSWALK",
      allocation_eligible: true, review_required: true,
      quality_flags: ["HISTORICAL", "FACILITIES_UNAVAILABLE", "APPROX_AREAL_CROSSWALK", "MIXED_2009_SOURCES"],
      check_reasons: ["E2_REVIEW_REQUIRED"], census_label: "Census 2011 / historical 2016 geography",
      need_weight: 1.354999 as number | null, need_basis: "DERIVED" as string | null,
      wad: 0.078268 as number | null, wad_basis: "DERIVED" as string | null,
      cad: 0.082556 as number | null, cad_basis: "DERIVED" as string | null,
      hardship: 0.115907 as number | null, hardship_basis: "DERIVED" as string | null,
      households: 12959 as number | null, households_basis: "DERIVED" as string | null,
      entitlement: 17559.432041 as number | null,
      critical_facilities: null as number | null, critical_facilities_basis: "UNAVAILABLE" as string | null,
      debt: NO_DEBT,
    },
  };
}

export function noCensusWard() {
  const response = wardResponse();
  Object.assign(response.explanation, {
    ward_id: "relation/7853000", ward_name: "Ward 150 Sample", status: "no_census_data", allocation_eligible: false,
    join_status: "NO_2009_MATCH", need_weight: null, need_basis: null, wad: null, wad_basis: null, cad: null, cad_basis: null,
    hardship: null, hardship_basis: null, households: null, households_basis: null, entitlement: null,
  });
  return response;
}

export const BOOKING_ID = "2025-04-29:MANIKONDA (DIV 18):00387";

export function bookingResponse() {
  return {
    explanation: {
      booking_id: BOOKING_ID, status: "waiting", group: "ward:relation/7848824", tier: 2,
      arrived_at: "2025-04-29T15:20:13+05:30", place: 387 as number | null, position: null as number | null,
      reason: null as string | null, arrival_rank: null as number | null, entitlement: null as number | null,
      quantum: null as number | null, deficit_before: null as number | null, capacity: 386 as number | null,
      cap_reason: null as string | null, waiting_hours: 4.5 as number | null, debt: NO_DEBT,
    },
    counterfactual: {
      booking_id: BOOKING_ID, status: "found", before_place: 387,
      changes: [
        { input: "tier", amount: 1, step: 1, from_value: 2, to_value: 1, after_place: 1 },
        { input: "arrival", amount: 15, step: 15, from_value: "2025-04-29T15:20:13+05:30", to_value: "2025-04-29T15:05:13+05:30", after_place: 384 },
        { input: "group_entitlement", amount: 1.4, step: 0.05, from_value: 22104.37, to_value: 53050.49, after_place: 385 },
        { input: "group_deficit", amount: 0.5, step: 0.5, from_value: 0, to_value: 0.5, after_place: 386 },
      ] as { input: string; amount: number; step: number; from_value: number | string; to_value: number | string; after_place: number }[],
      not_inputs: [["water_debt", "not part of today's ordering"]] as [string, string][],
    },
  };
}

export function contestItem(overrides: Record<string, unknown> = {}) {
  return {
    contest_id: "c-1", created_at: "2026-10-04T15:22:05+00:00", filed_by: "res-1", role: "resident",
    target_type: "ward", target_id: "relation/7848799", reason_code: "need_data_wrong",
    reason_text: "Our lane has no tap; call [number removed]", status: "open",
    ...overrides,
  };
}

export function contestReply() {
  return { reply_id: "r-1", created_at: "2026-10-04T15:22:16+00:00", officer_id: "off-1", outcome_code: "referred", reason_text: "Field check booked for next week." };
}
