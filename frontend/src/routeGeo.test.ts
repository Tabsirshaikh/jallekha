import { afterEach, describe, expect, it, vi } from "vitest";
import { fetchRoad, metres, pointAlong, remaining, type LatLng } from "./routeGeo";

// a road going north then east: 0.01 degrees is about 1.1 km
const road: LatLng[] = [[17.4, 78.4], [17.41, 78.4], [17.42, 78.4], [17.42, 78.41]];

describe("route geometry", () => {
  it("measures metres between two points", () => {
    expect(Math.round(metres([17.4, 78.4], [17.41, 78.4]))).toBeGreaterThan(1100);
    expect(metres([17.4, 78.4], [17.4, 78.4])).toBe(0);
  });

  it("keeps the whole road until the driver is on it", () => {
    expect(remaining(road, null)).toEqual(road);
    expect(remaining(road, [17.5, 78.5])).toEqual(road); // far away: not on the road yet
  });

  it("drops the part of the road already driven", () => {
    const left = remaining(road, [17.4101, 78.4]);
    expect(left[0]).toEqual([17.4101, 78.4]);
    expect(left.slice(1)).toEqual([[17.42, 78.4], [17.42, 78.41]]);
    expect(remaining(road, [17.42, 78.41]).length).toBe(1); // arrived: nothing left to draw
  });

  it("finds the place a fraction of the way along the road", () => {
    expect(pointAlong(road, 0)).toEqual(road[0]);
    expect(pointAlong(road, 1)).toEqual(road[3]);
    const half = pointAlong(road, 0.5);
    expect(half[0]).toBeGreaterThan(17.40);
    expect(half[0]).toBeLessThanOrEqual(17.42);
  });
});

describe("road from OSRM", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("asks OSRM for the road through the points and returns it as latitude, longitude", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ code: "Ok", routes: [{ distance: 2500, geometry: { coordinates: [[78.4, 17.4], [78.41, 17.41]] } }] }) });
    vi.stubGlobal("fetch", fetchMock);
    const out = await fetchRoad([[17.4, 78.4], [17.41, 78.41], [17.4, 78.4]], "https://osrm.test");
    expect(String(fetchMock.mock.calls[0][0])).toContain("/route/v1/driving/78.4,17.4;78.41,17.41;78.4,17.4?overview=full&geometries=geojson");
    expect(out).toEqual({ line: [[17.4, 78.4], [17.41, 78.41]], km: 2.5 });
  });

  it("gives null when the service cannot be reached, so the map falls back to straight lines", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));
    expect(await fetchRoad([[17.4, 78.4], [17.41, 78.41]], "https://osrm.test")).toBeNull();
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ code: "NoRoute" }) }));
    expect(await fetchRoad([[17.4, 78.4], [17.41, 78.41]], "https://osrm.test")).toBeNull();
  });
});
