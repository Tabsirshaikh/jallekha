import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { setToken } from "./api";
import { useApi } from "./useApi";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

describe("useApi", () => {
  beforeEach(() => setToken(null));
  afterEach(() => vi.unstubAllGlobals());

  it("loads data and marks it live", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({ total: 2 })));
    const { result } = renderHook(() => useApi<{ total: number }>("/shortage"));
    expect(result.current.loading).toBe(true);
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.data).toEqual({ total: 2 });
    expect(result.current.live).toBe(true);
    expect(result.current.error).toBeNull();
  });

  it("is not live and carries the error when the server fails", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
    const { result } = renderHook(() => useApi("/shortage"));
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.live).toBe(false);
    expect(result.current.data).toBeNull();
    expect(result.current.error).toMatchObject({ status: 0, code: "network_error" });
  });

  it("does nothing for a null path and refetches for a new path", async () => {
    const fetchMock = vi.fn().mockImplementation((url: string) => Promise.resolve(jsonResponse({ url })));
    vi.stubGlobal("fetch", fetchMock);
    const { result, rerender } = renderHook(({ path }: { path: string | null }) => useApi<{ url: string }>(path), { initialProps: { path: null as string | null } });
    expect(fetchMock).not.toHaveBeenCalled();
    expect(result.current.loading).toBe(false);
    rerender({ path: "/plans" });
    await waitFor(() => expect(result.current.data?.url).toMatch(/\/plans$/));
    rerender({ path: "/forecast" });
    await waitFor(() => expect(result.current.data?.url).toMatch(/\/forecast$/));
  });

  it("refetches when the token changes and on reload()", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ n: 1 }));
    vi.stubGlobal("fetch", fetchMock);
    const { result } = renderHook(() => useApi("/plans"));
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(fetchMock).toHaveBeenCalledTimes(1);
    act(() => setToken("t-new"));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    act(() => result.current.reload());
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3));
  });
});
