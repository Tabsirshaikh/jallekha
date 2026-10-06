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
    expect(await screen.findByText("wards where need may be rising")).toBeInTheDocument();
    expect(container.querySelectorAll(".atlas-map path")).toHaveLength(3);
    expect(screen.queryByText(/DERIVED|SIMULATION|GHMC_2016/)).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Ward 901 Testpur" }));
    const sheet = within(screen.getByRole("dialog", { name: "Ward 901 Testpur" }));
    expect(sheet.getByText("Need may be rising")).toBeInTheDocument();
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
    await screen.findByText("wards where need may be rising");
    fireEvent.click(screen.getByRole("tab", { name: "Bookings" }));
    expect(screen.getByText("Top 2 areas take 68% of all tankers")).toBeInTheDocument();
    expect(screen.getByText("Last 30 days, 120 live bookings")).toBeInTheDocument();
    expect(screen.getByText("MADHAPUR")).toBeInTheDocument();
  });

  it("falls back to saved data on a 401 and asks for sign-in", async () => {
    setToken("t-bad");
    vi.stubGlobal("fetch", vi.fn().mockImplementation(errorFetch(401)));
    const { container } = renderScreen();
    expect(await screen.findByRole("note")).toHaveTextContent("Sign in as an officer");
    expect(container.querySelectorAll(".atlas-map path").length).toBeGreaterThan(100);
  });

  it("does not call the API when signed out", () => {
    const fetch = vi.fn();
    vi.stubGlobal("fetch", fetch);
    renderScreen();
    expect(fetch).not.toHaveBeenCalled();
    expect(screen.getByRole("note")).toHaveTextContent("Sign in as an officer");
  });

  it("explains low-booking wards as booked vs expected", () => {
    vi.stubGlobal("fetch", vi.fn());
    const { container } = renderScreen();
    fireEvent.click(screen.getByRole("tab", { name: "Low bookings" }));
    const cards = container.querySelectorAll(".atlas-check-card");
    expect(cards.length).toBe(6);
    const first = within(cards[0] as HTMLElement);
    expect(first.getByText(/^Booked .* tankers \(2022–24\)$/)).toBeInTheDocument();
    expect(first.getByText(/^Similar wards booked about/)).toBeInTheDocument();
    expect(first.getByText(/^Our model expected about/)).toBeInTheDocument();
  });

  it("searches wards and opens the chosen one", () => {
    vi.stubGlobal("fetch", vi.fn());
    const { container } = renderScreen();
    fireEvent.change(screen.getByLabelText("Find a ward"), { target: { value: "Gachibowli" } });
    fireEvent.click(within(container.querySelector(".atlas-search ul") as HTMLElement).getByRole("button", { name: "Ward 105 Gachibowli" }));
    expect(screen.getByRole("dialog", { name: "Ward 105 Gachibowli" })).toBeInTheDocument();
  });
});
