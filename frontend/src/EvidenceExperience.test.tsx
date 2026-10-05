import { fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { setToken } from "./api";
import { AuthProvider } from "./auth";
import EvidenceExperience from "./EvidenceExperience";
import { LocaleProvider } from "./i18n";
import { errorFetch, liveFetch } from "./test/evidenceFixtures";

const PEER = "Peer-reference ratio below threshold";
const NB = "Statistical-model (negative binomial) reference ratio below threshold";

function renderScreen() {
  return render(
    <LocaleProvider>
      <AuthProvider>
        <EvidenceExperience />
      </AuthProvider>
    </LocaleProvider>,
  );
}

function wardList(container: HTMLElement) {
  return within(container.querySelector(".evidence-ward-list") as HTMLElement);
}

function expectOneReasonPerMethod(card: HTMLElement) {
  expect(within(card).getAllByText(PEER)).toHaveLength(1);
  expect(within(card).getAllByText(NB)).toHaveLength(1);
}

describe("EvidenceExperience", () => {
  beforeEach(() => setToken(null));
  afterEach(() => vi.unstubAllGlobals());

  it("shows live API data and says so", async () => {
    setToken("t-officer");
    vi.stubGlobal("fetch", vi.fn().mockImplementation(liveFetch));
    const { container } = renderScreen();

    expect(await screen.findByText("Live data")).toBeInTheDocument();
    expect(screen.getByText("Served by the JalLekha API just now.")).toBeInTheDocument();
    expect(wardList(container).getByText("Ward 901 Testpur")).toBeInTheDocument();
    expect(screen.queryByText("Ward 91 Khairatabad")).not.toBeInTheDocument();
    expect(container.querySelectorAll(".evidence-map path")).toHaveLength(3);

    // Unavailable values stay blank, never zero.
    fireEvent.click(wardList(container).getByText("Ward 902 Nullabad"));
    const card = container.querySelector(".evidence-selected-card") as HTMLElement;
    expect(within(card).getByRole("heading", { name: "Ward 902 Nullabad" })).toBeInTheDocument();
    expect(within(card).queryByText(/^0/)).not.toBeInTheDocument();
    expect(within(card).getByText("Unavailable")).toBeInTheDocument();

    // OSM facility counts are shown with their source and the warning that the map is incomplete.
    fireEvent.click(wardList(container).getByText("Ward 901 Testpur"));
    const testpur = container.querySelector(".evidence-selected-card") as HTMLElement;
    expect(within(testpur).getByText("Hospitals, clinics, schools, care homes · OSM")).toBeInTheDocument();
    expect(within(testpur).getByText("12")).toBeInTheDocument();
    expect(within(testpur).getByText(/facilities missing from the map are not counted/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("tab", { name: "Booking equity" }));
    expect(screen.getByText("Live: concentration of observed bookings, not unequal need")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("tab", { name: "Field checks" }));
    const cards = container.querySelectorAll<HTMLElement>(".evidence-candidate-card");
    expect(cards).toHaveLength(1);
    expect(within(cards[0]).getByRole("heading", { name: "Ward 901 Testpur" })).toBeInTheDocument();
    expectOneReasonPerMethod(cards[0]);
    expect(screen.getAllByText(/a flag is not proof/).length).toBeGreaterThan(0);
  });

  it("falls back to the saved snapshot on a 401 and asks for sign-in", async () => {
    setToken("t-expired");
    vi.stubGlobal("fetch", vi.fn().mockImplementation(errorFetch(401)));
    const { container } = renderScreen();
    expect(await screen.findByText("Saved snapshot")).toBeInTheDocument();
    expect(screen.getByText("Sign in with an officer token to see live data. Showing the saved snapshot.")).toBeInTheDocument();
    expect(wardList(container).getByText("Ward 91 Khairatabad")).toBeInTheDocument();
  });

  it("falls back to the saved snapshot when the server cannot be reached", async () => {
    setToken("t-officer");
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
    const { container } = renderScreen();
    expect(await screen.findByText("The server could not be reached. Showing the saved snapshot.")).toBeInTheDocument();
    expect(screen.getByText("Saved snapshot")).toBeInTheDocument();
    expect(wardList(container).getByText("Ward 91 Khairatabad")).toBeInTheDocument();
  });

  it("does not call the API when signed out and shows the snapshot", () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    renderScreen();
    expect(fetchMock).not.toHaveBeenCalled();
    expect(screen.getByText("Saved snapshot")).toBeInTheDocument();
    expect(screen.getByText("Sign in with an officer token to see live data. Showing the saved snapshot.")).toBeInTheDocument();
  });

  it("lists the six snapshot field-check candidates with one reason per method", () => {
    vi.stubGlobal("fetch", vi.fn());
    const { container } = renderScreen();
    fireEvent.click(screen.getByRole("tab", { name: "Field checks" }));
    const cards = container.querySelectorAll<HTMLElement>(".evidence-candidate-card");
    expect(cards).toHaveLength(6);
    cards.forEach(expectOneReasonPerMethod);
  });
});
