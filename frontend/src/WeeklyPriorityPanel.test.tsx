import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { LocaleProvider } from "./i18n";
import WeeklyPriorityPanel from "./WeeklyPriorityPanel";

vi.mock("./auth", () => ({ useAuth: () => ({ status: "signed-in", role: "officer" }) }));
afterEach(() => vi.unstubAllGlobals());

it("keeps missing records unknown and saves explicit officer supply verification", async () => {
  const fetch = vi.fn(async (_url: string, init?: RequestInit) => new Response(JSON.stringify(
    init?.method === "POST" ? { ledger_missing: false } : { items: [{ section_id: "5:ADIKMET", section: "ADIKMET", status: "UNKNOWN", population_estimate: 100, baseline_need_weight: 2, current_need_weight: 2, weekly_requirement_litres: null, confirmed_litres: null, shortfall_litres: null }] }
  ), { headers: { "Content-Type": "application/json" } }));
  vi.stubGlobal("fetch", fetch);
  render(<LocaleProvider><WeeklyPriorityPanel /></LocaleProvider>);
  expect(await screen.findByText("Current shortfall is unknown. Verify supply and complete delivery records first.")).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Alternative water supply"), { target: { value: "unavailable" } });
  fireEvent.change(screen.getByLabelText("Records verified through"), { target: { value: "2026-10-06" } });
  fireEvent.click(screen.getByLabelText("I checked all tanker delivery records for the seven days ending on this date."));
  fireEvent.change(screen.getByLabelText("What did you verify?"), { target: { value: "No piped water; full log checked" } });
  fireEvent.click(screen.getByRole("button", { name: "Save supply check" }));
  expect(await screen.findByText("Supply check saved")).toBeInTheDocument();
  const post = fetch.mock.calls.find(([, init]) => init?.method === "POST");
  expect(JSON.parse(String(post?.[1]?.body))).toMatchObject({ section_id: "5:ADIKMET", tanker_share: 1, records_complete: true });
});

it("shows requirement and confirmed deliveries separately from the Census baseline", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ items: [{ section_id: "5:ADIKMET", section: "ADIKMET", status: "SHORTFALL", population_estimate: 100, baseline_need_weight: 2, current_need_weight: 6, weekly_requirement_litres: 10500, confirmed_litres: 2100, shortfall_litres: 8400, window_start: "2026-09-30", window_end: "2026-10-06" }] }), { headers: { "Content-Type": "application/json" } })));
  render(<LocaleProvider><WeeklyPriorityPanel sectionId="5:ADIKMET" /></LocaleProvider>);
  expect(await screen.findByText("10,500")).toBeInTheDocument();
  expect(screen.getByText("2,100")).toBeInTheDocument();
  expect(screen.getByText("8,400")).toBeInTheDocument();
});
