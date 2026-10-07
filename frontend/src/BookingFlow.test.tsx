import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import BookingExperience, { type BookingView } from "./BookingExperience";
import DriverPlanRoute from "./DriverPlanRoute";
import { LocaleProvider } from "./i18n";
import { callsTo, json, routedFetch } from "./test/apiMock";

const booking = (over: Partial<BookingView> = {}): BookingView => ({
  booking_id: "BK-20261007-ABC123", arrived_at: "2026-10-07T07:10:00+05:30", section_name: "KONDAPUR (DIV 15)", lat: 17.4588, lon: 78.3731,
  category: "home", facility_name: null, water_at_home: "no", claim_status: "NONE", tier: 1, priority: "Second: no water at home", status: "WAITING",
  plan_id: null, tanker_id: null, station_id: null, trip_n: null, depart: null, arrive: null, delivery: null, phone_last2: "77", basis: "REAL", ...over,
});

describe("booking a tanker", () => {
  beforeEach(() => localStorage.clear());
  afterEach(() => vi.unstubAllGlobals());

  it("finds the section from the location, then books with who it is for and water at home", async () => {
    const fetchMock = routedFetch({
      "GET /bookings/locate": () => json({ inside: true, section: "section:KONDAPUR (DIV 15)", section_name: "KONDAPUR (DIV 15)", ward_id: "relation/1", ward_name: "Ward 107 Madhapur" }),
      "POST /bookings": () => json(booking(), 201),
      "GET /bookings/*": () => json(booking()),
      "GET /sms/test-mode": () => json({ test_mode: false }),
    });
    vi.stubGlobal("fetch", fetchMock);
    const geo = { getCurrentPosition: (ok: PositionCallback) => ok({ coords: { latitude: 17.4588, longitude: 78.3731 } } as GeolocationPosition) };
    vi.stubGlobal("navigator", { ...navigator, geolocation: geo });
    render(<LocaleProvider><BookingExperience /></LocaleProvider>);
    fireEvent.click(screen.getByRole("button", { name: "Use my location" }));
    expect(await screen.findByText("KONDAPUR (DIV 15)")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("radio", { name: "No water at all" }));
    fireEvent.change(screen.getByLabelText(/Phone \(with country code\)/), { target: { value: "+919800007777" } });
    fireEvent.click(screen.getByRole("button", { name: "Book the tanker" }));
    expect(await screen.findByText(/Booked: BK-20261007-ABC123/)).toBeInTheDocument();
    const sent = callsTo(fetchMock, "POST", "/bookings")[0].body!;
    expect(sent).toMatchObject({ category: "home", water_at_home: "no", phone: "+919800007777", lat: 17.4588, lon: 78.3731 });
    const card = await screen.findByRole("heading", { name: "My bookings" });
    expect(within(card.parentElement!).getByText("Second: no water at home")).toBeInTheDocument();
  });

  it("asks for the name of a hospital, which an officer checks before it goes first", async () => {
    vi.stubGlobal("fetch", routedFetch({ "GET /bookings/locate": () => json({ inside: true, section: "section:X", section_name: "X", ward_id: null, ward_name: null }) }));
    render(<LocaleProvider><BookingExperience /></LocaleProvider>);
    fireEvent.click(screen.getByRole("radio", { name: /Hospital or clinic/ }));
    expect(screen.getByText("An officer checks it once. Until then it waits like a home booking.")).toBeInTheDocument();
  });
});

describe("driver's trips from the approved plan", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("shows a tanker's trips and starts a booked delivery by sending the code", async () => {
    const assigned = booking({ status: "ASSIGNED", tanker_id: "T0080", station_id: "ST09", depart: "06:20", arrive: "06:22" });
    const fetchMock = routedFetch({
      "GET /sms/test-mode": () => json({ test_mode: true }),
      "GET /driver/tankers": () => json({ day: "2026-10-07", plan_id: "p", tankers_total: 700, items: [{ tanker_id: "T0080", station_id: "ST09", trips: 2, real_bookings: 1, first_depart: "06:20" }] }),
      "GET /driver/route": () => json({ day: "2026-10-07", plan_id: "p", tanker_id: "T0080", station_id: "ST09", finish: "07:30", km: 5, trips: [
        { n: 1, kind: "booked", name: "KONDAPUR (DIV 15)", depart: "06:20", arrive: "06:22", back: "06:55", km: 2, booking: assigned, stop_id: "bk-BK-20261007-ABC123" },
        { n: 2, kind: "booked", name: "MADHAPUR -2", depart: "07:00", arrive: "07:02", back: "07:30", km: 2, booking: null, stop_id: null },
      ] }),
      "POST /deliveries": () => json({ delivery_id: "d1", otp_issued: false, otp_verified: false, outcome_status: "pending" }),
      "POST /deliveries/*/otp": () => json({ delivery_id: "d1", otp_issued: true, otp_verified: false, outcome_status: "pending" }),
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<LocaleProvider><DriverPlanRoute /></LocaleProvider>);
    expect(await screen.findByText(/1 tankers carry bookings made through JalLekha/)).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText(/My tanker/), { target: { value: "T0080" } });
    expect(await screen.findByText("estimated load, no code needed", { exact: false })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Start delivery and send the code" }));
    await waitFor(() => expect(callsTo(fetchMock, "POST", "/deliveries/*/otp")).toHaveLength(1));
    expect(callsTo(fetchMock, "POST", "/deliveries")[0].body).toMatchObject({ stop_id: "bk-BK-20261007-ABC123", driver_id: "T0080" });
    expect(callsTo(fetchMock, "POST", "/deliveries/*/otp")[0].body).toEqual({ representative_id: "bk-BK-20261007-ABC123-rep" });
    expect(await screen.findByText(/Code sent to the booker's phone \(ends in 77\)/)).toBeInTheDocument();
  });
});
