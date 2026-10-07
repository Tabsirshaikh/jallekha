import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import PlanRoutes from "./PlanRoutes";
import { json, routedFetch } from "./test/apiMock";

const trip = (n: number, depart: string, back: string) => ({ n, kind: "booked", group: "section:KONDAPUR (DIV 15)", name: "KONDAPUR (DIV 15)", booking_id: `KONDAPUR (DIV 15)|2026-10-07|${n}`, lat: 17.46, lng: 78.36, depart, arrive: depart, unloaded: back, back, km: 4, minutes: 10, leg_basis: "OSRM" });
const tanker = { tanker_id: "T0035", station_id: "ST03", trips: [trip(1, "06:20", "07:05"), trip(2, "07:25", "08:02")], km: 8, finish: "08:02", sections_reached: 1 };
const station = { station_id: "ST03", lat: 17.49, lng: 78.5, tankers: 1, tankers_used: 1, capacity_trips: 9, trips: 2, special_trips: 0, km: 8, finish: "08:02", unscheduled: 0 };
const summary = { tankers: 1, fleet: 1150, stations: 1, trips: 2, special_trips: 0, unscheduled: 0, total_km: 8, sections_reached: 1, legs_estimated: 0, latest_finish: "08:02", average_trips_per_tanker: 2 };

describe("officer route map", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("ticks the stops a driver confirmed with the residents' codes (test mode)", async () => {
    vi.stubGlobal("fetch", routedFetch({
      "GET /plans/p/routes": () => (_body, url) => json({ plan_id: "p", day: "2026-10-07", station: url.searchParams.get("station"), summary, stations: [station], tankers: url.searchParams.get("station") ? [tanker] : [], unscheduled: [], unscheduled_total: 0, paths: [], basis: { times: "SIMULATION" } }),
      "GET /driver/visits": () => json({ day: "2026-10-07", plan_id: "p", items: [{ tanker_id: "T0035", n: 1, visited_at: "2026-10-07T01:10:00+00:00" }], basis: "SIMULATION" }),
    }));
    render(<PlanRoutes planId="p" />);
    expect(await screen.findByText("✓ 1 stops confirmed by drivers (test mode)")).toBeInTheDocument();
    fireEvent.click(screen.getAllByRole("button", { name: /ST03/ })[0]);
    const pick = (await screen.findByText("T0035")).closest("button")!;
    expect(pick).toHaveTextContent("✓ 1 confirmed");
    fireEvent.click(pick);
    expect(await screen.findByText("Driver confirmed")).toBeInTheDocument();
    expect(screen.getByText("✓ 01:10 UTC")).toBeInTheDocument();
  });
});
