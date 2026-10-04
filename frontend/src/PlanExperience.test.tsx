import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { setToken } from "./api";
import { AuthProvider } from "./auth";
import { LocaleProvider } from "./i18n";
import PlanExperience from "./PlanExperience";
import { apiError, json, planServer } from "./test/planFixtures";

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
  fireEvent.click(checkPanel().getByRole("button", { name: "Mark section:ADARSHNAGAR checked" }));
  expect(await screen.findByText("1 of 2 checked")).toBeInTheDocument();
  fireEvent.click(checkPanel().getByRole("button", { name: "Mark ward:relation/7852805 checked" }));
  expect(await screen.findByText("2 of 2 checked")).toBeInTheDocument();
}

describe("PlanExperience (live API)", () => {
  beforeEach(() => setToken(null));
  afterEach(() => vi.unstubAllGlobals());

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
    expect(queue.getByText("ward:relation/7848824")).toBeInTheDocument();
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
    expect(server.calls).toContainEqual({ method: "POST", path: "/plans", body: { day: "2025-05-01" } });
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
    await waitFor(() => expect(server.calls).toContainEqual({ method: "POST", path: "/plans", body: { day: "2025-06-01" } }));
    expect(await screen.findByText(outside)).toBeInTheDocument();
  });

  it("checks a flagged group with a reason and updates the progress", async () => {
    setToken("t-officer");
    const server = planServer();
    vi.stubGlobal("fetch", vi.fn().mockImplementation(server.fetchMock));
    renderScreen();
    await openPlan();

    const mark = checkPanel().getByRole("button", { name: "Mark section:ADARSHNAGAR checked" });
    expect(mark).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Check reason (used for each group you mark)"), { target: { value: "  Section placed by hand on the field map " } });
    expect(mark).toBeEnabled();
    fireEvent.click(mark);

    expect(await screen.findByText("1 of 2 checked")).toBeInTheDocument();
    expect(server.calls).toContainEqual({ method: "POST", path: CHECKS + "section%3AADARSHNAGAR/check", body: { officer_id: "off-1", reason: "Section placed by hand on the field map" } });
    expect(checkPanel().queryByRole("button", { name: "Mark section:ADARSHNAGAR checked" })).not.toBeInTheDocument();
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
    const mark = checkPanel().getByRole("button", { name: "Mark section:ADARSHNAGAR checked" });
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
    expect(fetchMock).not.toHaveBeenCalled();
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
});
