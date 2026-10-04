import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { setToken } from "./api";
import { AuthProvider } from "./auth";
import { LocaleProvider } from "./i18n";
import ResidentExperience from "./ResidentExperience";
import { apiError, callsTo, json, routedFetch } from "./test/apiMock";
import { fakeIndexedDb } from "./test/fakeIndexedDb";

const queued = {
  id: "22222222-aaaa-bbbb-cccc-000000000002", category: "tanker_missed", details: "Tanker did not come", areaLabel: "",
  createdAt: "2026-10-04T08:00:00.000Z", latitude: 17.385, longitude: 78.4867, state: "queued",
};

function renderRequests() {
  return render(
    <LocaleProvider>
      <AuthProvider>
        <ResidentExperience page="requests" onNavigate={() => undefined} />
      </AuthProvider>
    </LocaleProvider>,
  );
}

describe("ResidentExperience sync", () => {
  let db: ReturnType<typeof fakeIndexedDb>;

  beforeEach(() => {
    setToken(null);
    db = fakeIndexedDb({ "jallekha-resident": { reports: [queued] } });
    vi.stubGlobal("indexedDB", db);
  });
  afterEach(() => vi.unstubAllGlobals());

  it("sends saved reports with the bearer token and marks them sent", async () => {
    setToken("tok-res");
    const fetchMock = routedFetch({
      "GET /auth/me": () => json({ role: "resident", user_id: "res-1" }),
      "POST /intake/batch": () => json({ results: [{ status: "created", client_id: queued.id, complaint_id: "C-9", complaint_status: "open" }] }),
    });
    vi.stubGlobal("fetch", fetchMock);
    renderRequests();

    expect(await screen.findByText("Sent to JalLekha")).toBeInTheDocument();
    const [sent] = callsTo(fetchMock, "POST", "/intake/batch");
    expect(sent.headers.Authorization).toBe("Bearer tok-res");
    expect((sent.body?.items as Record<string, unknown>[])[0]).toMatchObject({ client_id: queued.id, channel: "app", category: "tanker_missed", lat: 17.385, lon: 78.4867 });
    expect(db.rows("jallekha-resident", "reports")[0]).toMatchObject({ state: "submitted", complaintId: "C-9" });
  });

  it("keeps reports queued and asks the resident to sign in on 403", async () => {
    setToken("tok-officer");
    vi.stubGlobal("fetch", routedFetch({
      "GET /auth/me": () => json({ role: "officer", user_id: "off-1" }),
      "POST /intake/batch": () => apiError(403),
    }));
    renderRequests();

    expect(await screen.findByText("Sign in with a resident token to send your saved reports. They stay saved on this device.")).toBeInTheDocument();
    expect(screen.getByText("Waiting to sync")).toBeInTheDocument();
    expect(screen.queryByText("Sent to JalLekha")).not.toBeInTheDocument();
    expect(db.rows("jallekha-resident", "reports")[0].state).toBe("queued");
  });

  it("asks for sign-in and keeps reports queued when nobody is signed in", async () => {
    vi.stubGlobal("fetch", routedFetch({ "POST /intake/batch": () => apiError(401) }));
    renderRequests();
    expect(await screen.findByText("Sign in with a resident token to send your saved reports. They stay saved on this device.")).toBeInTheDocument();
    expect(db.rows("jallekha-resident", "reports")[0].state).toBe("queued");
  });
});
