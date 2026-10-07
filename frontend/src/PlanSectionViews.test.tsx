import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import PlanFacts from "./PlanFacts";
import PlanPriority from "./PlanPriority";
import { PlanOutage, PlanScheduled } from "./PlanSupply";
import { adaptLivePlan } from "./planAdapter";
import { confidenceBody, planBody } from "./test/planFixtures";
import { overviewRaw, stationsRaw } from "./test/sectionOverviewFixture";

function overview() {
  const raw = { ...planBody(), source: "section_month", unit: "section", stations: Object.fromEntries(stationsRaw.map((s) => [s.station, { ...s, booked_trips: 80, lent: 0, borrowed: 0, waiting: [], served_total: 3, waiting_total: 0 }])), overview: overviewRaw };
  const plan = adaptLivePlan(raw, confidenceBody);
  if (!plan?.overview) throw new Error("no overview");
  return plan.overview;
}

describe("plan by section panels", () => {
  it("reads the overview, with each station's queue in served order", () => {
    const o = overview();
    expect(o.facts.bookings).toBe(120);
    expect(o.facts.tiers).toEqual([4, 10, 106]);
    expect(o.sections.find((s) => s.name === "BALANAGAR")?.scheduled?.loads).toBe(9);
    const st01 = o.stations.find((s) => s.station === "ST01")!;
    expect(st01.served.map((b) => b.reason)).toEqual(["TIER_0", "TIER_1", "DRR"]);
    expect(st01.bookings["section:MADHAPUR -2"]).toBe(30);
  });

  it("gives no overview for a malformed answer, so the screen falls back", () => {
    const raw = { ...planBody(), overview: { facts: { bookings: "many" }, sections: [], stations: [] } };
    expect(adaptLivePlan(raw, confidenceBody)?.overview).toBeNull();
  });

  it("explains every figure of the plan in plain words with its source", () => {
    render(<PlanFacts facts={overview().facts} day="2025-05-15" capacity="tight" />);
    const table = within(screen.getByRole("table"));
    expect(table.getByRole("rowheader", { name: "Bookings to serve today" }).closest("tr")).toHaveTextContent("100 new today (each section's real May 2025 total ÷ 31 days) + 20 still waiting");
    expect(table.getByRole("rowheader", { name: "Kept for areas that book too little" }).closest("tr")).toHaveTextContent("3 needed");
    expect(table.getByRole("rowheader", { name: "Bookings served today" }).closest("tr")).toHaveTextContent("67%");
    expect(table.getAllByText("Estimate").length).toBeGreaterThan(0);
  });

  it("shows the three priority steps and plays a station's queue", () => {
    render(<PlanPriority overview={overview()} />);
    expect(screen.getByRole("heading", { name: "Hospitals and care homes" })).toBeInTheDocument();
    expect(screen.getByText("4 hospital or care-home bookings")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "⏸ Pause" }));
    fireEvent.click(screen.getByRole("button", { name: "Next tanker" }));
    expect(screen.getByText(/Tanker/)).toHaveTextContent("Tanker 1 of 3: hospitals and care homes");
  });

  it("says why an area with few bookings gets water, and when no water cut needs any", () => {
    render(<><PlanScheduled overview={overview()} /><PlanOutage overview={overview()} /></>);
    const card = screen.getByRole("heading", { name: "BALANAGAR" }).closest("article")!;
    expect(card).toHaveTextContent("similar sections nearby booked 8.4× more");
    expect(card).toHaveTextContent("45,101litres sent today");
    expect(card).toHaveTextContent("Fully covered");
    expect(screen.getByText(/No water-cut notice covers this day/)).toBeInTheDocument();
  });
});
