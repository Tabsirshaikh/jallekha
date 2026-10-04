import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { setToken } from "./api";
import { AuthProvider } from "./auth";
import ImpactExperience from "./ImpactExperience";
import { LocaleProvider } from "./i18n";
import { impactResponse, jsonResponse } from "./test/apiFixtures";

function renderScreen() {
  return render(
    <LocaleProvider>
      <AuthProvider>
        <ImpactExperience />
      </AuthProvider>
    </LocaleProvider>,
  );
}

function officerApi() {
  return vi.fn((input: string) => {
    const url = new URL(input, "http://localhost");
    if (url.pathname === "/auth/me") return Promise.resolve(jsonResponse({ role: "officer", user_id: "off-1" }));
    if (url.pathname === "/impact") return Promise.resolve(jsonResponse(impactResponse(url.searchParams.get("replay") ?? "main_2025", url.searchParams.get("scenario") ?? "tight")));
    return Promise.resolve(jsonResponse({ error: { code: "not_found", message: "no route" } }, 404));
  });
}

describe("ImpactExperience", () => {
  beforeEach(() => setToken(null));
  afterEach(() => vi.unstubAllGlobals());

  it("renders the live A8 results with their SIMULATION badge and the live chip", async () => {
    setToken("t-officer");
    const fetchMock = officerApi();
    vi.stubGlobal("fetch", fetchMock);
    renderScreen();
    expect(await screen.findByText("Live data")).toBeInTheDocument();
    expect(screen.getByText("62.5%")).toBeInTheDocument();
    expect(screen.getByText("50%")).toBeInTheDocument();
    expect(screen.getAllByText("SIMULATION").length).toBeGreaterThan(0);
    expect(screen.getByText(/JalLekha fair queue/)).toBeInTheDocument();
    expect(screen.getByText(/live reason/)).toBeInTheDocument();
    const impactCalls = fetchMock.mock.calls.map(([u]) => String(u)).filter((u) => u.includes("/impact"));
    expect(impactCalls.at(-1)).toMatch(/replay=main_2025&scenario=fleet/);
  });

  it("asks the API again for a different scenario", async () => {
    setToken("t-officer");
    const fetchMock = officerApi();
    vi.stubGlobal("fetch", fetchMock);
    renderScreen();
    await screen.findByText("Live data");
    fireEvent.change(screen.getByRole("combobox", { name: "Scenario" }), { target: { value: "tight" } });
    await waitFor(() => expect(fetchMock.mock.calls.some(([u]) => String(u).includes("scenario=tight"))).toBe(true));
  });

  it("asks for sign-in and keeps the committed A8 snapshot when nobody is signed in", () => {
    const fetchMock = officerApi();
    vi.stubGlobal("fetch", fetchMock);
    renderScreen();
    expect(screen.getByText("Saved snapshot")).toBeInTheDocument();
    expect(screen.getByText(/Sign in as an officer to see live data/)).toBeInTheDocument();
    expect(screen.getAllByText("98.71%").length).toBeGreaterThan(0);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("falls back and says so when the API answers 401", async () => {
    setToken("t-officer");
    vi.stubGlobal("fetch", vi.fn((input: string) => Promise.resolve(input.endsWith("/auth/me") ? jsonResponse({ role: "officer", user_id: "off-1" }) : jsonResponse({ error: { code: "unauthorized", message: "Unknown token" } }, 401))));
    renderScreen();
    expect(await screen.findByText(/Your sign-in was not accepted/)).toBeInTheDocument();
    expect(screen.getByText("Saved snapshot")).toBeInTheDocument();
    expect(screen.getAllByText("98.71%").length).toBeGreaterThan(0);
  });

  it("falls back and says so on a network error", async () => {
    setToken("t-officer");
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
    renderScreen();
    expect(await screen.findByText(/server could not be reached/)).toBeInTheDocument();
    expect(screen.getAllByText("98.71%").length).toBeGreaterThan(0);
  });
});
