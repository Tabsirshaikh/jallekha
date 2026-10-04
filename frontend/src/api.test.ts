import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError, apiFetch, apiUrl, getToken, onTokenChange, setToken } from "./api";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

describe("api client", () => {
  beforeEach(() => {
    setToken(null);
  });
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("keeps the token and tells listeners when it changes", () => {
    const seen: Array<string | null> = [];
    const stop = onTokenChange((token) => seen.push(token));
    setToken("t-abc");
    expect(getToken()).toBe("t-abc");
    setToken(null);
    stop();
    setToken("t-ignored");
    expect(seen).toEqual(["t-abc", null]);
  });

  it("adds the bearer token and sends JSON bodies", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ ok: true }));
    vi.stubGlobal("fetch", fetchMock);
    setToken("t-abc");
    await apiFetch("/plans", { method: "POST", body: { day: "2025-05-01" } });
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe(apiUrl("/plans"));
    expect(init.method).toBe("POST");
    expect((init.headers as Record<string, string>).Authorization).toBe("Bearer t-abc");
    expect((init.headers as Record<string, string>)["Content-Type"]).toBe("application/json");
    expect(init.body).toBe(JSON.stringify({ day: "2025-05-01" }));
  });

  it("sends no Authorization header without a token", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ status: "ok" }));
    vi.stubGlobal("fetch", fetchMock);
    await apiFetch("/health");
    const init = fetchMock.mock.calls[0][1] as RequestInit;
    expect((init.headers as Record<string, string>).Authorization).toBeUndefined();
  });

  it("turns the shared error shape into an ApiError", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({ error: { code: "forbidden", message: "Role resident may not call this endpoint", details: null } }, 403)));
    const error = await apiFetch("/plans").catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ status: 403, code: "forbidden", message: "Role resident may not call this endpoint" });
  });

  it("reports an unreachable server as status 0 and a broken body as a generic error", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
    await expect(apiFetch("/health")).rejects.toMatchObject({ status: 0, code: "network_error" });
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("<html>bad gateway</html>", { status: 502 })));
    await expect(apiFetch("/health")).rejects.toMatchObject({ status: 502, code: "http_502" });
  });

  it("builds URLs from VITE_API_URL with one slash", () => {
    expect(apiUrl("/plans")).toMatch(/\/plans$/);
    expect(apiUrl("plans")).toMatch(/\/plans$/);
    expect(apiUrl("/plans")).not.toMatch(/\/\/plans$/);
  });
});
