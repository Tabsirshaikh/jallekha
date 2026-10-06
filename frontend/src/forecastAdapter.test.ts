import { describe, expect, it } from "vitest";
import {
  basisTag,
  outlookFromApi,
  outlookFromFixture,
  sectionsFromForecast,
  shortageFromApi,
  sortByRisk,
  summarizeBacktest,
  type ApiBacktestRow,
  type ApiForecastRow,
  type ApiShortageRow,
} from "./forecastAdapter";
import { backtestRows, cityRow, sectionRow, shortageRow } from "./test/apiFixtures";

describe("basisTag", () => {
  it("reads the leading basis word and treats missing or unknown text as UNAVAILABLE", () => {
    expect(basisTag("DERIVED: sum of section points")).toBe("DERIVED");
    expect(basisTag("ASSUMED: A8 fleet")).toBe("ASSUMED");
    expect(basisTag("REAL HMWSSB section")).toBe("REAL");
    expect(basisTag("SIMULATION")).toBe("SIMULATION");
    expect(basisTag("UNAVAILABLE")).toBe("UNAVAILABLE");
    expect(basisTag(null)).toBe("UNAVAILABLE");
    expect(basisTag("flag off")).toBe("UNAVAILABLE");
  });
});

describe("outlookFromApi", () => {
  it("uses calibrated city ranges and the forecast's capacity for all twelve months", () => {
    const rows = [{ ...cityRow("2026-09", 200000), lower_80: 160000, upper_80: 240000,
      lower_90: 140000, upper_90: 260000, lower_80_basis: "DERIVED: city calibration",
      capacity_trips: 303210, capacity_trips_basis: "DERIVED: fleet trips" }] as ApiForecastRow[];
    expect(outlookFromApi(rows, [])[0]).toMatchObject({low80: 160000, high90: 260000, capacity: 303210, capacityBasis: "DERIVED"});
  });
  it("keeps city intervals null (not zero), carries bases and sorts by month", () => {
    const rows = [cityRow("2026-03", 203085), cityRow("2026-02", 127725)] as ApiForecastRow[];
    const outlook = outlookFromApi(rows, []);
    expect(outlook.map((m) => m.month)).toEqual(["2026-02", "2026-03"]);
    expect(outlook[0]).toMatchObject({ median: 127725, low80: null, high80: null, low90: null, high90: null, capacity: null, basis: "DERIVED", rangeBasis: "UNAVAILABLE", capacityBasis: "UNAVAILABLE" });
    expect(outlook[0].rangeNote).toMatch(/section intervals do not add up/);
  });

  it("takes section capacity from the shortage rows of that section, marked ASSUMED", () => {
    const rows = [sectionRow("ADARSHNAGAR", "2026-02", 36), sectionRow("ADARSHNAGAR", "2026-05", 40)] as ApiForecastRow[];
    const shortage = shortageFromApi([shortageRow("ADARSHNAGAR", "high"), shortageRow("OTHER", "low", { capacity_trips: 99 })] as ApiShortageRow[]);
    const outlook = outlookFromApi(rows, shortage);
    expect(outlook[0]).toMatchObject({ median: 36, low80: 18, high80: 54, low90: 0, high90: 72, basis: "DERIVED", rangeBasis: "DERIVED", capacity: 24.3, capacityBasis: "ASSUMED" });
    expect(outlook[1]).toMatchObject({ capacity: null, capacityBasis: "UNAVAILABLE" });
  });
});

describe("outlookFromFixture", () => {
  it("keeps the demo fixture labelled SIMULATION", () => {
    const outlook = outlookFromFixture([{ month: "2026-10", low80: 1, high80: 3, low90: 0, high90: 4, median: 2, capacity: 2, basis: "SIMULATION" }]);
    expect(outlook[0]).toMatchObject({ median: 2, capacity: 2, basis: "SIMULATION", rangeBasis: "SIMULATION", capacityBasis: "SIMULATION", rangeNote: null });
  });
});

describe("shortageFromApi", () => {
  it("keeps unavailable capacity and ratio null and carries each basis", () => {
    const [row] = shortageFromApi([shortageRow("40 MLD STP ATTAPUR", "unknown")] as ApiShortageRow[]);
    expect(row).toMatchObject({
      section: "40 MLD STP ATTAPUR", month: "2026-02", monthsAhead: 1, forecast: 30, forecastBasis: "DERIVED",
      upper80: 55.4, upper80Basis: "DERIVED", capacity: null, capacityBasis: "UNAVAILABLE", ratio: null, ratioBasis: "UNAVAILABLE",
      risk: "unknown", groundwaterUnavailable: true,
    });
    expect(row.reason).toMatch(/groundwater data unavailable/);
  });

  it("maps an unexpected risk word to unknown", () => {
    const [row] = shortageFromApi([shortageRow("X", "severe")] as ApiShortageRow[]);
    expect(row.risk).toBe("unknown");
  });
});

describe("sortByRisk", () => {
  it("puts high first, then medium, unknown and low; higher capacity ratio first within a level", () => {
    const rows = shortageFromApi([
      shortageRow("LOW A", "low", { capacity_ratio: 0.2 }),
      shortageRow("UNKNOWN A", "unknown"),
      shortageRow("HIGH SMALL", "high", { capacity_ratio: 1.1 }),
      shortageRow("MEDIUM A", "medium", { capacity_ratio: 0.9 }),
      shortageRow("HIGH BIG", "high", { capacity_ratio: 2.4 }),
    ] as ApiShortageRow[]);
    expect(sortByRisk(rows).map((r) => r.section)).toEqual(["HIGH BIG", "HIGH SMALL", "MEDIUM A", "UNKNOWN A", "LOW A"]);
    expect(rows[0].section).toBe("LOW A");
  });
});

describe("summarizeBacktest", () => {
  it("compares models on shared origins, keeps the selection note and the models not run", () => {
    const summary = summarizeBacktest(backtestRows() as ApiBacktestRow[]);
    expect(summary.comparisons).toHaveLength(2);
    expect(summary.comparisons[0]).toMatchObject({ run: "s2_2022-01_2024-02", model: "seasonal_naive", cityMape: 15.0943, sectionWape: 31.3821, basis: "DERIVED", months: 10 });
    expect(summary.selected).toEqual({ model: "seasonal_naive", note: "no model beats seasonal naive on both metrics in both runs; baseline used" });
    expect(summary.notRun).toEqual([{ model: "global_gbm", note: "not run: needs scikit-learn or lightgbm" }]);
  });
});

describe("sectionsFromForecast", () => {
  it("lists distinct section names in order", () => {
    const rows = [sectionRow("B", "2026-02", 1), sectionRow("A", "2026-02", 1), sectionRow("B", "2026-03", 1)] as ApiForecastRow[];
    expect(sectionsFromForecast(rows)).toEqual(["A", "B"]);
  });
});
