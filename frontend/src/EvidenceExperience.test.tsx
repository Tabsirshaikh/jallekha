import { fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { setToken } from "./api";
import { AuthProvider } from "./auth";
import EvidenceExperience from "./EvidenceExperience";
import { LocaleProvider } from "./i18n";
import { errorFetch, liveFetch } from "./test/evidenceFixtures";

function renderScreen() {
  return render(
    <LocaleProvider>
      <AuthProvider>
        <EvidenceExperience />
      </AuthProvider>
    </LocaleProvider>,
  );
}

describe("EvidenceExperience", () => {
  beforeEach(() => setToken(null));
  afterEach(() => vi.unstubAllGlobals());

  it("shows the live wards and opens a ward sheet with the live signs in plain words", async () => {
    setToken("t-officer");
    vi.stubGlobal("fetch", vi.fn().mockImplementation(liveFetch));
    const { container } = renderScreen();
    expect(await screen.findByText("wards with 2 or more warning signs")).toBeInTheDocument();
    expect(container.querySelectorAll(".atlas-map path")).toHaveLength(3);
    expect(screen.queryByText(/DERIVED|SIMULATION|GHMC_2016/)).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Ward 901 Testpur" }));
    const sheet = within(screen.getByRole("dialog", { name: "Ward 901 Testpur" }));
    expect(sheet.getByText("2 or more warning signs")).toBeInTheDocument();
    expect(sheet.getByText("Background")).toBeInTheDocument();
    expect(sheet.getByText("Owed 6 tanker loads")).toBeInTheDocument();
    expect(sheet.getByText('3 "no water" complaints this week')).toBeInTheDocument();
    expect(sheet.getByText("No groundwater wells nearby")).toBeInTheDocument();
    fireEvent.click(sheet.getByRole("button", { name: "Close" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("shows live booking concentration on the bookings tab", async () => {
    setToken("t-officer");
    vi.stubGlobal("fetch", vi.fn().mockImplementation(liveFetch));
    renderScreen();
    await screen.findByText("wards with 2 or more warning signs");
    fireEvent.click(screen.getByRole("tab", { name: "2. Bookings" }));
    expect(screen.getByText("Top 2 areas take 68% of all tankers")).toBeInTheDocument();
    expect(screen.getByText("Last 30 days, 120 live bookings")).toBeInTheDocument();
    expect(screen.getByText("MADHAPUR")).toBeInTheDocument();
  });

  it("falls back to saved data on a 401 and asks for sign-in", async () => {
    setToken("t-bad");
    vi.stubGlobal("fetch", vi.fn().mockImplementation(errorFetch(401)));
    const { container } = renderScreen();
    expect(await screen.findByText(/^Sign in as an officer/)).toBeInTheDocument();
    expect(container.querySelectorAll(".atlas-map path").length).toBeGreaterThan(100);
  });

  it("does not call the API when signed out", () => {
    const fetch = vi.fn();
    vi.stubGlobal("fetch", fetch);
    renderScreen();
    expect(fetch).not.toHaveBeenCalled();
    expect(screen.getByText(/^Sign in as an officer/)).toBeInTheDocument();
  });

  it("shows exact sections and map dots without ward booking estimates", () => {
    vi.stubGlobal("fetch", vi.fn());
    const { container } = renderScreen();
    fireEvent.click(screen.getByRole("tab", { name: "3. Low bookings" }));
    const cards = container.querySelectorAll(".atlas-check-card");
    expect(cards.length).toBeGreaterThan(0);
    expect(container.querySelectorAll(".atlas-map circle")).toHaveLength(cards.length);
    const first = within(cards[0] as HTMLElement);
    expect(first.getByText(/^Booked .* tankers in 2025$/)).toBeInTheDocument();
    expect(first.getByText(/^Bookings per 1,000 domestic connections:/)).toBeInTheDocument();
    expect(first.getByText(/^Similar sections' rate:/)).toBeInTheDocument();
    expect(screen.queryByText(/^Statistical model/)).not.toBeInTheDocument();
    expect(first.getByText("Not yet checked on the ground")).toBeInTheDocument();
    fireEvent.click(first.getByRole("button", { name: "Open on map" }));
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(screen.queryByText(/^5 similar wards booked about/)).not.toBeInTheDocument();
  });

  it("searches wards and opens the chosen one", () => {
    vi.stubGlobal("fetch", vi.fn());
    const { container } = renderScreen();
    fireEvent.change(screen.getByLabelText("Find a ward"), { target: { value: "Gachibowli" } });
    fireEvent.click(within(container.querySelector(".atlas-search ul") as HTMLElement).getByRole("button", { name: "Ward 105 Gachibowli" }));
    expect(screen.getByRole("dialog", { name: "Ward 105 Gachibowli" })).toBeInTheDocument();
  });

  it("uses the live section list, including an empty list, instead of saved flags", async () => {
    setToken("t-officer");
    vi.stubGlobal("fetch", vi.fn().mockImplementation(liveFetch));
    const { container } = renderScreen();
    await screen.findByText("wards with 2 or more warning signs");
    fireEvent.click(screen.getByRole("tab", { name: "3. Low bookings" }));
    expect(await screen.findByText("Section checks from the service")).toBeInTheDocument();
    expect(container.querySelectorAll(".atlas-check-card")).toHaveLength(1);
    expect(container.querySelectorAll(".atlas-map circle")).toHaveLength(1);
    fireEvent.click(screen.getByRole("button", { name: "TEST SECTION" }));
    expect(screen.getByRole("dialog", { name: "Ward 901 Testpur" })).toBeInTheDocument();
    expect(screen.queryByText(/^Statistical model/)).not.toBeInTheDocument();
  });

  it("zooms only with the buttons", () => {
    vi.stubGlobal("fetch", vi.fn());
    const { container } = renderScreen();
    const svg = container.querySelector(".atlas-map") as SVGSVGElement;
    const fitted = svg.getAttribute("viewBox");
    fireEvent.wheel(svg, { deltaY: -100 });
    expect(svg.getAttribute("viewBox")).toBe(fitted);
    fireEvent.click(screen.getByRole("button", { name: "Zoom in" }));
    expect(svg.getAttribute("viewBox")).not.toBe(fitted);
    fireEvent.click(screen.getByRole("button", { name: "Fit map" }));
    expect(svg.getAttribute("viewBox")).toBe(fitted);
  });

  it("ranks wards under the map and lists building growth A-Z", () => {
    vi.stubGlobal("fetch", vi.fn());
    const { container } = renderScreen();
    expect(container.querySelectorAll(".atlas-rank li")).toHaveLength(15);
    fireEvent.click(screen.getByRole("button", { name: "Show all wards" }));
    expect(container.querySelectorAll(".atlas-rank li")).toHaveLength(145);
    fireEvent.click(screen.getByRole("radio", { name: "Building growth" }));
    expect(screen.getByText(/^Listed A–Z, not ranked/)).toBeInTheDocument();
  });
});
