import { ApiError, apiFetch } from "./api";

/** One per-item result of `POST /intake/batch` (docs/api_shapes.md, intake). */
export type IntakeResultRow = { client_id?: string; status?: string; complaint_id?: string; complaint_status?: string; error?: string };

/**
 * What a sync attempt came to. `signIn`: the server refused the token (401) or the role (403);
 * `failed`: anything else (offline, server error). Only `sent` may change an item's queue state.
 */
export type IntakeSync = { kind: "sent"; results: IntakeResultRow[] } | { kind: "signIn" } | { kind: "failed" };

/** Post queued items through the shared client, so the signed-in bearer token goes with them. */
export async function sendIntakeBatch(items: Record<string, unknown>[]): Promise<IntakeSync> {
  try {
    const payload = await apiFetch<{ results?: IntakeResultRow[] }>("/intake/batch", { method: "POST", body: { items } });
    return { kind: "sent", results: payload.results ?? [] };
  } catch (cause) {
    if (cause instanceof ApiError && (cause.status === 401 || cause.status === 403)) return { kind: "signIn" };
    return { kind: "failed" };
  }
}
