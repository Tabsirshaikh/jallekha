import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { setToken } from "./api";
import { AuthProvider } from "./auth";
import { LocaleProvider } from "./i18n";
import PlanExperience from "./PlanExperience";
import { apiError, derivedConfidenceBody, json, planServer, SUPPLIED_ID, WEIGHTED_ID } from "./test/planFixtures";
import { expectNoDataRequests } from "./test/noDataRequests";

const CHECKS = "/plans/replay-2025-05-01/groups/";

function renderScreen() {
  return render(
    <LocaleProvider>
      <AuthProvider>
        <PlanExperience />
      </AuthProvider>
    </LocaleProvider>,
  );
}

async function openPlan() {
  fireEvent.click(await screen.findByRole("button", { name: "Open plan 2025-05-01" }));
  return screen.findByRole("heading", { name: "Flagged groups to check" });
}

function checkPanel() {
  return within(screen.getByRole("region", { name: "Flagged groups to check" }));
}

async function checkBoth(reason = "Compared with the field map") {
  fireEvent.change(screen.getByLabelText("Check reason (used for each group you mark)"), { target: { value: reason } });
  fireEvent.click(checkPanel().getByRole("button", { name: "Mark ADARSHNAGAR checked" }));
  expect(await screen.findByText("1 of 2 checked")).toBeInTheDocument();
  fireEvent.click(checkPanel().getByRole("button", { name: "Mark Ward 76 Serilingampally checked" }));
  expect(await screen.findByText("2 of 2 checked")).toBeInTheDocument();
}

describe("PlanExperience (live API)", () => {
  beforeEach(() => setToken(null));
  afterEach(() => vi.unstubAllGlobals());

  it("says how a calibrated threshold was chosen, and that it rests on assumed error rates", async () => {
    setToken("t-officer");
    vi.stubGlobal("fetch", vi.fn().mockImplementation(planServer({ confidence: derivedConfidenceBody }).fetchMock));
    renderScreen();
    await screen.findByText("Live data");
    await openPlan();
    expect(screen.getByText(/chosen on a simulated replay with deliberately wrong data/)).toBeInTheDocument();
    expect(screen.queryByText(/PROVISIONAL and not calibrated/)).not.toBeInTheDocument();
    expect(screen.getByText("DERIVED · SIMULATION")).toBeInTheDocument();
  });

  it("lists stored plans, opens one and shows queue, schedule, outage and confidence", async () => {
    setToken("t-officer");
    const server = planServer();
    vi.stubGlobal("fetch", vi.fn().mockImplementation(server.fetchMock));
    renderScreen();

    expect(await screen.findByText("Live data")).toBeInTheDocument();
    expect(screen.getByText(/built from the committed A8 replay \(SIMULATION\)/)).toBeInTheDocument();
    expect(screen.getByText("0 of 2 flagged groups checked")).toBeInTheDocument();
    expect(screen.queryByText("Sample Ward A")).not.toBeInTheDocument();

    await openPlan();
    expect(screen.getByText(/PROVISIONAL and not calibrated/)).toBeInTheDocument();
    expect(screen.getByText("0 of 2 checked")).toBeInTheDocument();
    expect(checkPanel().getByText("section:ADARSHNAGAR")).toBeInTheDocument();
    expect(checkPanel().getByText("ward:relation/7852805")).toBeInTheDocument();
    // Trips are the sum over stations; the replay basis is on screen.
    expect(screen.getByText("418")).toBeInTheDocument();
    expect(screen.getAllByText(/SIMULATION/).length).toBeGreaterThan(0);
    // Queue rows carry each group's own confidence state.
    const queue = within(screen.getByRole("region", { name: "Groups in today's queue" }));
    expect(queue.getByText("Ward 105 Gachibowli")).toBeInTheDocument();
    expect(queue.getAllByText("Needs check")).toHaveLength(2);
    expect(queue.getByText("Above threshold")).toBeInTheDocument();
    // Schedule: unavailable litres stay blank, never zero; unrouted wards are named.
    const schedule = within(screen.getByRole("region", { name: "Scheduled supply" }));
    expect(schedule.getByText("relation/7848859").closest(".plan-schedule-row")).toHaveTextContent("—");
    expect(schedule.getByText("Needs a service point")).toBeInTheDocument();
    expect(screen.getByText("Unused outage litres")).toBeInTheDocument();
  });

  it("builds a plan for a replay day and opens it", async () => {
    setToken("t-officer");
    const server = planServer({ plans: false });
    vi.stubGlobal("fetch", vi.fn().mockImplementation(server.fetchMock));
    renderScreen();

    expect(await screen.findByText("No plans are stored yet. Build one for a replay day.")).toBeInTheDocument();
    const day = screen.getByLabelText("Build plan for a day");
    expect(day).toHaveAttribute("min", "2025-03-01");
    expect(day).toHaveAttribute("max", "2025-07-31");
    fireEvent.change(day, { target: { value: "2025-05-01" } });
    fireEvent.click(screen.getByRole("button", { name: "Build plan" }));

    expect(await screen.findByText("Plan for 2025-05-01 built and opened.")).toBeInTheDocument();
    expect(server.calls).toContainEqual({ method: "POST", path: "/plans", body: { day: "2025-05-01", weights: { wad: 2, cad: 1, hardship: 1 } } });
    expect(await screen.findByRole("heading", { name: "Flagged groups to check" })).toBeInTheDocument();
  });

  it("explains a day outside the replay window", async () => {
    setToken("t-officer");
    const server = planServer();
    vi.stubGlobal("fetch", vi.fn().mockImplementation(server.fetchMock));
    renderScreen();

    const outside = "That day is outside the replay window (2025-03-01 to 2025-07-31).";
    // Outside the input's range: refused before asking the server.
    fireEvent.change(await screen.findByLabelText("Build plan for a day"), { target: { value: "2025-08-15" } });
    fireEvent.click(screen.getByRole("button", { name: "Build plan" }));
    expect(await screen.findByText(outside)).toBeInTheDocument();
    expect(server.calls.some((call) => call.method === "POST")).toBe(false);

    // The server's 404 (no replay data for the day) gives the same message.
    fireEvent.change(screen.getByLabelText("Build plan for a day"), { target: { value: "2025-06-01" } });
    fireEvent.click(screen.getByRole("button", { name: "Build plan" }));
    await waitFor(() => expect(server.calls).toContainEqual({ method: "POST", path: "/plans", body: { day: "2025-06-01", weights: { wad: 2, cad: 1, hardship: 1 } } }));
    expect(await screen.findByText(outside)).toBeInTheDocument();
  });

  it("checks a flagged group with a reason and updates the progress", async () => {
    setToken("t-officer");
    const server = planServer();
    vi.stubGlobal("fetch", vi.fn().mockImplementation(server.fetchMock));
    renderScreen();
    await openPlan();

    const mark = checkPanel().getByRole("button", { name: "Mark ADARSHNAGAR checked" });
    expect(mark).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Check reason (used for each group you mark)"), { target: { value: "  Section placed by hand on the field map " } });
    expect(mark).toBeEnabled();
    fireEvent.click(mark);

    expect(await screen.findByText("1 of 2 checked")).toBeInTheDocument();
    expect(server.calls).toContainEqual({ method: "POST", path: CHECKS + "section%3AADARSHNAGAR/check", body: { officer_id: "off-1", reason: "Section placed by hand on the field map" } });
    expect(checkPanel().queryByRole("button", { name: "Mark ADARSHNAGAR checked" })).not.toBeInTheDocument();
    expect(await screen.findByText("1 of 2 flagged groups checked")).toBeInTheDocument();
  });

  it("keeps approval disabled until every flag is checked, then approves with officer id and reason", async () => {
    setToken("t-officer");
    const server = planServer();
    vi.stubGlobal("fetch", vi.fn().mockImplementation(server.fetchMock));
    renderScreen();
    await openPlan();

    const approve = screen.getByRole("button", { name: "Approve plan" });
    fireEvent.change(screen.getByLabelText("Officer approval reason"), { target: { value: "Queue matches the replay day" } });
    expect(approve).toBeDisabled();
    expect(screen.getByText("Check all flagged groups first (0 of 2 checked).")).toBeInTheDocument();

    await checkBoth();
    await waitFor(() => expect(approve).toBeEnabled());
    fireEvent.click(approve);

    expect(await screen.findByText("Plan approved by off-1")).toBeInTheDocument();
    expect(server.calls).toContainEqual({ method: "POST", path: "/plans/replay-2025-05-01/approve", body: { officer_id: "off-1", reason: "Queue matches the replay day" } });
  });

  it("requires an approval reason", async () => {
    setToken("t-officer");
    vi.stubGlobal("fetch", vi.fn().mockImplementation(planServer().fetchMock));
    renderScreen();
    await openPlan();
    await checkBoth();
    expect(screen.getByRole("button", { name: "Approve plan" })).toBeDisabled();
    expect(screen.getByText("Enter a reason to approve.")).toBeInTheDocument();
  });

  it("shows the server's message when it still refuses approval", async () => {
    setToken("t-officer");
    const server = planServer({ approve: () => apiError(409, "conflict", "Plan replay-2025-05-01 is already approved") });
    vi.stubGlobal("fetch", vi.fn().mockImplementation(server.fetchMock));
    renderScreen();
    await openPlan();
    await checkBoth();
    fireEvent.change(screen.getByLabelText("Officer approval reason"), { target: { value: "Reviewed" } });
    fireEvent.click(screen.getByRole("button", { name: "Approve plan" }));
    expect(await screen.findByText(/Plan replay-2025-05-01 is already approved/)).toBeInTheDocument();
  });

  it("asks for an officer id when the token has none", async () => {
    setToken("t-dev");
    const server = planServer({ userId: null });
    vi.stubGlobal("fetch", vi.fn().mockImplementation(server.fetchMock));
    renderScreen();
    await openPlan();

    const officer = screen.getByLabelText("Officer id");
    expect(officer).toBeRequired();
    fireEvent.change(screen.getByLabelText("Check reason (used for each group you mark)"), { target: { value: "Checked" } });
    const mark = checkPanel().getByRole("button", { name: "Mark ADARSHNAGAR checked" });
    expect(mark).toBeDisabled();
    fireEvent.change(officer, { target: { value: "off-9" } });
    expect(mark).toBeEnabled();
    fireEvent.click(mark);
    await screen.findByText("1 of 2 checked");
    expect(server.calls).toContainEqual({ method: "POST", path: CHECKS + "section%3AADARSHNAGAR/check", body: { officer_id: "off-9", reason: "Checked" } });
  });
});

describe("PlanExperience (sample fallback)", () => {
  beforeEach(() => setToken(null));
  afterEach(() => vi.unstubAllGlobals());

  it("does not call the API when signed out and shows the sample plan", () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    renderScreen();
    expectNoDataRequests(fetchMock);
    expect(screen.getByText("Saved snapshot")).toBeInTheDocument();
    expect(screen.getByText("Sign in with an officer token to see live plans. Showing the sample plan.")).toBeInTheDocument();
    expect(screen.getAllByText("Sample Ward A").length).toBeGreaterThan(0);
    expect(screen.getByRole("button", { name: "Approve demo plan" })).toBeDisabled();
  });

  it("asks for sign-in after a 401", async () => {
    setToken("t-expired");
    vi.stubGlobal("fetch", vi.fn().mockImplementation(() => Promise.resolve(apiError(401, "unauthorized", "A bearer token is required"))));
    renderScreen();
    expect(await screen.findByText("Sign in with an officer token to see live plans. Showing the sample plan.")).toBeInTheDocument();
    expect(screen.getByText("Saved snapshot")).toBeInTheDocument();
    expect(screen.getAllByText("Sample Ward A").length).toBeGreaterThan(0);
  });

  it("says the server could not be reached", async () => {
    setToken("t-officer");
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
    renderScreen();
    expect(await screen.findByText("The server could not be reached. Showing the sample plan.")).toBeInTheDocument();
    expect(screen.getByText("Saved snapshot")).toBeInTheDocument();
    expect(screen.getAllByText("Sample Ward A").length).toBeGreaterThan(0);
  });

  it("says when the account may not open officer plans", async () => {
    setToken("t-driver");
    vi.stubGlobal("fetch", vi.fn().mockImplementation((url: string) => Promise.resolve(url.endsWith("/auth/me") ? json({ role: "driver", user_id: "drv-1" }) : apiError(403, "forbidden", "Role driver may not call this endpoint"))));
    renderScreen();
    expect(await screen.findByText("This account cannot open officer plans. Showing the sample plan.")).toBeInTheDocument();
    expect(screen.getAllByText("Sample Ward A").length).toBeGreaterThan(0);
  });

  it("shows ward and section names, and the id only where no name is known", async () => {
    setToken("t-officer");
    vi.stubGlobal("fetch", vi.fn().mockImplementation(planServer().fetchMock));
    renderScreen();
    await openPlan();
    expect(screen.getAllByText("Ward 105 Gachibowli").length).toBeGreaterThan(0);
    expect(checkPanel().getByRole("button", { name: "Mark ADARSHNAGAR checked" })).toBeInTheDocument();
    expect(checkPanel().getByRole("button", { name: "Mark Ward 76 Serilingampally checked" })).toBeInTheDocument();
  });

  it("offers the three need weights at their defaults and sends the chosen ones", async () => {
    setToken("t-officer");
    const server = planServer();
    vi.stubGlobal("fetch", vi.fn().mockImplementation(server.fetchMock));
    renderScreen();
    await screen.findByRole("button", { name: "Open plan 2025-05-01" });
    const wad = screen.getByLabelText("Water access") as HTMLInputElement;
    const cad = screen.getByLabelText("Phone access") as HTMLInputElement;
    const hardship = screen.getByLabelText("Hardship") as HTMLInputElement;
    expect([wad.value, cad.value, hardship.value]).toEqual(["2", "1", "1"]);
    expect(screen.getByText(/can move only a few trips/i)).toBeInTheDocument();
    fireEvent.change(wad, { target: { value: "5" } });
    fireEvent.change(cad, { target: { value: "0" } });
    fireEvent.change(hardship, { target: { value: "0" } });
    fireEvent.change(screen.getByLabelText("Build plan for a day"), { target: { value: "2025-05-01" } });
    fireEvent.click(screen.getByRole("button", { name: "Build plan" }));
    await screen.findByRole("heading", { name: "Flagged groups to check" });
    const build = server.calls.find((c) => c.method === "POST" && c.path === "/plans");
    expect(build?.body).toEqual({ day: "2025-05-01", weights: { wad: 5, cad: 0, hardship: 0 } });
  });

  it("resets the weights to the defaults", async () => {
    setToken("t-officer");
    vi.stubGlobal("fetch", vi.fn().mockImplementation(planServer().fetchMock));
    renderScreen();
    await screen.findByRole("button", { name: "Open plan 2025-05-01" });
    const wad = screen.getByLabelText("Water access") as HTMLInputElement;
    fireEvent.change(wad, { target: { value: "4.5" } });
    expect(wad.value).toBe("4.5");
    fireEvent.click(screen.getByRole("button", { name: "Reset weights" }));
    expect(wad.value).toBe("2");
  });

  it("labels a weighted plan in the list and shows who gains and who loses when it is open", async () => {
    setToken("t-officer");
    const server = planServer();
    vi.stubGlobal("fetch", vi.fn().mockImplementation(server.fetchMock));
    renderScreen();
    await screen.findByRole("button", { name: "Open plan 2025-05-01" });
    fireEvent.change(screen.getByLabelText("Water access"), { target: { value: "5" } });
    fireEvent.change(screen.getByLabelText("Phone access"), { target: { value: "0" } });
    fireEvent.change(screen.getByLabelText("Hardship"), { target: { value: "0" } });
    fireEvent.change(screen.getByLabelText("Build plan for a day"), { target: { value: "2025-05-01" } });
    fireEvent.click(screen.getByRole("button", { name: "Build plan" }));
    const panel = await screen.findByRole("region", { name: "Who gains and who loses" });
    expect(await within(panel).findByText("Ward 105 Gachibowli")).toBeInTheDocument();
    expect(within(panel).getByText("+8")).toBeInTheDocument();
    expect(within(panel).getByText("ward:relation/7852805")).toBeInTheDocument(); // no name known
    expect(within(panel).getByText("\u22128")).toBeInTheDocument();
    expect(within(panel).getByText(/SIMULATION/)).toBeInTheDocument();
    expect(screen.getByText("Weights 5 / 0 / 0")).toBeInTheDocument();
    expect(server.calls.some((c) => c.path === `/plans/${WEIGHTED_ID}/compare`)).toBe(true);
  });

  it("shows no comparison for a default plan", async () => {
    setToken("t-officer");
    vi.stubGlobal("fetch", vi.fn().mockImplementation(planServer().fetchMock));
    renderScreen();
    await openPlan();
    expect(screen.queryByRole("region", { name: "Who gains and who loses" })).not.toBeInTheDocument();
  });

  it("says so when the comparison cannot load, and still shows the plan", async () => {
    setToken("t-officer");
    const failing = planServer({ compare: apiError(500, "internal_error", "boom") });
    vi.stubGlobal("fetch", vi.fn().mockImplementation(failing.fetchMock));
    renderScreen();
    await screen.findByRole("button", { name: "Open plan 2025-05-01" });
    fireEvent.change(screen.getByLabelText("Water access"), { target: { value: "5" } });
    fireEvent.change(screen.getByLabelText("Build plan for a day"), { target: { value: "2025-05-01" } });
    fireEvent.click(screen.getByRole("button", { name: "Build plan" }));
    expect(await screen.findByText("The comparison could not be loaded.")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Flagged groups to check" })).toBeInTheDocument();
  });

  describe("plans from supplied bookings", () => {
    const CSV = "booking_id,section,arrived_at\nB-1,ADARSHNAGAR,2026-10-03T05:30:00+05:30\nB-2,BAHADURPURA,2026-10-03T06:00:00+05:30\n";

    async function paste(csv: string, day = "2026-10-03") {
      await screen.findByRole("button", { name: "Open plan 2025-05-01" });
      fireEvent.change(screen.getByLabelText("Day of these bookings"), { target: { value: day } });
      fireEvent.change(screen.getByLabelText("Bookings (CSV)"), { target: { value: csv } });
      fireEvent.click(screen.getByRole("button", { name: "Build plan from bookings" }));
    }

    it("builds a plan from pasted bookings and says where it came from", async () => {
      setToken("t-officer");
      const server = planServer();
      vi.stubGlobal("fetch", vi.fn().mockImplementation(server.fetchMock));
      renderScreen();
      await paste(CSV);
      expect(await screen.findByRole("heading", { name: "Flagged groups to check" })).toBeInTheDocument();
      const post = server.calls.find((c) => c.method === "POST" && c.path === "/plans");
      expect(post?.body).toEqual({
        day: "2026-10-03",
        weights: { wad: 2, cad: 1, hardship: 1 },
        bookings: [
          { booking_id: "B-1", section: "ADARSHNAGAR", arrived_at: "2026-10-03T05:30:00+05:30" },
          { booking_id: "B-2", section: "BAHADURPURA", arrived_at: "2026-10-03T06:00:00+05:30" },
        ],
      });
      expect(await screen.findByText("Built from 2 bookings supplied for 2026-10-03, not the replay. The bookings are as supplied (not verified here); capacity is an ASSUMED fleet scenario.")).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "Open plan 2026-10-03 built from supplied bookings" })).toBeInTheDocument();
      expect(server.calls.some((c) => c.path === `/plans/${SUPPLIED_ID}`)).toBe(true);
    });

    it("shows a problem in the CSV with its line and does not call the server", async () => {
      setToken("t-officer");
      const server = planServer();
      vi.stubGlobal("fetch", vi.fn().mockImplementation(server.fetchMock));
      renderScreen();
      await paste("booking_id,section,arrived_at\nB-1,ADARSHNAGAR,2026-10-03T05:30:00+05:30\nB-2,BAHADURPURA\n");
      expect(await screen.findByText("Line 3: expected 3 values but found 2.")).toBeInTheDocument();
      expect(server.calls.some((c) => c.method === "POST")).toBe(false);
    });

    it("shows the server's list of problems", async () => {
      setToken("t-officer");
      vi.stubGlobal("fetch", vi.fn().mockImplementation(planServer().fetchMock));
      renderScreen();
      await paste("booking_id,section,arrived_at\nB-1,BAD,2026-10-03T05:30:00+05:30\n");
      expect(await screen.findByText(/booking 1: section is not an HMWSSB section/)).toBeInTheDocument();
    });

    it("asks for at least one booking and for a day", async () => {
      setToken("t-officer");
      const server = planServer();
      vi.stubGlobal("fetch", vi.fn().mockImplementation(server.fetchMock));
      renderScreen();
      await screen.findByRole("button", { name: "Open plan 2025-05-01" });
      fireEvent.click(screen.getByRole("button", { name: "Build plan from bookings" }));
      expect(await screen.findByText("Choose the day of the bookings and paste at least one booking.")).toBeInTheDocument();
      expect(server.calls.some((c) => c.method === "POST")).toBe(false);
    });
  });
});
