import { describe, expect, it } from "vitest";
import {
  bookingFromApi,
  contestDetailFromApi,
  contestsFromApi,
  counterfactualFromApi,
  errorKind,
  wardFromApi,
} from "./explainAdapter";
import { ApiError } from "./api";
import { bookingResponse, contestItem, contestReply, noCensusWard, wardResponse } from "./test/explainFixtures";

describe("wardFromApi", () => {
  it("keeps every value with its basis", () => {
    const ward = wardFromApi(wardResponse());
    expect(ward.id).toBe("relation/7848799");
    expect(ward.name).toBe("Ward 91 Khairatabad");
    expect(ward.hasCensus).toBe(true);
    expect(ward.needWeight).toEqual({ value: 1.354999, basis: "DERIVED" });
    expect(ward.households).toEqual({ value: 12959, basis: "DERIVED" });
    expect(ward.entitlement).toEqual({ value: 17559.432041, basis: "DERIVED" });
    expect(ward.criticalFacilities).toEqual({ value: null, basis: "UNAVAILABLE" });
    expect(ward.qualityFlags).toContain("HISTORICAL");
    expect(ward.checkReasons).toEqual(["E2_REVIEW_REQUIRED"]);
    expect(ward.reviewRequired).toBe(true);
    expect(ward.debtAvailable).toBe(false);
  });

  it("shows no number for a ward without Census data", () => {
    const ward = wardFromApi(noCensusWard());
    expect(ward.hasCensus).toBe(false);
    expect(ward.needWeight.value).toBeNull();
    expect(ward.wad.value).toBeNull();
    expect(ward.households.value).toBeNull();
    expect(ward.entitlement.value).toBeNull();
  });

  it("keeps numbers null even if a no-Census ward carries one", () => {
    const response = noCensusWard();
    response.explanation.need_weight = 2;
    expect(wardFromApi(response).needWeight.value).toBeNull();
  });
});

describe("bookingFromApi", () => {
  it("maps a waiting booking and keeps its missing values null", () => {
    const { booking } = bookingFromApi(bookingResponse());
    expect(booking.id).toBe("2025-04-29:MANIKONDA (DIV 18):00387");
    expect(booking.status).toBe("waiting");
    expect(booking.place).toBe(387);
    expect(booking.capacity).toBe(386);
    expect(booking.tier).toBe(2);
    expect(booking.position).toBeNull();
    expect(booking.reason).toBeNull();
    expect(booking.entitlement).toBeNull();
    expect(booking.quantum).toBeNull();
    expect(booking.deficitBefore).toBeNull();
    expect(booking.capReason).toBeNull();
  });

  it("maps the counterfactual changes into plain steps", () => {
    const { counterfactual } = bookingFromApi(bookingResponse());
    expect(counterfactual).not.toBeNull();
    expect(counterfactual?.status).toBe("found");
    expect(counterfactual?.before).toBe(387);
    expect(counterfactual?.steps).toEqual([
      { kind: "tier", from: 2, to: 1, after: 1 },
      { kind: "arrival", minutes: 15, after: 384 },
      { kind: "entitlement", percent: 140, after: 385 },
      { kind: "deficit", amount: 0.5, after: 386 },
    ]);
    expect(counterfactual?.notInputs).toEqual(["water_debt"]);
  });

  it("gives a null counterfactual when the API sends none", () => {
    const response = bookingResponse() as Record<string, unknown>;
    delete response.counterfactual;
    expect(bookingFromApi(response as ReturnType<typeof bookingResponse>).counterfactual).toBeNull();
    expect(counterfactualFromApi(null)).toBeNull();
  });

  it("reads already-first and no-change counterfactuals", () => {
    const first = counterfactualFromApi({ booking_id: "b", status: "already_first", before_place: 1, changes: [], not_inputs: [["water_debt", "not part of today's ordering"]] });
    expect(first).toEqual({ status: "already_first", before: 1, steps: [], notInputs: ["water_debt"] });
    const none = counterfactualFromApi({ booking_id: "b", status: "no_change_within_limits", before_place: 9, changes: [], not_inputs: [] });
    expect(none?.status).toBe("none");
  });
});

describe("contests", () => {
  it("maps a contest page; the reply is not loaded yet", () => {
    const page = contestsFromApi({ total: 3, offset: 0, limit: 50, items: [contestItem({ status: "open" })] });
    expect(page.total).toBe(3);
    expect(page.items[0]).toMatchObject({ id: "c-1", targetType: "ward", targetId: "relation/7848799", reasonCode: "need_data_wrong", status: "open" });
    expect(page.items[0].reply).toBeUndefined();
    expect(page.items[0].text).toContain("[number removed]");
  });

  it("maps a contest detail with and without a reply", () => {
    expect(contestDetailFromApi({ ...contestItem({ status: "open" }), reply: null }).reply).toBeNull();
    const replied = contestDetailFromApi({ ...contestItem({ status: "replied" }), reply: contestReply() });
    expect(replied.status).toBe("replied");
    expect(replied.reply).toEqual({ id: "r-1", createdAt: "2026-10-04T15:22:16+00:00", officerId: "off-1", outcome: "referred", text: "Field check booked for next week." });
  });
});

describe("errorKind", () => {
  it("names each server answer in plain terms", () => {
    expect(errorKind(new ApiError(0, "network_error", "x"))).toBe("unreachable");
    expect(errorKind(new ApiError(401, "unauthorized", "x"))).toBe("rejected");
    expect(errorKind(new ApiError(403, "forbidden", "x"))).toBe("forbidden");
    expect(errorKind(new ApiError(404, "not_found", "x"))).toBe("notFound");
    expect(errorKind(new ApiError(409, "conflict", "x"))).toBe("conflict");
    expect(errorKind(new ApiError(422, "validation_error", "x"))).toBe("invalid");
    expect(errorKind(new ApiError(500, "internal_error", "x"))).toBe("error");
  });
});
