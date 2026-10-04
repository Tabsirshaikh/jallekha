/** Small API responses in the real T10 shapes (checked against a running API), for U5 tests. */

const square = (x: number, y: number) => ({
  type: "Polygon",
  coordinates: [[[x, y], [x + 0.01, y], [x + 0.01, y + 0.01], [x, y + 0.01], [x, y]]],
});

export const atlasPage = {
  total: 3,
  offset: 0,
  limit: 200,
  items: [
    {
      ward_id: "relation/901", ward_name: "Ward 901 Testpur", geo_version: "GHMC_2016_150", census_year: 2011,
      review_required: false, allocation_eligible: true, population: 50000, population_basis: "DERIVED",
      households: 12000, households_basis: "DERIVED", wad: 0.21, wad_basis: "DERIVED",
    },
    {
      ward_id: "relation/902", ward_name: "Ward 902 Nullabad", geo_version: "GHMC_2016_150", census_year: null,
      review_required: true, allocation_eligible: false, population: null, population_basis: "UNAVAILABLE",
      households: null, households_basis: "UNAVAILABLE", wad: null, wad_basis: "UNAVAILABLE",
    },
    {
      ward_id: "relation/903", ward_name: "Ward 903 Plainville", geo_version: "GHMC_2016_150", census_year: 2011,
      review_required: false, allocation_eligible: true, population: 40000, population_basis: "DERIVED",
      households: 9000, households_basis: "DERIVED", wad: 0.05, wad_basis: "DERIVED",
    },
  ],
};

export const equityWardsPage = {
  total: 3,
  offset: 0,
  limit: 200,
  items: [
    { ward_id: "relation/901", ward_name: "Ward 901 Testpur", bookings: 120, bookings_per_1000: 10.5, mapping_status: "APPROXIMATE_SECTION_POINT_IN_WARD", basis: "DERIVED_APPROXIMATE" },
    { ward_id: "relation/902", ward_name: "Ward 902 Nullabad", bookings: null, bookings_per_1000: null, mapping_status: "NO_PLACED_SECTION", basis: "UNAVAILABLE" },
    { ward_id: "relation/903", ward_name: "Ward 903 Plainville", bookings: 900, bookings_per_1000: 99.25, mapping_status: "APPROXIMATE_SECTION_POINT_IN_WARD", basis: "DERIVED_APPROXIMATE" },
  ],
};

export const equitySummary = {
  bookings: 1020, bottom_booking_share: 0.02, bottom_section_count: 100, delivered: 1000, gini: 0.61,
  interpretation: "Live: concentration of observed bookings, not unequal need", missing_source_months: ["2022-12"],
  section_count: 12, top_booking_share: 0.5, top_section_count: 2,
};

export const fieldChecks = {
  schema_version: "E5-1",
  summary: { area_count: 3, data_review_count: 1, eligible_count: 2, field_check_count: 1 },
  limitations: ["Low bookings cannot identify unmet need or a reporting probability."],
  field_check_list: [],
  rows: [
    {
      ward_id: "relation/901", ward_name: "Ward 901 Testpur", status: "AGREED_FIELD_CHECK_CANDIDATE", field_check_candidate: true,
      growth_ratio_context_only: 1.25, growth_quality: "STABLE_TREND",
      reasons: [
        { basis: "DERIVED", code: "LOW_OBSERVED_REFERENCE_RATIO", model: "PEER_MEDIAN", threshold: 0.11, value: 0.05 },
        { basis: "DERIVED", code: "LOW_OBSERVED_REFERENCE_RATIO", model: "NB", threshold: 0.03, value: 0.01 },
        { basis: "REAL", code: "WAD_ABOVE_COHORT_QUANTILE", threshold: 0.1, value: 0.21 },
      ],
    },
    {
      ward_id: "relation/902", ward_name: "Ward 902 Nullabad", status: "DATA_REVIEW", field_check_candidate: null,
      growth_ratio_context_only: null, growth_quality: null,
      reasons: [{ basis: "UNAVAILABLE", code: "WARD_BOOKINGS_UNAVAILABLE", value: null }],
    },
    {
      ward_id: "relation/903", ward_name: "Ward 903 Plainville", status: "NOT_FLAGGED", field_check_candidate: false,
      growth_ratio_context_only: 1.5, growth_quality: "STABLE_TREND", reasons: [],
    },
  ],
  rows_total: 3,
};

export const waterAccessLayer = {
  type: "FeatureCollection",
  layer_id: "water_access_evidence",
  geography_version: "GHMC_2016_150",
  features: [
    { type: "Feature", geometry: square(78.4, 17.4), properties: { ward_id: "relation/901", ward_name: "Ward 901 Testpur", water_access_deficit_share: 0.21 } },
    { type: "Feature", geometry: square(78.42, 17.4), properties: { ward_id: "relation/902", ward_name: "Ward 902 Nullabad", water_access_deficit_share: null } },
    { type: "Feature", geometry: square(78.44, 17.4), properties: { ward_id: "relation/903", ward_name: "Ward 903 Plainville", water_access_deficit_share: 0.05 } },
  ],
};

export const liveInput = { atlas: atlasPage, equityWards: equityWardsPage, equitySummary, fieldChecks, layer: waterAccessLayer };

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

/** A fetch stand-in that answers each U5 route (and /auth/me) like the real API. */
export function liveFetch(url: string): Promise<Response> {
  const path = new URL(url, "http://localhost").pathname;
  const routes: Record<string, unknown> = {
    "/auth/me": { role: "officer", user_id: "off-test" },
    "/atlas/wards": atlasPage,
    "/equity/wards": equityWardsPage,
    "/equity/summary": equitySummary,
    "/underserved/field-checks": fieldChecks,
    "/coverage/layers/water_access_evidence": waterAccessLayer,
  };
  return Promise.resolve(path in routes ? json(routes[path]) : json({ error: { code: "not_found", message: "Not found" } }, 404));
}

export function errorFetch(status: number): () => Promise<Response> {
  return () => Promise.resolve(json({ error: { code: status === 401 ? "unauthorized" : "error", message: "No" } }, status));
}
