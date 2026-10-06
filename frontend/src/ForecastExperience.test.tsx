import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { setToken } from "./api";
import { AuthProvider } from "./auth";
import ForecastExperience from "./ForecastExperience";
import { LocaleProvider } from "./i18n";
import { backtestRows, cityRow, jsonResponse, sectionRow, shortageRow } from "./test/apiFixtures";


function renderScreen() {
  return render(
    <LocaleProvider>
      <AuthProvider>
        <ForecastExperience />
      </AuthProvider>
    </LocaleProvider>,
  );
}

type Shortage = ReturnType<typeof shortageRow>;

function officerApi(shortage: Shortage[] = [shortageRow("ALPHA LOW", "low", { capacity_ratio: 0.3 }), shortageRow("AMEENPUR (PD 8)", "high"), shortageRow("40 MLD STP ATTAPUR", "unknown")]) {
  return vi.fn((input: string) => {
    const url = new URL(input, "http://localhost");
    const q = url.searchParams;
    if (url.pathname === "/auth/me") return Promise.resolve(jsonResponse({ role: "officer", user_id: "off-1" }));
    if (url.pathname === "/forecast/backtest") return Promise.resolve(jsonResponse({ items: backtestRows(), total: 5 }));
    if (url.pathname === "/forecast" && q.get("level") === "city") return Promise.resolve(jsonResponse({ items: [cityRow("2026-02", 127725), cityRow("2026-03", 203085)], total: 2 }));
    if (url.pathname === "/forecast" && q.get("section")) return Promise.resolve(jsonResponse({ items: [sectionRow(q.get("section") ?? "", "2026-02", 36)], total: 1 }));
    if (url.pathname === "/forecast" && q.get("level") === "section") return Promise.resolve(jsonResponse({ items: [sectionRow("ADARSHNAGAR", "2026-02", 36), sectionRow("AMEENPUR (PD 8)", "2026-02", 30)], total: 2 }));
    if (url.pathname === "/shortage") {
      const offset = Number(q.get("offset") ?? 0);
      const limit = Number(q.get("limit") ?? 50);
      return Promise.resolve(jsonResponse({ items: shortage.slice(offset, offset + limit), total: shortage.length, basis: "DERIVED" }));
    }
    return Promise.resolve(jsonResponse({ error: { code: "not_found", message: "no route" } }, 404));
  });
}

describe("ForecastExperience", () => {
  beforeEach(() => setToken(null));
  afterEach(() => vi.unstubAllGlobals());

  it("shows the live T2 city forecast as DERIVED with blank city intervals", async () => {
    setToken("t-officer");
    vi.stubGlobal("fetch", officerApi());
    renderScreen();
    expect(await screen.findByText("Live data")).toBeInTheDocument();
    const detail = screen.getByRole("region", { name: "Selected forecast month" });
    expect(within(detail).getByText("127,725")).toBeInTheDocument();
    expect(within(detail).queryByText(/DERIVED/)).toBeNull(); // no basis labels on screen (owner decision)
    expect(within(detail).getByText(/section intervals do not add up/)).toBeInTheDocument();
    expect(within(detail).queryByText(/^0$/)).not.toBeInTheDocument();
  });

  it("lists shortage risks with high first, months ahead, blank unknown capacity and the groundwater note", async () => {
    setToken("t-officer");
    vi.stubGlobal("fetch", officerApi());
    renderScreen();
    await screen.findByText("Live data");
    fireEvent.click(screen.getByRole("tab", { name: "Shortage warnings" }));
    const list = screen.getByRole("list", { name: "Shortage risk list" });
    const items = within(list).getAllByRole("listitem");
    expect(items).toHaveLength(3);
    expect(items[0]).toHaveTextContent("AMEENPUR (PD 8)");
    expect(items[0]).toHaveTextContent("High");
    expect(items[0]).toHaveTextContent("1 month ahead");
    expect(items[0]).toHaveTextContent("ASSUMED");
    expect(items[2]).toHaveTextContent("ALPHA LOW");
    const unknown = items[1];
    expect(unknown).toHaveTextContent("40 MLD STP ATTAPUR");
    expect(unknown).toHaveTextContent("Unknown");
    expect(within(unknown).getByText("—")).toBeInTheDocument();
    expect(screen.getByText(/Groundwater data unavailable/)).toBeInTheDocument();
    expect(screen.getByText(/named as before the Feb\/Mar 2026 re-cut/)).toBeInTheDocument();
  });

  it("says groundwater is shown in the reasons, not used for the risk, when the API has it", async () => {
    setToken("t-officer");
    const reason = "Forecast 75 bookings in 2026-02; groundwater 0.8 m shallower than usual near this section (median of 7 wells within 5 km, 2026-01).";
    vi.stubGlobal("fetch", officerApi([shortageRow("ALPHA LOW", "low", { groundwater_status: "DERIVED", groundwater_m: -0.8, reason })]));
    renderScreen();
    await screen.findByText("Live data");
    fireEvent.click(screen.getByRole("tab", { name: "Shortage warnings" }));
    expect(screen.getByText(/0.8 m shallower than usual/)).toBeInTheDocument();
    expect(screen.getAllByText(/not used to set the risk|not part of the risk rule/).length).toBeGreaterThan(0);
    expect(screen.queryByText(/Groundwater data unavailable/)).not.toBeInTheDocument();
  });

  it("shows a small real capacity with a decimal instead of rounding it to zero", async () => {
    setToken("t-officer");
    vi.stubGlobal("fetch", officerApi([shortageRow("GUNDLAPOCHAMPALLY (PD 7)", "high", { capacity_trips: 0.3, capacity_ratio: 3.5156 })]));
    renderScreen();
    await screen.findByText("Live data");
    fireEvent.click(screen.getByRole("tab", { name: "Shortage warnings" }));
    const [item] = within(screen.getByRole("list", { name: "Shortage risk list" })).getAllByRole("listitem");
    expect(within(item).getByText("0.3")).toBeInTheDocument();
  });

  it("filters by risk and pages the long list with Show more", async () => {
    setToken("t-officer");
    const many = [
      ...Array.from({ length: 25 }, (_, i) => shortageRow(`LOW ${String(i).padStart(2, "0")}`, "low", { capacity_ratio: 0.1 })),
      ...Array.from({ length: 205 }, (_, i) => shortageRow(`MED ${String(i).padStart(3, "0")}`, "medium", { capacity_ratio: 0.9 })),
      shortageRow("ONLY HIGH", "high"),
    ];
    vi.stubGlobal("fetch", officerApi(many));
    renderScreen();
    await screen.findByText("Live data");
    fireEvent.click(screen.getByRole("tab", { name: "Shortage warnings" }));
    const list = () => screen.getByRole("list", { name: "Shortage risk list" });
    expect(within(list()).getAllByRole("listitem")).toHaveLength(20);
    expect(within(list()).getAllByRole("listitem")[0]).toHaveTextContent("ONLY HIGH");
    expect(screen.getByText("Showing 20 of 231")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Show more" }));
    expect(within(list()).getAllByRole("listitem")).toHaveLength(40);
    fireEvent.click(screen.getByRole("button", { name: "High (1)" }));
    expect(within(list()).getAllByRole("listitem")).toHaveLength(1);
    expect(screen.queryByRole("button", { name: "Show more" })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Low (25)" }));
    expect(within(list()).getAllByRole("listitem")).toHaveLength(20);
  });

  it("shows live backtest accuracy against the seasonal-naive baseline", async () => {
    setToken("t-officer");
    vi.stubGlobal("fetch", officerApi());
    renderScreen();
    await screen.findByText("Live data");
    fireEvent.click(screen.getByRole("tab", { name: "Accuracy vs baseline" }));
    expect(screen.getByText("15.1%")).toBeInTheDocument();
    expect(screen.getByText("25.3%")).toBeInTheDocument();
    expect(screen.getByText(/no model beats seasonal naive/)).toBeInTheDocument();
  });

  it("loads a selected section with its DERIVED interval and ASSUMED capacity", async () => {
    setToken("t-officer");
    vi.stubGlobal("fetch", officerApi());
    renderScreen();
    await screen.findByText("Live data");
    fireEvent.change(screen.getByRole("combobox", { name: "Area" }), { target: { value: "AMEENPUR (PD 8)" } });
    const detail = screen.getByRole("region", { name: "Selected forecast month" });
    await waitFor(() => expect(within(detail).getByText("18–54")).toBeInTheDocument());
    expect(within(detail).getByText("24")).toBeInTheDocument();
    expect(within(detail).queryByText(/ASSUMED/)).toBeNull();
  });

  it("asks for sign-in and keeps the labelled fixtures when nobody is signed in", async () => {
    const fetchMock = officerApi();
    vi.stubGlobal("fetch", fetchMock);
    renderScreen();
    expect(screen.getByText("Saved snapshot")).toBeInTheDocument();
    expect(screen.getByText(/Sign in as an officer to see live data/)).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("falls back and says the sign-in was not accepted when the API answers 401", async () => {
    setToken("t-officer");
    vi.stubGlobal("fetch", vi.fn((input: string) => Promise.resolve(input.endsWith("/auth/me") ? jsonResponse({ role: "officer", user_id: "off-1" }) : jsonResponse({ error: { code: "unauthorized", message: "Unknown token" } }, 401))));
    renderScreen();
    expect(await screen.findByText(/Your sign-in was not accepted/)).toBeInTheDocument();
    expect(screen.getByText("Saved snapshot")).toBeInTheDocument();
  });

  it("falls back and says the server could not be reached on a network error", async () => {
    setToken("t-officer");
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
    renderScreen();
    expect(await screen.findByText(/server could not be reached/)).toBeInTheDocument();
    expect(screen.getByText("Saved snapshot")).toBeInTheDocument();
  });
});
