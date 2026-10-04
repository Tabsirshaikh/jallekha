import { act, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { getToken, setToken } from "./api";
import { AuthProvider, useAuth } from "./auth";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

function Probe() {
  const auth = useAuth();
  return (
    <div>
      <p data-testid="status">{auth.status}</p>
      <p data-testid="who">{auth.role ?? "-"}:{auth.userId ?? "-"}</p>
      <button onClick={() => void auth.signIn("t-field-1")}>in</button>
      <button onClick={() => auth.signOut()}>out</button>
    </div>
  );
}

describe("AuthProvider", () => {
  beforeEach(() => setToken(null));
  afterEach(() => vi.unstubAllGlobals());

  it("starts anonymous when there is no token", () => {
    vi.stubGlobal("fetch", vi.fn());
    render(<AuthProvider><Probe /></AuthProvider>);
    expect(screen.getByTestId("status")).toHaveTextContent("anonymous");
  });

  it("signs in through /auth/me and keeps the role and user id", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({ role: "field_worker", user_id: "fw-7" })));
    render(<AuthProvider><Probe /></AuthProvider>);
    await act(async () => screen.getByText("in").click());
    await waitFor(() => expect(screen.getByTestId("status")).toHaveTextContent("signed-in"));
    expect(screen.getByTestId("who")).toHaveTextContent("field_worker:fw-7");
    expect(getToken()).toBe("t-field-1");
  });

  it("rejects a token the server does not know and forgets it", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({ error: { code: "unauthorized", message: "Unknown token" } }, 401)));
    render(<AuthProvider><Probe /></AuthProvider>);
    await act(async () => screen.getByText("in").click());
    await waitFor(() => expect(screen.getByTestId("status")).toHaveTextContent("rejected"));
    expect(getToken()).toBeNull();
  });

  it("checks a stored token on load and signs out cleanly", async () => {
    setToken("t-stored");
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({ role: "officer", user_id: null })));
    render(<AuthProvider><Probe /></AuthProvider>);
    await waitFor(() => expect(screen.getByTestId("status")).toHaveTextContent("signed-in"));
    expect(screen.getByTestId("who")).toHaveTextContent("officer:-");
    await act(async () => screen.getByText("out").click());
    expect(screen.getByTestId("status")).toHaveTextContent("anonymous");
    expect(getToken()).toBeNull();
  });

  it("keeps the token and says the server is unreachable when it cannot be asked", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
    render(<AuthProvider><Probe /></AuthProvider>);
    await act(async () => screen.getByText("in").click());
    await waitFor(() => expect(screen.getByTestId("status")).toHaveTextContent("unreachable"));
    expect(getToken()).toBe("t-field-1");
  });
});
