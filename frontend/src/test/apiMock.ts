import { vi } from "vitest";

export function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

export function apiError(status: number, code = status === 401 ? "unauthorized" : status === 403 ? "forbidden" : "validation_error", message = "No"): Response {
  return json({ error: { code, message, details: null } }, status);
}

type Handler = Response | ((body: unknown, url: URL) => Response);

/**
 * A fetch stand-in keyed by "METHOD /path" (query ignored). A handler is a Response factory result
 * or a function of the parsed JSON body; unknown routes answer 404 in the shared error shape.
 */
export function routedFetch(routes: Record<string, () => Handler>) {
  return vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = new URL(String(input), "http://localhost");
    const key = `${init?.method ?? "GET"} ${url.pathname}`;
    const make = routes[key];
    if (!make) return apiError(404, "not_found", `No route ${key}`);
    const handler = make();
    if (handler instanceof Response) return handler;
    const body = typeof init?.body === "string" ? (JSON.parse(init.body) as unknown) : undefined;
    return handler(body, url);
  });
}

/** Headers and parsed body of every call to `path` made through the mock. */
export function callsTo(mock: ReturnType<typeof routedFetch>, method: string, path: string) {
  return mock.mock.calls
    .filter(([input, init]) => (init?.method ?? "GET") === method && new URL(String(input), "http://localhost").pathname === path)
    .map(([input, init]) => ({
      url: new URL(String(input), "http://localhost"),
      headers: (init?.headers ?? {}) as Record<string, string>,
      body: typeof init?.body === "string" ? (JSON.parse(init.body) as Record<string, unknown>) : undefined,
    }));
}
