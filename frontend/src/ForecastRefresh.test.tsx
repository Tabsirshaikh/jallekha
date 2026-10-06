import { fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { setToken } from "./api";
import { AuthProvider } from "./auth";
import ForecastExperience from "./ForecastExperience";
import { LocaleProvider } from "./i18n";
import { cityRow, sectionRow, jsonResponse } from "./test/apiFixtures";

describe("Refreshed forecast", () => {
  afterEach(() => { setToken(null); vi.unstubAllGlobals(); });
  it("shows current calibrated city ranges, then honest past-month sentences", async () => {
    setToken("officer");
    const fetchMock = vi.fn((input: string) => {
      const url = new URL(input, "http://localhost");
      if (Number(url.searchParams.get("limit")) > 200) return Promise.resolve(jsonResponse({}, 422));
      if (url.pathname === "/auth/me") return Promise.resolve(jsonResponse({role: "officer", user_id: "off-1"}));
      let items: unknown[] = [];
      if (url.pathname === "/forecast") items = url.searchParams.get("level") === "section" ? [sectionRow("ADARSHNAGAR", "2026-09", 36)] : [{...cityRow("2026-09", 200000), lower_80: 160000, upper_80: 240000, lower_90: 140000, upper_90: 260000, lower_80_basis: "DERIVED", capacity_trips: 190000, updated_through: "2026-08"}];
      if (url.pathname === "/forecast/history") items = [{month: "2026-08", level: "city", section: null, actual: 164367, actual_basis: "REAL"}];
      if (url.pathname === "/forecast/accuracy") items = [{month: "2026-05", level: "city", section: null, point: 228302, actual: 319106, error_pct: -28.46}];
      return Promise.resolve(jsonResponse({items, total: items.length}));
    });
    vi.stubGlobal("fetch", fetchMock);
    const {container} = render(<LocaleProvider><AuthProvider><ForecastExperience /></AuthProvider></LocaleProvider>);
    await screen.findByText("Live data");
    expect(screen.getByText("Booking data through Aug 2026")).toBeInTheDocument();
    expect(screen.getByRole("tab", {name: "Next 12 months"})).toBeInTheDocument();
    const detail = screen.getByRole("region", {name: "Selected forecast month"});
    expect(within(detail).getByText("160,000–240,000")).toBeInTheDocument();
    expect(within(detail).getByText("Short by 10,000")).toBeInTheDocument();
    expect(container.querySelector(".range-90")).not.toBeNull();
    expect(container.textContent).not.toMatch(/MAPE|WAPE|DERIVED|SIMULATION|seasonal.naive/);
    fireEvent.click(screen.getByRole("tab", {name: "How good was our forecast?"}));
    expect(screen.getByText(/May 2026: we expected 228,302, actual 319,106 — 28% too low/)).toBeInTheDocument();
    expect(screen.getByText(/On average, forecasts were 28% away/)).toBeInTheDocument();
  });
});
