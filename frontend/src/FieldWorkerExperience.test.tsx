import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { setToken } from "./api";
import { AuthProvider } from "./auth";
import FieldWorkerExperience from "./FieldWorkerExperience";
import { LocaleProvider } from "./i18n";
import { apiError, callsTo, json, routedFetch } from "./test/apiMock";
import { fakeIndexedDb } from "./test/fakeIndexedDb";

const queued = {
  id: "11111111-aaaa-bbbb-cccc-000000000001", category: "no_water", details: "No water since morning", areaId: "", householdId: "HH-7",
  language: "en", createdAt: "2026-10-04T08:00:00.000Z", state: "queued",
};

function renderQueue() {
  return render(
    <LocaleProvider>
      <AuthProvider>
        <FieldWorkerExperience page="queue" onNavigate={() => undefined} />
      </AuthProvider>
    </LocaleProvider>,
  );
}

describe("FieldWorkerExperience", () => {
  let db: ReturnType<typeof fakeIndexedDb>;

  beforeEach(() => {
    setToken(null);
    db = fakeIndexedDb({ "jallekha-field-worker": { reports: [queued] } });
    vi.stubGlobal("indexedDB", db);
  });
  afterEach(() => vi.unstubAllGlobals());

  it("uses the signed-in field worker, sends the bearer token and marks the report sent", async () => {
    setToken("tok-fw");
    const fetchMock = routedFetch({
      "GET /auth/me": () => json({ role: "field_worker", user_id: "fw-1" }),
      "POST /intake/batch": () => json({ results: [{ status: "created", client_id: queued.id, complaint_id: "C-1", complaint_status: "open" }] }),
    });
    vi.stubGlobal("fetch", fetchMock);
    renderQueue();

    expect(await screen.findByText("Sent to intake")).toBeInTheDocument();
    expect(screen.getByText(/Signed in as field worker/)).toHaveTextContent("fw-1");
    expect(screen.queryByText(/DEMO-FW-01/)).not.toBeInTheDocument();
    expect(screen.queryByText("SYNTHETIC DEMO")).not.toBeInTheDocument();

    const [sent] = callsTo(fetchMock, "POST", "/intake/batch");
    expect(sent.headers.Authorization).toBe("Bearer tok-fw");
    const item = (sent.body?.items as Record<string, unknown>[])[0];
    expect(item).toMatchObject({ client_id: queued.id, channel: "field_worker", reporter_id: "fw-1", household_id: "HH-7", is_synthetic: false });
    expect(item).not.toHaveProperty("area_id");
    expect(db.rows("jallekha-field-worker", "reports")[0]).toMatchObject({ state: "submitted", complaintId: "C-1" });
  });

  it("keeps reports queued and asks for sign-in when intake answers 401", async () => {
    setToken("tok-expired");
    vi.stubGlobal("fetch", routedFetch({
      "GET /auth/me": () => json({ role: "field_worker", user_id: "fw-1" }),
      "POST /intake/batch": () => apiError(401),
    }));
    renderQueue();

    expect(await screen.findByText("Sign in with a field-worker token to send saved reports. They stay saved on this device.")).toBeInTheDocument();
    expect(screen.getByText("Waiting to sync")).toBeInTheDocument();
    expect(screen.queryByText("Sent to intake")).not.toBeInTheDocument();
    expect(db.rows("jallekha-field-worker", "reports")[0].state).toBe("queued");
  });

  it("shows the labelled demo identity when nobody is signed in and never marks reports sent", async () => {
    const fetchMock = routedFetch({ "POST /intake/batch": () => apiError(401) });
    vi.stubGlobal("fetch", fetchMock);
    renderQueue();

    expect(screen.getByText("SYNTHETIC DEMO")).toBeInTheDocument();
    expect(screen.getByText(/Sample worker ID: DEMO-FW-01/)).toBeInTheDocument();
    expect(await screen.findByText("Sign in with a field-worker token to send saved reports. They stay saved on this device.")).toBeInTheDocument();
    expect(screen.getByText("Waiting to sync")).toBeInTheDocument();
  });

  it("keeps reports queued when the server cannot be reached", async () => {
    setToken("tok-fw");
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
    renderQueue();
    expect(await screen.findByText("Could not reach intake. Reports remain saved here.")).toBeInTheDocument();
    await waitFor(() => expect(db.rows("jallekha-field-worker", "reports")[0].state).toBe("queued"));
  });
});
