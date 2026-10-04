import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { setToken } from "./api";
import { AuthProvider } from "./auth";
import ExplainExperience from "./ExplainExperience";
import { LocaleProvider } from "./i18n";
import { jsonResponse } from "./test/apiFixtures";
import { BOOKING_ID, bookingResponse, contestItem, contestReply, noCensusWard, wardResponse } from "./test/explainFixtures";

const SAMPLE = /DEMO-BK-105/;

function renderScreen() {
  return render(
    <LocaleProvider>
      <AuthProvider>
        <ExplainExperience />
      </AuthProvider>
    </LocaleProvider>,
  );
}

type Stored = ReturnType<typeof contestItem> & { reply: ReturnType<typeof contestReply> | null };
type Call = { method: string; path: string; search: URLSearchParams; body: unknown };

/** A small in-memory T10: explain routes, contests and replies, with the caller's role and user id. */
function fakeApi({ role, userId, contests = [], replyStatus }: { role: string; userId: string | null; contests?: Stored[]; replyStatus?: number }) {
  const store: Stored[] = [...contests];
  const calls: Call[] = [];
  const fetchMock = vi.fn((input: string, init?: RequestInit) => {
    const url = new URL(input, "http://localhost");
    const path = decodeURIComponent(url.pathname);
    const method = init?.method ?? "GET";
    const body = init?.body ? JSON.parse(String(init.body)) : undefined;
    calls.push({ method, path, search: url.searchParams, body });
    const ok = (value: unknown) => Promise.resolve(jsonResponse(value));
    const fail = (status: number, code: string, message: string) => Promise.resolve(jsonResponse({ error: { code, message, details: null } }, status));
    if (path === "/auth/me") return ok({ role, user_id: userId });
    if (path === "/explain/wards/relation/7848799") return ok(wardResponse());
    if (path === "/explain/wards/relation/7853000") return ok(noCensusWard());
    if (path === `/explain/bookings/${BOOKING_ID}`) return ok(bookingResponse());
    if (path.startsWith("/explain/")) return fail(404, "not_found", "not found");
    if (path === "/contests" && method === "POST") {
      const item: Stored = { ...contestItem({ contest_id: `c-${store.length + 1}`, filed_by: userId, role, target_type: body.target_type, target_id: body.target_id, reason_code: body.reason_code, reason_text: body.reason_text, status: "open" }), reply: null };
      store.unshift(item);
      return ok({ status: "filed", contest_id: item.contest_id, reply_id: null, ledger_seq: 7, error: null });
    }
    if (path === "/contests") {
      if (role !== "officer" && userId === null) return fail(403, "forbidden", "This token is not bound to a user id, so it has no own contests");
      const status = url.searchParams.get("status");
      const items = store.filter((c) => (role === "officer" || c.filed_by === userId) && (!status || c.status === status));
      return ok({ total: items.length, offset: 0, limit: 50, items: items.map((c) => { const copy: Record<string, unknown> = { ...c }; delete copy.reply; return copy; }) });
    }
    const reply = path.match(/^\/contests\/([^/]+)\/reply$/);
    if (reply && method === "POST") {
      if (replyStatus === 409) return fail(409, "conflict", "This contest already has a reply");
      const item = store.find((c) => c.contest_id === reply[1]);
      if (!item) return fail(404, "not_found", "No such contest");
      item.status = "replied";
      item.reply = { ...contestReply(), officer_id: body.officer_id, outcome_code: body.outcome_code, reason_text: body.reason_text };
      return ok({ status: "replied", contest_id: item.contest_id, reply_id: "r-9", ledger_seq: 8, error: null });
    }
    const detail = path.match(/^\/contests\/([^/]+)$/);
    if (detail) {
      const item = store.find((c) => c.contest_id === detail[1]);
      return item ? ok(item) : fail(404, "not_found", "Contest not found");
    }
    return fail(404, "not_found", "no route");
  });
  return { fetchMock, store, calls };
}

function lookUp(type: "ward" | "booking", id: string) {
  fireEvent.change(screen.getByRole("combobox", { name: "What to explain" }), { target: { value: type } });
  fireEvent.change(screen.getByRole("textbox", { name: "Ward or booking id" }), { target: { value: id } });
  fireEvent.click(screen.getByRole("button", { name: "Show explanation" }));
}

const contestCalls = (calls: Call[]) => calls.filter((call) => call.path.startsWith("/contests"));

describe("ExplainExperience (live)", () => {
  beforeEach(() => { setToken(null); localStorage.clear(); });
  afterEach(() => vi.unstubAllGlobals());

  it("shows a live ward explanation with its values and bases", async () => {
    setToken("tok-res");
    vi.stubGlobal("fetch", fakeApi({ role: "resident", userId: "res-1" }).fetchMock);
    renderScreen();
    expect(await screen.findByText("Live data")).toBeInTheDocument();
    expect(screen.queryByText(SAMPLE)).not.toBeInTheDocument();
    lookUp("ward", "relation/7848799");
    const panel = await screen.findByRole("region", { name: "Ward 91 Khairatabad" });
    expect(within(panel).getByText("12,959")).toBeInTheDocument();
    expect(within(panel).getByText("Need weight")).toBeInTheDocument();
    expect(within(panel).getByText("Census 2011 / historical 2016 geography")).toBeInTheDocument();
    expect(within(panel).getAllByText(/DERIVED/).length).toBeGreaterThan(0);
  });

  it("shows no number for a ward without Census data", async () => {
    setToken("tok-res");
    vi.stubGlobal("fetch", fakeApi({ role: "resident", userId: "res-1" }).fetchMock);
    renderScreen();
    await screen.findByText("Live data");
    lookUp("ward", "relation/7853000");
    const panel = await screen.findByRole("region", { name: "Ward 150 Sample" });
    expect(within(panel).getByText(/no usable Census data/)).toBeInTheDocument();
    expect(within(panel).queryByText("Need weight")).not.toBeInTheDocument();
  });

  it("shows a live booking explanation and the counterfactual in plain words", async () => {
    setToken("tok-res");
    vi.stubGlobal("fetch", fakeApi({ role: "resident", userId: "res-1" }).fetchMock);
    renderScreen();
    await screen.findByText("Live data");
    lookUp("booking", BOOKING_ID);
    const panel = await screen.findByRole("region", { name: BOOKING_ID });
    expect(within(panel).getByText("387")).toBeInTheDocument();
    expect(within(panel).getByText("386")).toBeInTheDocument();
    expect(within(panel).getByText("What would have to change")).toBeInTheDocument();
    expect(within(panel).getByText("If its priority tier were 1 instead of 2, it would move from place 387 to place 1.")).toBeInTheDocument();
    expect(within(panel).getByText("If it had been booked 15 minutes earlier, it would move from place 387 to place 384.")).toBeInTheDocument();
    expect(within(panel).getByText("If its group's entitlement were 140% higher, it would move from place 387 to place 385.")).toBeInTheDocument();
    expect(within(panel).getByText("Water debt is not an input to today's queue order.")).toBeInTheDocument();
  });

  it("says plainly when a booking is not in the stored plans", async () => {
    setToken("tok-res");
    vi.stubGlobal("fetch", fakeApi({ role: "resident", userId: "res-1" }).fetchMock);
    renderScreen();
    await screen.findByText("Live data");
    lookUp("booking", "nope");
    expect(await screen.findByText("No booking with this id in the stored plans.")).toBeInTheDocument();
  });

  it("lets a resident file a contest, then shows it waiting and later with the officer's reply", async () => {
    setToken("tok-res");
    const api = fakeApi({ role: "resident", userId: "res-1" });
    vi.stubGlobal("fetch", api.fetchMock);
    renderScreen();
    await screen.findByText("Live data");
    expect(await screen.findByText("No contests yet.")).toBeInTheDocument();
    lookUp("ward", "relation/7848799");
    await screen.findByRole("region", { name: "Ward 91 Khairatabad" });
    const send = screen.getByRole("button", { name: "Send contest" });
    expect(send).toBeDisabled();
    fireEvent.change(screen.getByRole("combobox", { name: "Reason" }), { target: { value: "ranking_wrong" } });
    fireEvent.change(screen.getByRole("textbox", { name: "What should the officer check?" }), { target: { value: "Please check our lane" } });
    fireEvent.click(send);
    expect(await screen.findByText(/Contest sent/)).toBeInTheDocument();
    const post = api.calls.find((call) => call.method === "POST" && call.path === "/contests");
    expect(post?.body).toEqual({ target_type: "ward", target_id: "relation/7848799", reason_code: "ranking_wrong", reason_text: "Please check our lane" });
    const list = await screen.findByRole("list", { name: "Your contests" });
    await waitFor(() => expect(within(list).getAllByRole("listitem")).toHaveLength(1));
    const item = within(list).getAllByRole("listitem")[0];
    expect(item).toHaveTextContent("Please check our lane");
    expect(item).toHaveTextContent("Queue ranking seems wrong");
    expect(item).toHaveTextContent("Waiting for officer reply");

    // The officer replies elsewhere; the resident refreshes and sees the reply.
    Object.assign(api.store[0], { status: "replied", reply: contestReply() });
    fireEvent.click(screen.getByRole("button", { name: "Refresh" }));
    await waitFor(() => expect(screen.getByRole("list", { name: "Your contests" })).toHaveTextContent("Field check booked for next week."));
    expect(screen.getByRole("list", { name: "Your contests" })).toHaveTextContent("Referred for review");
  });

  it("tells an officer that only residents and councillors file contests", async () => {
    setToken("tok-off");
    vi.stubGlobal("fetch", fakeApi({ role: "officer", userId: "off-1" }).fetchMock);
    renderScreen();
    await screen.findByText("Live data");
    lookUp("ward", "relation/7848799");
    await screen.findByRole("region", { name: "Ward 91 Khairatabad" });
    expect(screen.getByText("Only residents and councillors can file a contest.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Send contest" })).not.toBeInTheDocument();
  });

  it("lets the officer list, filter, open and reply with a required reason", async () => {
    setToken("tok-off");
    const api = fakeApi({
      role: "officer", userId: "off-1",
      contests: [
        { ...contestItem({ contest_id: "c-open", reason_text: "Lane has no tap" }), reply: null },
        { ...contestItem({ contest_id: "c-done", status: "replied", reason_text: "Old complaint" }), reply: contestReply() },
      ],
    });
    vi.stubGlobal("fetch", api.fetchMock);
    renderScreen();
    const list = await screen.findByRole("list", { name: "Contests" });
    await waitFor(() => expect(within(list).getAllByRole("listitem")).toHaveLength(2));
    fireEvent.click(screen.getByRole("button", { name: "Open" }));
    await waitFor(() => expect(within(screen.getByRole("list", { name: "Contests" })).getAllByRole("listitem")).toHaveLength(1));
    expect(api.calls.some((call) => call.path === "/contests" && call.search.get("status") === "open")).toBe(true);
    expect(screen.getByRole("list", { name: "Contests" })).toHaveTextContent("Lane has no tap");
    fireEvent.click(screen.getByRole("button", { name: "Review c-open" }));
    const send = await screen.findByRole("button", { name: "Send reply" });
    expect(send).toBeDisabled();
    fireEvent.change(screen.getByRole("combobox", { name: "Outcome" }), { target: { value: "ranking_stands" } });
    fireEvent.change(screen.getByRole("textbox", { name: "Reason for this decision" }), { target: { value: "Census figures checked; ranking is right." } });
    expect(send).toBeEnabled();
    fireEvent.click(send);
    expect(await screen.findByText(/Reply sent/)).toBeInTheDocument();
    const post = api.calls.find((call) => call.method === "POST" && call.path === "/contests/c-open/reply");
    expect(post?.body).toEqual({ officer_id: "off-1", outcome_code: "ranking_stands", reason_text: "Census figures checked; ranking is right." });
    // Refreshed from the API: the open filter no longer lists it; All shows it with the reply.
    fireEvent.click(screen.getByRole("button", { name: "Replied" }));
    await waitFor(() => expect(screen.getByRole("list", { name: "Contests" })).toHaveTextContent("Lane has no tap"));
  });

  it("shows the officer a plain message when the contest already has a reply (409)", async () => {
    setToken("tok-off");
    const api = fakeApi({ role: "officer", userId: "off-1", contests: [{ ...contestItem({ contest_id: "c-open" }), reply: null }], replyStatus: 409 });
    vi.stubGlobal("fetch", api.fetchMock);
    renderScreen();
    fireEvent.click(await screen.findByRole("button", { name: "Review c-open" }));
    fireEvent.change(await screen.findByRole("textbox", { name: "Reason for this decision" }), { target: { value: "Checked." } });
    fireEvent.click(screen.getByRole("button", { name: "Send reply" }));
    expect(await screen.findByText(/This contest already has a reply/)).toBeInTheDocument();
  });

  it("says the sign-in is not linked to a person when the contest list answers 403", async () => {
    setToken("tok-anon");
    vi.stubGlobal("fetch", fakeApi({ role: "resident", userId: null }).fetchMock);
    renderScreen();
    expect(await screen.findByText(/This sign-in is not linked to a person/)).toBeInTheDocument();
    expect(screen.getByText("Live data")).toBeInTheDocument();
    expect(screen.queryByText(SAMPLE)).not.toBeInTheDocument();
  });
});

describe("ExplainExperience (sample fallback)", () => {
  beforeEach(() => { setToken(null); localStorage.clear(); });
  afterEach(() => vi.unstubAllGlobals());

  it("keeps the sample and browser-only contests when nobody is signed in", async () => {
    const api = fakeApi({ role: "resident", userId: "res-1" });
    vi.stubGlobal("fetch", api.fetchMock);
    renderScreen();
    expect(screen.getByText("Saved snapshot")).toBeInTheDocument();
    expect(screen.getByText(/Sign in as an officer, resident or councillor/)).toBeInTheDocument();
    expect(screen.getAllByText(SAMPLE).length).toBeGreaterThan(0);
    fireEvent.change(screen.getByRole("textbox", { name: "What should the officer check?" }), { target: { value: "Sample check" } });
    fireEvent.click(screen.getByRole("button", { name: "File sample contest" }));
    expect(await screen.findByText("Not sent to the server")).toBeInTheDocument();
    expect(localStorage.getItem("jallekha-u8-contests")).toContain("Sample check");
    expect(api.fetchMock).not.toHaveBeenCalled();
  });

  it("falls back when the sign-in is rejected (401) and never calls the contest routes", async () => {
    setToken("tok-bad");
    const fetchMock = vi.fn<(input: string) => Promise<Response>>(() => Promise.resolve(jsonResponse({ error: { code: "unauthorized", message: "Unknown token" } }, 401)));
    vi.stubGlobal("fetch", fetchMock);
    renderScreen();
    expect(await screen.findByText(/Your sign-in was not accepted/)).toBeInTheDocument();
    expect(screen.getByText("Saved snapshot")).toBeInTheDocument();
    expect(screen.getAllByText(SAMPLE).length).toBeGreaterThan(0);
    expect(fetchMock.mock.calls.every(([input]) => !String(input).includes("/contests"))).toBe(true);
  });

  it("falls back when the server cannot be reached and never calls the contest routes", async () => {
    setToken("tok-res");
    const fetchMock = vi.fn().mockRejectedValue(new TypeError("Failed to fetch"));
    vi.stubGlobal("fetch", fetchMock);
    renderScreen();
    expect(await screen.findByText(/server could not be reached/)).toBeInTheDocument();
    expect(screen.getByText("Saved snapshot")).toBeInTheDocument();
    expect(screen.getAllByText(SAMPLE).length).toBeGreaterThan(0);
    expect(fetchMock.mock.calls.every(([input]) => !String(input).includes("/contests"))).toBe(true);
  });

  it("falls back for a role that cannot read explanations", async () => {
    setToken("tok-drv");
    const api = fakeApi({ role: "driver", userId: "drv-1" });
    vi.stubGlobal("fetch", api.fetchMock);
    renderScreen();
    expect(await screen.findByText(/for officers, residents and councillors/)).toBeInTheDocument();
    expect(contestCalls(api.calls)).toHaveLength(0);
  });

  it("falls back when the contest list returns a server error", async () => {
    setToken("tok-res");
    vi.stubGlobal("fetch", vi.fn((input: string) => Promise.resolve(input.endsWith("/auth/me") ? jsonResponse({ role: "resident", user_id: "res-1" }) : jsonResponse({ error: { code: "internal_error", message: "boom" } }, 500))));
    renderScreen();
    expect(await screen.findByText(/The server returned an error/)).toBeInTheDocument();
    expect(screen.getByText("Saved snapshot")).toBeInTheDocument();
    expect(screen.getAllByText(SAMPLE).length).toBeGreaterThan(0);
  });
});
