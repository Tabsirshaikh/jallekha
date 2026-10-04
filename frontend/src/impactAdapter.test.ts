import { describe, expect, it } from "vitest";
import { impactFromApi, policyDifference, type ApiImpact } from "./impactAdapter";
import { impactResponse } from "./test/apiFixtures";

describe("impactFromApi", () => {
  it("maps each policy into a row with the response's basis on every measure", () => {
    const view = impactFromApi(impactResponse() as ApiImpact);
    expect(view.rows.map((r) => r.policy)).toEqual(["B1", "JL"]);
    expect(view.rows[1]).toMatchObject({ replay: "main_2025", scenario: "tight", seed_count: 30, label: "SIMULATION" });
    expect(view.rows[1].metrics.served_share).toEqual({ mean: 0.625, min: 0.615, max: 0.635, basis: "SIMULATION" });
    expect(view.policies.JL).toMatch(/fair queue/);
    expect(view.baselines.delivered_share.main_2025).toBe(0.99878);
    expect(view.unavailableReason).toBe("The booking replay has no complaints (live reason).");
  });

  it("keeps a measure the API did not send as null, never zero", () => {
    const response = impactResponse() as ApiImpact;
    delete (response.results.B1 as Record<string, unknown>).km_per_kl;
    const view = impactFromApi(response);
    expect(view.rows[0].metrics.km_per_kl).toEqual({ mean: null, min: null, max: null, basis: "SIMULATION" });
  });
});

describe("policyDifference", () => {
  it("is null when either side is missing", () => {
    expect(policyDifference(0.6, 0.5)).toBeCloseTo(0.1);
    expect(policyDifference(null, 0.5)).toBeNull();
    expect(policyDifference(0.6, null)).toBeNull();
  });
});
