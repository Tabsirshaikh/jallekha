import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { setToken } from "./api";
import { AuthProvider } from "./auth";
import { LocaleProvider, type Locale } from "./i18n";
import ResidentExperience from "./ResidentExperience";
import { apiError, callsTo, json, routedFetch } from "./test/apiMock";
import { fakeIndexedDb } from "./test/fakeIndexedDb";
import { noValue, smsSummary, wardCard } from "./test/wardCardFixtures";

function renderWard(locale: Locale = "en") {
  return render(
    <LocaleProvider initialLocale={locale}>
      <AuthProvider>
        <ResidentExperience page="ward" onNavigate={() => undefined} />
      </AuthProvider>
    </LocaleProvider>,
  );
}

function residentApi(card = wardCard(), sms = smsSummary()) {
  return routedFetch({
    "GET /auth/me": () => json({ role: "resident", user_id: "res-1" }),
    "GET /wards/*/*/report-card": () => json(card),
    "GET /wards/*/*/sms-summary": () => json(sms),
  });
}

describe("ResidentExperience ward report card", () => {
  beforeEach(() => {
    setToken(null);
    vi.stubGlobal("indexedDB", fakeIndexedDb({ "jallekha-resident": { reports: [] } }));
  });
  afterEach(async () => {
    cleanup();
    await new Promise((resolve) => setTimeout(resolve, 10)); // let the screen's own storage read finish before indexedDB is unstubbed
    Reflect.deleteProperty(navigator, "clipboard");
    vi.unstubAllGlobals();
  });

  it("shows the live card for a resident, asking for the ward id as it is", async () => {
    setToken("tok-res");
    const fetchMock = residentApi();
    vi.stubGlobal("fetch", fetchMock);
    renderWard();

    expect(await screen.findByText("Live data")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Ward 105 Gachibowli" })).toBeInTheDocument();
    expect(screen.queryByText(/SYNTHETIC demonstration only/)).not.toBeInTheDocument();
    const [cardCall] = callsTo(fetchMock, "GET", "/wards/*/*/report-card");
    expect(cardCall.url.pathname).toBe("/wards/relation/7848824/report-card");
    expect(cardCall.headers.Authorization).toBe("Bearer tok-res");
    expect(callsTo(fetchMock, "GET", "/wards/*/*/sms-summary")[0].url.search).toBe("?lang=en");

    expect(screen.getByText("66,431")).toBeInTheDocument();
    expect(screen.getByText("Piped water, supply hours not known")).toBeInTheDocument();

    const deliveries = within(screen.getByRole("region", { name: "Deliveries" }));
    expect(deliveries.getByText("SYNTHETIC")).toBeInTheDocument();
    expect(deliveries.getByText("Period").nextElementSibling).toHaveTextContent("Last 30 days");
    expect(deliveries.getByText("Deliveries started").nextElementSibling).toHaveTextContent("3");
    expect(deliveries.getByText("Confirmed").nextElementSibling).toHaveTextContent("2");
    expect(deliveries.getByText("Disputed").nextElementSibling).toHaveTextContent("1");
    expect(deliveries.getByText("Still open").nextElementSibling).toHaveTextContent("0");

    const debt = within(screen.getByRole("region", { name: "Water debt" }));
    expect(debt.getByText("DERIVED")).toBeInTheDocument();
    expect(debt.getByText("Tanker loads owed").nextElementSibling).toHaveTextContent("24");
    expect(debt.getByText("Litres owed").nextElementSibling).toHaveTextContent("120,000");
    expect(debt.getByText("Days in debt").nextElementSibling).toHaveTextContent("1");
    expect(debt.getByText("Alert raised").nextElementSibling).toHaveTextContent("No");
    expect(debt.getByText("Last day closed").nextElementSibling).toHaveTextContent("2026-10-03");

    const schedule = within(screen.getByRole("region", { name: "Schedule" }));
    expect(schedule.getByText("Plan day").nextElementSibling).toHaveTextContent("2026-10-03");
    expect(schedule.getByText("Status").nextElementSibling).toHaveTextContent("Approved");
    expect(schedule.getByText("Based on").nextElementSibling).toHaveTextContent("Bookings supplied for the day");
    expect(schedule.getByText("Booked trips served").nextElementSibling).toHaveTextContent("4");
    expect(schedule.getByText("Booked trips waiting").nextElementSibling).toHaveTextContent("0");
    expect(schedule.getByText("stop-g1").nextElementSibling).toHaveTextContent("26 loads");
  });

  it("shows the SMS text with a copy button", async () => {
    setToken("tok-res");
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", { value: { writeText }, configurable: true });
    vi.stubGlobal("fetch", residentApi());
    renderWard();

    expect(await screen.findByText(/Ward 105 Gachibowli: 66431 tanker bookings/)).toBeInTheDocument();
    expect(screen.queryByText(/This text is in English/)).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Copy SMS text" }));
    await waitFor(() => expect(writeText).toHaveBeenCalledWith(expect.stringContaining("66431 tanker bookings")));
    expect(await screen.findByRole("button", { name: "Copied" })).toBeInTheDocument();
  });

  it("says the SMS is in English when the wording for the language is not reviewed yet", async () => {
    setToken("tok-res");
    const fetchMock = residentApi(wardCard(), smsSummary("te", "en"));
    vi.stubGlobal("fetch", fetchMock);
    renderWard("te");

    expect(await screen.findByText(/Ward 105 Gachibowli: 66431 tanker bookings/)).toBeInTheDocument();
    expect(screen.getByRole("note")).toHaveTextContent("ఇంగ్లీషులో ఉంది");
    expect(callsTo(fetchMock, "GET", "/wards/*/*/sms-summary")[0].url.search).toBe("?lang=te");
  });

  it("shows the reason, and no number, for a block that has no value", async () => {
    setToken("tok-res");
    vi.stubGlobal("fetch", residentApi(wardCard({
      deliveries: noValue("no delivery stop is registered in this ward yet"),
      debt: noValue("no day has been closed for this ward yet"),
      schedule: noValue("no plan is stored for this ward"),
    })));
    renderWard();

    await screen.findByText("Live data");
    const deliveries = within(screen.getByRole("region", { name: "Deliveries" }));
    expect(deliveries.getByText(/no delivery stop is registered in this ward yet/)).toBeInTheDocument();
    expect(deliveries.queryByText("Deliveries started")).not.toBeInTheDocument();
    const debt = within(screen.getByRole("region", { name: "Water debt" }));
    expect(debt.getByText(/no day has been closed for this ward yet/)).toBeInTheDocument();
    expect(debt.queryByText("Tanker loads owed")).not.toBeInTheDocument();
    expect(within(screen.getByRole("region", { name: "Schedule" })).getByText(/no plan is stored for this ward/)).toBeInTheDocument();
  });

  it("asks for another ward from the picker", async () => {
    setToken("tok-res");
    const fetchMock = residentApi();
    vi.stubGlobal("fetch", fetchMock);
    renderWard();
    await screen.findByText("Live data");

    const picker = screen.getByRole("combobox", { name: "Choose ward" });
    expect(within(picker).getByRole("option", { name: "Ward 150 Monda Market" })).toBeInTheDocument();
    fireEvent.change(picker, { target: { value: "relation/7857838" } });
    await waitFor(() => expect(callsTo(fetchMock, "GET", "/wards/*/*/report-card").some((call) => call.url.pathname === "/wards/relation/7857838/report-card")).toBe(true));
  });

  it("keeps the labelled sample and asks for sign-in when nobody is signed in", () => {
    const fetchMock = residentApi();
    vi.stubGlobal("fetch", fetchMock);
    renderWard();

    expect(screen.getByText("Saved snapshot")).toBeInTheDocument();
    expect(screen.getByText(/Sign in to see live ward figures/)).toBeInTheDocument();
    expect(screen.getByText(/SYNTHETIC demonstration only/)).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Sample Ward 12" })).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "Water debt" })).not.toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("does not ask the ward routes for a driver, and says live cards are not for that role", async () => {
    setToken("tok-driver");
    const fetchMock = routedFetch({ "GET /auth/me": () => json({ role: "driver", user_id: "drv-1" }) });
    vi.stubGlobal("fetch", fetchMock);
    renderWard();

    expect(await screen.findByText(/live ward cards are for residents, councillors and officers/i)).toBeInTheDocument();
    expect(callsTo(fetchMock, "GET", "/wards/*/*/report-card")).toHaveLength(0);
    expect(screen.getByText("Saved snapshot")).toBeInTheDocument();
  });

  it("falls back to the sample and says so when the API answers with an error", async () => {
    setToken("tok-res");
    vi.stubGlobal("fetch", routedFetch({
      "GET /auth/me": () => json({ role: "resident", user_id: "res-1" }),
      "GET /wards/*/*/report-card": () => apiError(500, "internal_error"),
      "GET /wards/*/*/sms-summary": () => apiError(500, "internal_error"),
    }));
    renderWard();

    expect(await screen.findByText(/The server returned an error/)).toBeInTheDocument();
    expect(screen.getByText("Saved snapshot")).toBeInTheDocument();
    expect(screen.getByText(/SYNTHETIC demonstration only/)).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "Water debt" })).not.toBeInTheDocument();
  });

  it("falls back on a network error", async () => {
    setToken("tok-res");
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
      if (String(input).endsWith("/auth/me")) return json({ role: "resident", user_id: "res-1" });
      throw new TypeError("Failed to fetch");
    }));
    renderWard();
    expect(await screen.findByText(/server could not be reached/)).toBeInTheDocument();
    expect(screen.getByText("Saved snapshot")).toBeInTheDocument();
  });

  it("keeps the live card and says the SMS is unavailable when only the SMS call fails", async () => {
    setToken("tok-res");
    vi.stubGlobal("fetch", routedFetch({
      "GET /auth/me": () => json({ role: "resident", user_id: "res-1" }),
      "GET /wards/*/*/report-card": () => json(wardCard()),
      "GET /wards/*/*/sms-summary": () => apiError(500, "internal_error"),
    }));
    renderWard();

    await screen.findByText("Live data");
    expect(await screen.findByText("The SMS summary is not available right now.")).toBeInTheDocument();
    expect(screen.getByText("Live data")).toBeInTheDocument();
  });

  it("shows plain words for a service type, and the code itself only when it is not known", async () => {
    setToken("tok-res");
    vi.stubGlobal("fetch", residentApi(wardCard({ need: { service_class: "no_connection", need_weight: 2.1, need_basis: "DERIVED" } })));
    renderWard();
    expect(await screen.findByText("Mostly no tap connection")).toBeInTheDocument();
    cleanup();

    vi.stubGlobal("fetch", residentApi(wardCard({ need: { service_class: "something_new", need_weight: 2.1, need_basis: "DERIVED" } })));
    renderWard();
    expect(await screen.findByText("something_new")).toBeInTheDocument();
  });

  it("shows 'Not available.' and not 0 when a ward has no placed bookings", async () => {
    setToken("tok-res");
    const base = wardCard();
    vi.stubGlobal("fetch", residentApi(wardCard({ bookings: { ...base.bookings, bookings: null, bookings_per_1000: null } })));
    renderWard();
    await screen.findByText("Live data");
    const tile = screen.getByText(/Tanker bookings, 2022-01 to 2024-02/).closest("article") as HTMLElement;
    expect(within(tile).getByText("Not available.")).toBeInTheDocument();
    expect(within(tile).queryByText("0")).not.toBeInTheDocument();
  });

  it("can choose any ward of the evidence snapshot and asks for that ward", async () => {
    setToken("tok-res");
    const fetchMock = residentApi();
    vi.stubGlobal("fetch", fetchMock);
    renderWard();
    await screen.findByText("Live data");

    const picker = screen.getByRole("combobox", { name: "Choose ward" });
    expect(picker).toHaveValue("relation/7848824");
    expect(within(picker).getAllByRole("option")).toHaveLength(145);
    fireEvent.change(picker, { target: { value: "relation/7848799" } });
    await waitFor(() => expect(callsTo(fetchMock, "GET", "/wards/*/*/report-card").some((call) => call.url.pathname === "/wards/relation/7848799/report-card")).toBe(true));
    expect(callsTo(fetchMock, "GET", "/wards/*/*/sms-summary").some((call) => call.url.pathname === "/wards/relation/7848799/sms-summary")).toBe(true);
  });

  it("keeps the ward picker and a retry button above the sample after the card request fails", async () => {
    setToken("tok-res");
    let failing = true;
    const fetchMock = routedFetch({
      "GET /auth/me": () => json({ role: "resident", user_id: "res-1" }),
      "GET /wards/*/*/report-card": () => (failing ? apiError(500, "internal_error") : json(wardCard())),
      "GET /wards/*/*/sms-summary": () => json(smsSummary()),
    });
    vi.stubGlobal("fetch", fetchMock);
    renderWard();

    expect(await screen.findByText(/The server returned an error/)).toBeInTheDocument();
    expect(screen.getByText(/SYNTHETIC demonstration only/)).toBeInTheDocument();
    const picker = screen.getByRole("combobox", { name: "Choose ward" });
    const cardCalls = () => callsTo(fetchMock, "GET", "/wards/*/*/report-card");
    expect(cardCalls()).toHaveLength(1);

    fireEvent.change(picker, { target: { value: "relation/7857838" } });
    await waitFor(() => expect(cardCalls().some((call) => call.url.pathname === "/wards/relation/7857838/report-card")).toBe(true));
    await screen.findByText(/The server returned an error/);
    const before = cardCalls().length;

    failing = false;
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    await waitFor(() => expect(cardCalls().length).toBe(before + 1));
    expect(await screen.findByText("Live data")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Try again" })).not.toBeInTheDocument();
  });

  it("has its own loading text while the SMS is on its way", async () => {
    setToken("tok-res");
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
      const path = new URL(String(input), "http://localhost").pathname;
      if (path === "/auth/me") return json({ role: "resident", user_id: "res-1" });
      if (path.endsWith("/report-card")) return json(wardCard());
      return new Promise<Response>(() => undefined);
    }));
    renderWard();
    await screen.findByText("Live data");
    expect(screen.getByText("Loading the SMS text…")).toBeInTheDocument();
    expect(screen.queryByText("Loading the ward card…")).not.toBeInTheDocument();
  });
});
