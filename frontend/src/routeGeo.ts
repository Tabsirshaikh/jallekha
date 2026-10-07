// Small map helpers for the driver's route: distances, the part of a road still ahead of the
// driver, a point along a road, and the road itself from OSRM (OpenStreetMap roads). No React here.

export type LatLng = [number, number];

/** The public OSRM demo server unless the deployment sets its own (VITE_OSRM_URL). */
export const OSRM_URL = ((import.meta.env.VITE_OSRM_URL as string | undefined) ?? "https://router.project-osrm.org").replace(/\/+$/, "");

/** Metres between two points (haversine). */
export function metres(a: LatLng, b: LatLng): number {
  const rad = Math.PI / 180, dLat = (b[0] - a[0]) * rad, dLng = (b[1] - a[1]) * rad;
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(a[0] * rad) * Math.cos(b[0] * rad) * Math.sin(dLng / 2) ** 2;
  return 2 * 6371000 * Math.asin(Math.sqrt(h));
}

/** The closest place on the road to `p`: which segment, and the point on it (flat approximation, fine over a city). */
function snap(line: LatLng[], p: LatLng): { segment: number; at: LatLng; off: number } {
  const kx = Math.cos((p[0] * Math.PI) / 180);
  let best = { segment: 0, at: line[0], off: Infinity };
  for (let i = 0; i + 1 < line.length; i++) {
    const [ay, ax] = line[i], [by, bx] = line[i + 1];
    const dx = (bx - ax) * kx, dy = by - ay, len2 = dx * dx + dy * dy;
    const t = len2 === 0 ? 0 : Math.max(0, Math.min(1, (((p[1] - ax) * kx) * dx + (p[0] - ay) * dy) / len2));
    const at: LatLng = [ay + (by - ay) * t, ax + (bx - ax) * t];
    const off = metres(p, at);
    if (off < best.off) best = { segment: i, at, off };
  }
  return best;
}

/** The part of the road still ahead of the driver; the whole road while the driver is not on it (`maxOff` metres). */
export function remaining(line: LatLng[], p: LatLng | null, maxOff = 300): LatLng[] {
  if (!p || line.length < 2) return line;
  const s = snap(line, p);
  if (s.off > maxOff) return line;
  const ahead = line.slice(s.segment + 1);
  if (ahead.length > 0 && metres(s.at, ahead[0]) < 1) ahead.shift(); // standing on the next corner
  return [s.at, ...ahead];
}

/** The place a fraction (0 to 1) of the way along the road, by length. */
export function pointAlong(line: LatLng[], fraction: number): LatLng {
  if (line.length === 0) return [0, 0];
  const parts = line.slice(1).map((q, i) => metres(line[i], q));
  const total = parts.reduce((a, b) => a + b, 0);
  let left = Math.max(0, Math.min(1, fraction)) * total;
  for (let i = 0; i < parts.length; i++) {
    if (left <= parts[i] || i === parts.length - 1) {
      const f = parts[i] === 0 ? 0 : Math.min(1, left / parts[i]);
      return [line[i][0] + (line[i + 1][0] - line[i][0]) * f, line[i][1] + (line[i + 1][1] - line[i][1]) * f];
    }
    left -= parts[i];
  }
  return line[0];
}

/** The road through `points` in order from OSRM, or null when the service cannot be reached (the map then draws straight lines). */
export async function fetchRoad(points: LatLng[], base = OSRM_URL, timeoutMs = 8000): Promise<{ line: LatLng[]; km: number } | null> {
  const control = new AbortController();
  const timer = setTimeout(() => control.abort(), timeoutMs);
  try {
    const where = points.map(([lat, lng]) => `${lng},${lat}`).join(";");
    const res = await fetch(`${base}/route/v1/driving/${where}?overview=full&geometries=geojson`, { signal: control.signal });
    if (!res.ok) return null;
    const body = (await res.json()) as { code?: string; routes?: { distance: number; geometry: { coordinates: [number, number][] } }[] };
    const route = body.code === "Ok" ? body.routes?.[0] : undefined;
    if (!route || route.geometry.coordinates.length < 2) return null;
    return { line: route.geometry.coordinates.map(([lng, lat]) => [lat, lng] as LatLng), km: Math.round(route.distance / 100) / 10 };
  } catch {
    return null;
  } finally {
    clearTimeout(timer);
  }
}
