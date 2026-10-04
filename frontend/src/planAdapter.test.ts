import { describe, expect, it } from "vitest";
import { ApiError } from "./api";
import { adaptCompare, adaptLivePlan, adaptPlanList, planReason } from "./planAdapter";
import { compareBody, confidenceBody, listBody, planBody } from "./test/planFixtures";

describe("adaptPlanList", () => {
  it("maps the stored plans and keeps the total", () => {
    const list = adaptPlanList(listBody(1));
    expect(list).toEqual({
      total: 1,
      defaultWeights: { wad: 2, cad: 1, hardship: 1 },
      maxWeight: 5,
      items: [{ id: "replay-2025-05-01", day: "2025-05-01", status: "DRAFT", flagsTotal: 2, checkedTotal: 1, simulation: true, weights: null, source: "planner_replay" }],
    });
  });

  it("keeps unknown counts null rather than zero", () => {
    const raw = listBody();
    const item = { ...raw.items[0], flags_total: null, checked_total: undefined };
    expect(adaptPlanList({ ...raw, items: [item] })?.items[0]).toMatchObject({ flagsTotal: null, checkedTotal: null });
  });

  it("rejects an answer that is not a plan list", () => {
    expect(adaptPlanList(null)).toBeNull();
    expect(adaptPlanList({ items: "nope" })).toBeNull();
    expect(adaptPlanList({ total: 1, items: [{ day: "2025-05-01" }] })).toBeNull();
  });
});

describe("adaptLivePlan", () => {
  it("maps totals, schedule, outage and basis", () => {
    const plan = adaptLivePlan(planBody(), confidenceBody);
    expect(plan).not.toBeNull();
    expect(plan).toMatchObject({
      id: "replay-2025-05-01", day: "2025-05-01", status: "DRAFT", approved: false, approvedBy: null,
      trips: 418, reserveTrips: 325, outageTrips: 0, served: 6, waiting: 1, stationsTotal: 2,
      basis: { plan: expect.stringContaining("SIMULATION"), flags: expect.stringContaining("PROVISIONAL") },
      outage: { critical: 0, allocations: 0, unusedLitres: 9735000, countsTowardDebt: false },
      scheduledTotal: 2, unroutedTotal: 1,
    });
    expect(plan?.outage.basis.lpcd).toContain("ASSUMED");
    expect(plan?.schedule).toEqual([
      { wardId: "relation/7848824", litres: 127542.41237198106, floor: 214399.92285, status: "FLOOR_NOT_MET", unrouted: "NEEDS_SERVICE_POINT" },
      { wardId: "relation/7848859", litres: null, floor: 130536.65898000001, status: "FLOOR_NOT_MET", unrouted: null },
    ]);
  });

  it("keeps unavailable numbers null, never zero", () => {
    const raw = planBody();
    const broken = { ...raw, reserve_trips: null, stations: { ...raw.stations, ST02: { ...raw.stations.ST02, trips: null } }, outage: { ...raw.outage, unused_litres: null, counts_toward_water_debt: null } };
    const plan = adaptLivePlan(broken, confidenceBody);
    expect(plan?.reserveTrips).toBeNull();
    expect(plan?.trips).toBeNull();
    expect(plan?.outage.unusedLitres).toBeNull();
    expect(plan?.outage.countsTowardDebt).toBeNull();
  });

  it("lists every flag with its check state and the groups still unchecked", () => {
    const plan = adaptLivePlan(planBody({ "section:ADARSHNAGAR": "map checked" }), confidenceBody);
    expect(plan?.flags).toEqual([
      { group: "section:ADARSHNAGAR", confidence: 0, reason: expect.stringContaining("census_join_quality"), checked: true, checkReason: "map checked" },
      { group: "ward:relation/7852805", confidence: 0.25, reason: expect.stringContaining("section_location"), checked: false, checkReason: null },
    ]);
    expect(plan?.flagsTotal).toBe(2);
    expect(plan?.checkedTotal).toBe(1);
    expect(plan?.unchecked).toEqual(["ward:relation/7852805"]);
  });

  it("marks each queue group with its own needs_check and served count", () => {
    const plan = adaptLivePlan(planBody(), confidenceBody);
    expect(plan?.queue).toEqual([
      { group: "ward:relation/7848824", served: 3, confidence: 0.5, needsCheck: false, checked: false },
      { group: "ward:relation/7852805", served: 2, confidence: 0.25, needsCheck: true, checked: false },
      { group: "section:ADARSHNAGAR", served: 1, confidence: 0, needsCheck: true, checked: false },
    ]);
  });

  it("keeps a group's confidence null when the gate gave none", () => {
    const groups = confidenceBody.groups.map((g) => (g.group === "ward:relation/7848824" ? { ...g, confidence: null } : g));
    const plan = adaptLivePlan(planBody(), { ...confidenceBody, groups });
    expect(plan?.queue[0]).toMatchObject({ group: "ward:relation/7848824", confidence: null, needsCheck: false });
  });

  it("does not count served bookings per group when a station's list is cut short", () => {
    const raw = planBody();
    const cut = { ...raw, stations: { ...raw.stations, ST01: { ...raw.stations.ST01, served_total: 40 } } };
    const plan = adaptLivePlan(cut, confidenceBody);
    expect(plan?.served).toBe(42);
    expect(plan?.queue.every((row) => row.served === null)).toBe(true);
  });

  it("maps the provisional threshold and calibration", () => {
    expect(adaptLivePlan(planBody(), confidenceBody)?.confidence).toEqual({ threshold: 0.5, thresholdBasis: "PROVISIONAL", calibrationStatus: "not_separable", groups: 3, belowThreshold: 2 });
  });

  it("shows the approval the server recorded", () => {
    const plan = adaptLivePlan(planBody({}, "APPROVED", { by: "off-1", reason: "ok" }), confidenceBody);
    expect(plan).toMatchObject({ status: "APPROVED", approved: true, approvedBy: "off-1", approvalReason: "ok" });
  });

  it("rejects a plan or confidence answer of the wrong shape", () => {
    expect(adaptLivePlan(null, confidenceBody)).toBeNull();
    expect(adaptLivePlan({ ...planBody(), flags: [] }, confidenceBody)).toBeNull();
    expect(adaptLivePlan(planBody(), { threshold: 0.5 })).toBeNull();
  });
});

describe("planReason", () => {
  it("says why the sample plan is shown", () => {
    expect(planReason(new ApiError(401, "unauthorized", "x"))).toBe("signIn");
    expect(planReason(new ApiError(403, "forbidden", "x"))).toBe("forbidden");
    expect(planReason(new ApiError(0, "network_error", "x"))).toBe("unreachable");
    expect(planReason(new ApiError(500, "internal", "x"))).toBe("serverError");
  });
});


describe("weights and names", () => {
  it("reads the weights a plan was built with, and the names of its groups", () => {
    const plan = adaptLivePlan(planBody(), confidenceBody);
    expect(plan?.weights).toEqual({ wad: 2, cad: 1, hardship: 1, isDefault: true });
    expect(plan?.names).toMatchObject({ "ward:relation/7848824": "Ward 105 Gachibowli", "section:ADARSHNAGAR": "ADARSHNAGAR", "ward:relation/9999999": null });
    expect(plan?.basis.weights).toContain("ASSUMED");
    const weighted = adaptLivePlan(planBody({}, "DRAFT", null, true), confidenceBody);
    expect(weighted?.weights).toEqual({ wad: 5, cad: 0, hardship: 0, isDefault: false });
    expect(weighted?.id).toBe("replay-2025-05-01-w5-0-0");
  });

  it("keeps weights null when the answer has none, instead of inventing the defaults", () => {
    const old = Object.fromEntries(Object.entries(planBody()).filter(([key]) => key !== "weights" && key !== "group_names"));
    const plan = adaptLivePlan(old, confidenceBody);
    expect(plan?.weights).toBeNull();
    expect(plan?.names).toEqual({});
  });

  it("marks list rows that are weighted", () => {
    const list = adaptPlanList(listBody(0, "DRAFT", true));
    expect(list?.items.map((item) => item.weights)).toEqual([null, { wad: 5, cad: 0, hardship: 0 }]);
  });

  it("maps who gains and who loses, keeping an unknown name null", () => {
    const view = adaptCompare(compareBody);
    expect(view).toMatchObject({ against: "replay-2025-05-01", weights: { wad: 5, cad: 0, hardship: 0 }, defaultWeights: { wad: 2, cad: 1, hardship: 1 } });
    expect(view?.gainers[0]).toEqual({ group: "ward:relation/7848824", name: "Ward 105 Gachibowli", servedDefault: 192, servedWeighted: 200, change: 8 });
    expect(view?.losers[0]).toMatchObject({ group: "ward:relation/7852805", name: null, change: -8 });
  });

  it("rejects a comparison that is not one", () => {
    expect(adaptCompare(null)).toBeNull();
    expect(adaptCompare({ ...compareBody, gainers: "no" })).toBeNull();
    expect(adaptCompare({ ...compareBody, losers: [{ group: "x" }] })).toBeNull();
  });
});

describe("where a plan came from", () => {
  it("reads the source and the number of supplied bookings", () => {
    const replay = adaptLivePlan(planBody(), confidenceBody);
    expect(replay).toMatchObject({ source: "planner_replay", bookingsSupplied: null });
    const supplied = adaptLivePlan(planBody({}, "DRAFT", null, false, 40), confidenceBody);
    expect(supplied).toMatchObject({ id: "plan-2026-10-03-ab12cd34", day: "2026-10-03", source: "supplied_bookings", bookingsSupplied: 40 });
  });

  it("marks supplied plans in the list", () => {
    const list = adaptPlanList(listBody(0, "DRAFT", false, true));
    expect(list?.items.map((item) => item.source)).toEqual(["supplied_bookings", "planner_replay"]); // newest day first
  });

  it("keeps the source null when the answer does not say", () => {
    const old = Object.fromEntries(Object.entries(planBody()).filter(([key]) => key !== "source" && key !== "bookings_supplied"));
    expect(adaptLivePlan(old, confidenceBody)).toMatchObject({ source: null, bookingsSupplied: null });
  });
});

