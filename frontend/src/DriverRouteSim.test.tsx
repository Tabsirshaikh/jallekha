import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import DriverRouteSim, { type SimTrip } from "./DriverRouteSim";
import { spotAt } from "./routePlay";

const station = { station_id: "ST09", lat: 17.45, lng: 78.38 };
const trip = (n: number, over: Partial<SimTrip>): SimTrip => ({
  n, kind: "booked", name: `KONDAPUR (DIV 15)`, group: "section:KONDAPUR (DIV 15)", lat: 17.46, lng: 78.36,
  depart: "06:20", arrive: "06:30", unloaded: "07:00", back: "07:10", km: 4, booked: false, done: false, ...over,
});
const trips = [trip(1, {}), trip(2, { name: "MADHAPUR -2", group: "section:MADHAPUR -2", lat: 17.45, lng: 78.39, depart: "07:30", arrive: "07:40", unloaded: "08:10", back: "08:20" })];

describe("the tanker's position through the day", () => {
  it("fills at the station, drives out, empties the tank, drives back, and fills again", () => {
    const legs = [{ x: 100, y: 0, dep: 380, arr: 390, unl: 420, back: 430, kind: 0 }, { x: 0, y: 100, dep: 450, arr: 460, unl: 490, back: 500, kind: 0 }];
    const home: [number, number] = [0, 0];
    expect(spotAt(legs, home, 350)).toBeNull(); // before the first fill
    expect(spotAt(legs, home, 370)).toMatchObject({ state: "fill", x: 0, y: 0, i: 0 });
    expect(spotAt(legs, home, 385)).toMatchObject({ state: "out", x: 50, i: 0 });
    expect(spotAt(legs, home, 400)).toMatchObject({ state: "unload", x: 100, i: 0 });
    expect(spotAt(legs, home, 425)).toMatchObject({ state: "back", x: 50, i: 0 });
    expect(spotAt(legs, home, 440)).toMatchObject({ state: "fill", x: 0, y: 0, i: 1 }); // back to fill for stop 2
    expect(spotAt(legs, home, 455)).toMatchObject({ state: "out", y: 50, i: 1 });
    expect(spotAt(legs, home, 510)).toBeNull(); // the day is done
  });
});

describe("driver route simulation", () => {
  it("plays the plan's day on the map: station, stop, back to the station, next stop", () => {
    const choose = vi.fn();
    render(<DriverRouteSim station={station} trips={trips} current={1} onChoose={choose} />);
    expect(screen.getByText("Filling station ST09")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Stop 1: KONDAPUR (DIV 15)" })).toBeInTheDocument();
    // the day, step by step, with the return to the filling station between stops
    const steps = screen.getByRole("list", { name: "My day, step by step" });
    expect(steps).toHaveTextContent("06:00Fill the tank at filling station ST09");
    expect(steps).toHaveTextContent("07:00Drive back to filling station ST09 to fill again");
    expect(steps).toHaveTextContent("07:10Fill the tank at filling station ST09");
    expect(steps).toHaveTextContent("08:10Drive back to filling station ST09 (day done)");
    const time = screen.getByRole("slider", { name: "Time of day" });
    fireEvent.change(time, { target: { value: String(6 * 60 + 10) } });
    expect(screen.getAllByText("Filling the tank at station ST09 for stop 1").length).toBeGreaterThan(0);
    fireEvent.change(time, { target: { value: String(6 * 60 + 25) } });
    expect(screen.getAllByText("Driving to stop 1: KONDAPUR (DIV 15)").length).toBeGreaterThan(0);
    fireEvent.change(time, { target: { value: String(6 * 60 + 45) } });
    expect(screen.getAllByText("Emptying the tank at stop 1").length).toBeGreaterThan(0);
    fireEvent.change(time, { target: { value: String(7 * 60 + 5) } });
    expect(screen.getAllByText("Driving back to station ST09 to fill again").length).toBeGreaterThan(0);
    fireEvent.change(time, { target: { value: String(7 * 60 + 35) } });
    expect(screen.getAllByText("Driving to stop 2: MADHAPUR -2").length).toBeGreaterThan(0);
    // clicking a stop jumps to its trip
    fireEvent.click(screen.getByRole("button", { name: "Stop 2: MADHAPUR -2" }));
    expect(choose).toHaveBeenCalledWith(2);
  });

  it("ticks a stop the residents confirmed", () => {
    render(<DriverRouteSim station={station} trips={[{ ...trips[0], done: true }, trips[1]]} current={2} onChoose={() => {}} />);
    expect(screen.getByRole("button", { name: "Stop 1: KONDAPUR (DIV 15)" })).toHaveTextContent("✓");
    expect(screen.getByText(/1 of 2 stops confirmed/)).toBeInTheDocument();
  });
});
