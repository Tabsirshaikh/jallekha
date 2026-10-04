import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { useState } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { setToken } from "./api";
import { AuthProvider } from "./auth";
import DriverExperience from "./DriverExperience";
import type { VerifyResult } from "./driverAdapter";
import { LocaleProvider } from "./i18n";
import { apiError, callsTo, json, routedFetch } from "./test/apiMock";
import { confirmedOutcome, delivery, inside, issued, noLocation, outside, registeredPhones, stopsPage } from "./test/driverFixtures";

const SIGN_IN = "Sign in with a driver token to see your registered stops and record deliveries. Showing the sample route.";

function Harness() {
  const [page, setPage] = useState<"route" | "proof" | "help">("route");
  return <DriverExperience page={page} onNavigate={(item) => setPage(item === "driverProof" ? "proof" : item === "help" ? "help" : "route")} />;
}

function renderDriver() {
  return render(
    <LocaleProvider>
      <AuthProvider>
        <Harness />
      </AuthProvider>
    </LocaleProvider>,
  );
}

function stubPosition(position: { latitude: number; longitude: number } | "denied") {
  const getCurrentPosition = vi.fn((ok: PositionCallback, fail?: PositionErrorCallback | null) => {
    if (position === "denied") fail?.({ code: 1, message: "User denied Geolocation", PERMISSION_DENIED: 1, POSITION_UNAVAILABLE: 2, TIMEOUT: 3 } as GeolocationPositionError);
    else ok({ coords: { ...position, accuracy: 10 }, timestamp: Date.now() } as GeolocationPosition);
  });
  Object.defineProperty(navigator, "geolocation", { value: { getCurrentPosition }, configurable: true });
  return getCurrentPosition;
}

/** The live driver API: one stop, deliveries that move through start, OTP, verify and outcome. */
function driverApi(verify: { result: VerifyResult; location: typeof inside; patch?: object }, outcome: object = {}) {
  let id = "";
  return routedFetch({
    "GET /auth/me": () => json({ role: "driver", user_id: "drv-1" }),
    "GET /stops": () => json(stopsPage),
    "GET /deliveries": () => json({ total: 1, offset: 0, limit: 200, items: [delivery("D-20261003-00000001", { otp_issued: true, otp_verified: true, outcome_status: "Disputed" })] }),
    "POST /deliveries": () => (body) => {
      id = String((body as { delivery_id: string }).delivery_id);
      return json(delivery(id));
    },
    "POST /deliveries/*/otp": () => json(delivery(id, issued)),
    "POST /deliveries/*/otp/verify": () => json({ result: verify.result, location: verify.location, delivery: delivery(id, { ...issued, ...verify.patch }) }),
    "GET /deliveries/*": () => json({ ...delivery(id, { ...issued, ...verify.patch }), counts_toward_debt: null, ...outcome }),
  });
}

async function startAndSendCode() {
  fireEvent.click(await screen.findByRole("button", { name: "Open delivery steps" }));
  fireEvent.click(screen.getByRole("button", { name: "Start delivery" }));
  expect(await screen.findByText(/Delivery D-\d{8}-[0-9a-f]{8} started/)).toBeInTheDocument();
  fireEvent.click(screen.getByRole("radio", { name: /R2/ }));
  fireEvent.click(screen.getByRole("button", { name: "Send code" }));
  expect(await screen.findByText(/Code sent to R2/)).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("6-digit delivery code"), { target: { value: "123456" } });
  fireEvent.click(screen.getByRole("button", { name: "Check code at my location" }));
}

function expectNoSecrets(container: HTMLElement) {
  for (const phone of registeredPhones) expect(container.innerHTML).not.toContain(phone);
}

describe("DriverExperience", () => {
  beforeEach(() => setToken(null));
  afterEach(() => {
    vi.unstubAllGlobals();
    Reflect.deleteProperty(navigator, "geolocation");
  });

  it("shows the sample route with the snapshot chip and a sign-in reason when nobody is signed in", () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    renderDriver();
    expect(fetchMock).not.toHaveBeenCalled();
    expect(screen.getByText("Saved snapshot")).toBeInTheDocument();
    expect(screen.getByText(SIGN_IN)).toBeInTheDocument();
    expect(screen.getByText("Sample stop 01")).toBeInTheDocument();
  });

  it("asks for a driver token when another role is signed in", async () => {
    setToken("tok-off");
    vi.stubGlobal("fetch", routedFetch({ "GET /auth/me": () => json({ role: "officer", user_id: "off-1" }) }));
    renderDriver();
    expect(await screen.findByText("This is not a driver token. Sign in as a driver to record deliveries. Showing the sample route.")).toBeInTheDocument();
    expect(screen.getByText("Sample stop 01")).toBeInTheDocument();
  });

  it("says when the server cannot be reached and keeps the sample route", async () => {
    setToken("tok-drv");
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
    renderDriver();
    expect(await screen.findByText("The server could not be reached. Showing the sample route.")).toBeInTheDocument();
    expect(screen.getByText("Saved snapshot")).toBeInTheDocument();
    expect(screen.getByText("Sample stop 01")).toBeInTheDocument();
  });

  it("lists registered stops and the driver's deliveries from the API", async () => {
    setToken("tok-drv");
    const fetchMock = driverApi({ result: "verified", location: inside });
    vi.stubGlobal("fetch", fetchMock);
    const { container } = renderDriver();
    expect(await screen.findByText("Live data")).toBeInTheDocument();
    expect(screen.getByText("E2E-STOP-1")).toBeInTheDocument();
    expect(screen.getByText("2 representatives · 3 residents")).toBeInTheDocument();
    const list = within(container.querySelector(".driver-delivery-list") as HTMLElement);
    expect(list.getByText("D-20261003-00000001")).toBeInTheDocument();
    expect(list.getByText("Disputed")).toBeInTheDocument();
    expect(screen.queryByText("Sample stop 01")).not.toBeInTheDocument();
    expect(callsTo(fetchMock, "GET", "/deliveries")[0].url.searchParams.get("driver_id")).toBe("drv-1");
    expectNoSecrets(container);
  });

  it("records a delivery: start, code to a representative, verify inside the fence, Confirmed outcome", async () => {
    setToken("tok-drv");
    const position = stubPosition({ latitude: 17.3851, longitude: 78.4867 });
    const fetchMock = driverApi({ result: "verified", location: inside, patch: { otp_verified: true, sampled_residents: 3 } }, confirmedOutcome);
    vi.stubGlobal("fetch", fetchMock);
    const { container } = renderDriver();

    await startAndSendCode();
    expect(await screen.findByText("Code verified at the stop. Residents at this stop are now asked by SMS whether the water arrived.")).toBeInTheDocument();
    const outcome = await screen.findByRole("region", { name: "Delivery outcome" });
    await waitFor(() => expect(within(outcome).getByText("Confirmed")).toBeInTheDocument());
    expect(within(outcome).getByText("Counts toward water debt: Yes")).toBeInTheDocument();
    expect(within(outcome).getByText("OTP verified · residents mostly confirm")).toBeInTheDocument();

    const [start] = callsTo(fetchMock, "POST", "/deliveries");
    expect(start.body).toMatchObject({ stop_id: "E2E-STOP-1", driver_id: "drv-1" });
    expect(String(start.body?.delivery_id)).toMatch(/^D-\d{8}-[0-9a-f]{8}$/);
    expect(start.headers.Authorization).toBe("Bearer tok-drv");
    expect(callsTo(fetchMock, "POST", "/deliveries/*/otp")[0].body).toEqual({ representative_id: "R2" });
    expect(callsTo(fetchMock, "POST", "/deliveries/*/otp/verify")[0].body).toEqual({ code: "123456", lat: 17.3851, lon: 78.4867 });
    expect(position).toHaveBeenCalledTimes(1);
    expect(screen.getByLabelText("6-digit delivery code")).toHaveValue("");
    expect(container.textContent).not.toContain("123456");
    expectNoSecrets(container);
  });

  it("says how far outside the fence the driver is", async () => {
    setToken("tok-drv");
    stubPosition({ latitude: 17.4, longitude: 78.4867 });
    vi.stubGlobal("fetch", driverApi({ result: "outside_geofence", location: outside, patch: { outside_tries: 1 } }));
    renderDriver();
    await startAndSendCode();
    expect(await screen.findByText("You are about 1,668 m from the stop. The code can only be checked within 150 m. Move closer and try again; this try did not use up an attempt.")).toBeInTheDocument();
    const outcome = await screen.findByRole("region", { name: "Delivery outcome" });
    expect(within(outcome).getByText("Waiting for resident replies")).toBeInTheDocument();
    expect(within(outcome).getByText("Counts toward water debt: Not decided yet")).toBeInTheDocument();
  });

  it("reports a wrong code with the number of wrong tries", async () => {
    setToken("tok-drv");
    stubPosition({ latitude: 17.3851, longitude: 78.4867 });
    vi.stubGlobal("fetch", driverApi({ result: "wrong_code", location: inside, patch: { wrong_attempts: 1 } }));
    renderDriver();
    await startAndSendCode();
    expect(await screen.findByText("That code is not right. Wrong tries so far: 1. Too many wrong tries lock the code for this stop.")).toBeInTheDocument();
  });

  it("sends no position when location is denied, explains it and offers a retry", async () => {
    setToken("tok-drv");
    const position = stubPosition("denied");
    const fetchMock = driverApi({ result: "outside_geofence", location: noLocation, patch: { outside_tries: 1 } });
    vi.stubGlobal("fetch", fetchMock);
    renderDriver();
    await startAndSendCode();

    expect(await screen.findByRole("alert")).toHaveTextContent("Your position could not be read, so the code was checked without it. Turn on location for this site and try again.");
    expect(await screen.findByText("No position was sent, so the server could not check that you are at the stop. This try did not use up an attempt.")).toBeInTheDocument();
    expect(callsTo(fetchMock, "POST", "/deliveries/*/otp/verify")[0].body).toEqual({ code: "123456" });

    fireEvent.click(screen.getByRole("button", { name: "Try again with my location" }));
    await waitFor(() => expect(position).toHaveBeenCalledTimes(2));
    await waitFor(() => expect(callsTo(fetchMock, "POST", "/deliveries/*/otp/verify")).toHaveLength(2));
  });

  it("shows a server refusal without inventing a result", async () => {
    setToken("tok-drv");
    vi.stubGlobal("fetch", routedFetch({
      "GET /auth/me": () => json({ role: "driver", user_id: "drv-1" }),
      "GET /stops": () => json(stopsPage),
      "GET /deliveries": () => json({ total: 0, offset: 0, limit: 200, items: [] }),
      "POST /deliveries": () => apiError(403, "forbidden", "Role officer may not call this endpoint"),
    }));
    renderDriver();
    fireEvent.click(await screen.findByRole("button", { name: "Open delivery steps" }));
    fireEvent.click(screen.getByRole("button", { name: "Start delivery" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("This is not a driver token. Sign in as a driver to record deliveries.");
    expect(screen.queryByRole("button", { name: "Send code" })).not.toBeInTheDocument();
  });
});
