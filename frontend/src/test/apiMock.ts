import { vi } from "vitest";

export function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

export function apiError(status: number, code = status === 401 ? "unauthorized" : status === 403 ? "forbidden" : "validation_error", message = "No"): Response {
  return json({ error: { code, message, details: null } }, status);
}

type Handler = Response | ((body: unknown, url: URL) => Response);

function matches(pattern: string, key: string): boolean {
  const want = pattern.split("/");
  const got = key.split("/");
  return want.length === got.length && want.every((part, index) => part === "*" || part === got[index]);
}

/**
 * A fetch stand-in keyed by "METHOD /path" (query ignored; a `*` path segment matches any one
 * segment). A handler is a Response or a function of the parsed JSON body and URL; unknown
 * routes answer 404 in the shared error shape.
 */
export function routedFetch(routes: Record<string, () => Handler>) {
  return vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = new URL(String(input), "http://localhost");
    const key = `${init?.method ?? "GET"} ${url.pathname}`;
    const pattern = Object.keys(routes).find((candidate) => matches(candidate, key));
    const make = pattern === undefined ? undefined : routes[pattern];
    if (!make) return apiError(404, "not_found", `No route ${key}`);
    const handler = make();
    if (handler instanceof Response) return handler;
    const body = typeof init?.body === "string" ? (JSON.parse(init.body) as unknown) : undefined;
    return handler(body, url);
  });
}

/** Headers and parsed body of every call to `path` (same `*` rule) made through the mock. */
export function callsTo(mock: ReturnType<typeof routedFetch>, method: string, path: string) {
  return mock.mock.calls
    .filter(([input, init]) => (init?.method ?? "GET") === method && matches(`${method} ${path}`, `${method} ${new URL(String(input), "http://localhost").pathname}`))
    .map(([input, init]) => ({
      url: new URL(String(input), "http://localhost"),
      headers: (init?.headers ?? {}) as Record<string, string>,
      body: typeof init?.body === "string" ? (JSON.parse(init.body) as Record<string, unknown>) : undefined,
    }));
}
