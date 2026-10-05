import { describe, expect, it } from "vitest";
import { badgeKind, badgeLabel, liveWards, wardCardFromApi } from "./wardCardAdapter";
import { noValue, wardCard } from "./test/wardCardFixtures";

const card = wardCard;

describe("wardCardFromApi", () => {
  it("maps the live blocks into plain view values with their badges", () => {
    const view = wardCardFromApi(card());
    expect(view.wardName).toBe("Ward 105 Gachibowli");
    expect(view.need).toEqual({ serviceClass: "piped_regularity_unknown", needWeight: 1.716028, basis: "DERIVED" });
    expect(view.bookings).toEqual({ count: 66431, from: "2022-01", to: "2024-02", basis: "DERIVED_APPROXIMATE" });
    expect(view.deliveries).toEqual({
      badge: "SYNTHETIC",
      reason: null,
      data: { windowDays: 30, started: 3, stops: 1, outcomes: { Confirmed: 2, Disputed: 1, Unconfirmed: 0, Failed: 0, open: 0 } },
    });
    expect(view.debt.badge).toBe("DERIVED");
    expect(view.debt.data).toEqual({ loads: 24, litres: 120000, daysInDebt: 1, alertRaised: false, lastClosedDay: "2026-10-03" });
    expect(view.schedule.data).toEqual({ day: "2026-10-03", status: "APPROVED", source: "supplied_bookings", served: 4, waiting: 0, stopLoads: [{ stopId: "stop-g1", loads: 26 }] });
    expect(view.schedule.basis).toContain("12 bookings supplied");
  });

  it("keeps the reason and no numbers when a block has no value", () => {
    const none = noValue("no delivery stop is registered in this ward yet");
    const view = wardCardFromApi(card({ deliveries: none, debt: { ...none, reason: "no day has been closed" }, schedule: { ...none, reason: "no plan stored" } }));
    expect(view.deliveries).toEqual({ badge: "UNAVAILABLE", reason: "no delivery stop is registered in this ward yet", data: null });
    expect(view.debt.data).toBeNull();
    expect(view.debt.reason).toBe("no day has been closed");
    expect(view.schedule.data).toBeNull();
  });

  it("leaves booked counts and the closed day empty when the API does not give them", () => {
    const base = card();
    const view = wardCardFromApi({
      ...base,
      debt: { ...base.debt, value: { debt_litres: 0, debt_loads: 0, days_in_debt: 0, alert_raised: false, settled_through: null } },
      schedule: { ...base.schedule, value: { plan_id: "p", day: "2026-10-04", status: "DRAFT", source: "replay", stops: [] } },
    });
    expect(view.debt.data?.lastClosedDay).toBeNull();
    expect(view.schedule.data).toMatchObject({ status: "DRAFT", source: "replay", served: null, waiting: null, stopLoads: [] });
    expect(view.schedule.badge).toBe("SIMULATION");
  });

  it("reads the badge from the start of a basis sentence", () => {
    expect(badgeLabel("MIXED (REAL and SYNTHETIC stops)")).toBe("MIXED");
    expect(badgeLabel("DERIVED (A6: litres ...)")).toBe("DERIVED");
    expect(badgeLabel("Plan from 12 bookings supplied")).toBeNull();
    expect(badgeKind("REAL")).toBe("real");
    expect(badgeKind("DERIVED_APPROXIMATE")).toBe("derived");
    expect(badgeKind("MIXED")).toBe("derived");
    expect(badgeKind("SYNTHETIC")).toBe("simulation");
  });
});

describe("wardCardFromApi, missing figures", () => {
  it("keeps null bookings and a null need weight as null, never 0", () => {
    const base = card();
    const view = wardCardFromApi({
      ...base,
      need: { ...base.need, need_weight: null },
      bookings: { ...base.bookings, bookings: null, bookings_per_1000: null },
    });
    expect(view.bookings.count).toBeNull();
    expect(view.need.needWeight).toBeNull();
  });
});

describe("liveWards", () => {
  it("lists every ward of the evidence snapshot in ward-number order, with Gachibowli among them", () => {
    expect(liveWards).toHaveLength(145);
    expect(new Set(liveWards.map((ward) => ward.id)).size).toBe(145);
    expect(liveWards).toContainEqual({ id: "relation/7848824", name: "Ward 105 Gachibowli" });
    expect(liveWards).toContainEqual({ id: "relation/7848799", name: "Ward 91 Khairatabad" });
    const numbers = liveWards.map((ward) => Number(/^Ward (\d+)/.exec(ward.name)?.[1]));
    expect(numbers).toEqual([...numbers].sort((a, b) => a - b));
  });
});
