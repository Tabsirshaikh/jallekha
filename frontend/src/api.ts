/** Shared client for the JalLekha API (T10): bearer token, shared error shape, no silent failures. */

const BASE = ((import.meta.env.VITE_API_URL as string | undefined) ?? "").replace(/\/+$/, "");
const STORAGE_KEY = "jallekha-api-token";

export class ApiError extends Error {
  status: number;
  code: string;
  details: unknown;

  constructor(status: number, code: string, message: string, details: unknown = null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

export function apiUrl(path: string): string {
  return `${BASE}/${path.replace(/^\/+/, "")}`;
}

// The token lives in sessionStorage so a closed tab signs out; a private window or blocked storage
// falls back to memory and the page still works for the session.
let memoryToken: string | null = null;
const listeners = new Set<(token: string | null) => void>();

export function getToken(): string | null {
  try {
    return sessionStorage.getItem(STORAGE_KEY) ?? memoryToken;
  } catch {
    return memoryToken;
  }
}

export function setToken(token: string | null): void {
  memoryToken = token;
  try {
    if (token) sessionStorage.setItem(STORAGE_KEY, token);
    else sessionStorage.removeItem(STORAGE_KEY);
  } catch {
    // memory copy is enough
  }
  listeners.forEach((listener) => listener(token));
}

export function onTokenChange(listener: (token: string | null) => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

type FetchOptions = {
  method?: "GET" | "POST";
  body?: unknown;
  headers?: Record<string, string>;
  signal?: AbortSignal;
};

async function failure(response: Response): Promise<ApiError> {
  try {
    const parsed = (await response.json()) as { error?: { code?: string; message?: string; details?: unknown } };
    if (parsed.error?.code) return new ApiError(response.status, parsed.error.code, parsed.error.message ?? parsed.error.code, parsed.error.details ?? null);
  } catch {
    // not the shared error shape (for example a proxy error page)
  }
  return new ApiError(response.status, `http_${response.status}`, response.statusText || `HTTP ${response.status}`);
}

export async function apiFetch<T>(path: string, options: FetchOptions = {}): Promise<T> {
  const headers: Record<string, string> = { Accept: "application/json", ...options.headers };
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  if (options.body !== undefined) headers["Content-Type"] = "application/json";
  let response: Response;
  try {
    response = await fetch(apiUrl(path), {
      method: options.method ?? "GET",
      headers,
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
      signal: options.signal,
    });
  } catch (cause) {
    if (cause instanceof DOMException && cause.name === "AbortError") throw cause;
    throw new ApiError(0, "network_error", "The server could not be reached");
  }
  if (!response.ok) throw await failure(response);
  return (await response.json()) as T;
}
