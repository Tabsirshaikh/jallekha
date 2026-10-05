import { describe, expect, it } from "vitest";
import { ApiError } from "./api";
import { adaptLiveEvidence, reasonForError } from "./evidenceAdapter";
import { atlasPage, liveInput } from "./test/evidenceFixtures";

describe("adaptLiveEvidence", () => {
  it("maps API rows into the screen's ward view", () => {
    const live = adaptLiveEvidence(liveInput);
    expect(live).not.toBeNull();
    const testpur = live!.dataset.wards.find((ward) => ward.id === "relation/901");
    expect(testpur).toEqual({
      id: "relation/901", name: "Ward 901 Testpur", censusYear: 2011, reviewRequired: false,
      population2011: 50000, households2011: 12000, waterAccessDeficitShare: 0.21, criticalFacilities: 12,
      growthRatio: 1.25, growthQuality: "STABLE_TREND", bookings: 120, bookingsPer1000: 10.5,
      bookingStatus: "APPROXIMATE_SECTION_POINT_IN_WARD", fieldStatus: "AGREED_FIELD_CHECK_CANDIDATE", fieldCandidate: true,
      fieldReasons: [
        { code: "LOW_OBSERVED_REFERENCE_RATIO", model: "PEER_MEDIAN", value: 0.05, threshold: 0.11, basis: "DERIVED" },
        { code: "LOW_OBSERVED_REFERENCE_RATIO", model: "NB", value: 0.01, threshold: 0.03, basis: "DERIVED" },
        { code: "WAD_ABOVE_COHORT_QUANTILE", value: 0.21, threshold: 0.1, basis: "REAL" },
      ],
    });
  });

  it("keeps unavailable values as null, never zero", () => {
    const ward = adaptLiveEvidence(liveInput)!.dataset.wards.find((row) => row.id === "relation/902")!;
    expect(ward).toMatchObject({
      censusYear: null, reviewRequired: true, population2011: null, households2011: null, waterAccessDeficitShare: null,
      growthRatio: null, growthQuality: null, bookings: null, bookingsPer1000: null, fieldCandidate: null,
    });
    expect(ward.fieldReasons).toEqual([{ code: "WARD_BOOKINGS_UNAVAILABLE", value: null, threshold: null, basis: "UNAVAILABLE" }]);
  });

  it("keeps the OSM facility count apart from Census gaps, and null when it is missing", () => {
    const wards = adaptLiveEvidence(liveInput)!.dataset.wards;
    expect(wards.find((row) => row.id === "relation/902")!.criticalFacilities).toBe(4);
    expect(wards.find((row) => row.id === "relation/903")!.criticalFacilities).toBeNull();
  });

  it("builds the summary, equity totals and ward polygons", () => {
    const live = adaptLiveEvidence(liveInput)!;
    expect(live.dataset.snapshotDate).toBeNull();
    expect(live.dataset.geographyVersion).toBe("GHMC_2016_150");
    expect(live.dataset.summary).toMatchObject({
      wardCount: 3, censusMappedCount: 2, censusReviewCount: 1, fieldCheckCount: 1, eligibleCount: 2, dataReviewCount: 1,
    });
    expect(live.dataset.summary.equity).toMatchObject({ bookings: 1020, gini: 0.61, section_count: 12, missing_source_months: ["2022-12"] });
    expect(live.features.map((feature) => feature.properties.ward_id)).toEqual(["relation/901", "relation/902", "relation/903"]);
  });

  it("refuses incomplete or malformed answers instead of showing a partial screen", () => {
    expect(adaptLiveEvidence({ ...liveInput, atlas: { ...atlasPage, total: 400 } })).toBeNull();
    expect(adaptLiveEvidence({ ...liveInput, atlas: { role: "officer" } })).toBeNull();
    expect(adaptLiveEvidence({ ...liveInput, equitySummary: { bookings: 1 } })).toBeNull();
    expect(adaptLiveEvidence({ ...liveInput, layer: { features: "none" } })).toBeNull();
  });
});

describe("reasonForError", () => {
  it("tells sign-in problems apart from an unreachable or failing server", () => {
    expect(reasonForError(new ApiError(401, "unauthorized", "x"))).toBe("signIn");
    expect(reasonForError(new ApiError(403, "forbidden", "x"))).toBe("forbidden");
    expect(reasonForError(new ApiError(0, "network_error", "x"))).toBe("unreachable");
    expect(reasonForError(new ApiError(500, "internal", "x"))).toBe("serverError");
  });
});
