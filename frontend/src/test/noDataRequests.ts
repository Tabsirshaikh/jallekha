import { expect } from "vitest";

/** Signed out, the only request a screen may make is the probe asking whether the server is open. */
export function expectNoDataRequests(fetchMock: { mock: { calls: unknown[][] } }): void {
  const urls = fetchMock.mock.calls.map((call) => String(call[0]));
  expect(urls.filter((url) => !url.endsWith("/auth/me"))).toEqual([]);
}
