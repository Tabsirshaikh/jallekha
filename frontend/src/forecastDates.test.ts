import { describe, expect, it } from "vitest";
import { warningWindow, currentWarnings } from "./forecastDates";
import { shortageFromApi } from "./forecastAdapter";
import { shortageRow } from "./test/apiFixtures";

describe("current shortage window", () => {
  it("uses the next three calendar months in Hyderabad, including across a year boundary", () => {
    expect(warningWindow(new Date("2026-10-07T00:00:00Z"))).toEqual({origin: "2026-10", from: "2026-11", through: "2027-01"});
    expect(warningWindow(new Date("2026-12-31T20:00:00Z"))).toEqual({origin: "2027-01", from: "2027-02", through: "2027-04"});
  });
  it("omits past warnings and recalculates lead times without changing their risk", () => {
    const rows = shortageFromApi(["2026-09", "2026-11", "2027-01", "2027-02"].map(month => shortageRow("GOLCONDA", "high", {month, months_ahead: 3})));
    const shown = currentWarnings(rows, warningWindow(new Date("2026-10-07T00:00:00Z")));
    expect(shown.map(row => [row.month, row.monthsAhead, row.risk])).toEqual([["2026-11", 1, "high"], ["2027-01", 3, "high"]]);
  });
});
