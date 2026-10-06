import wardGeometry from "./data/u5Geometry.json";

// Shared by the plan maps: the ward outlines (for context) and one projection over them, so every
// plan map is drawn in the same place and shape.

export type Pos = [number, number];
export type Feature = { geometry: { type: string; coordinates: unknown }; properties: { ward_id: string; ward_name: string } };

function pts(v: unknown): Pos[] {
  if (!Array.isArray(v)) return [];
  if (typeof v[0] === "number" && typeof v[1] === "number") return [[v[0], v[1]]];
  return v.flatMap(pts);
}
export function rings(f: Feature): Pos[][] {
  const polys = f.geometry.type === "Polygon" ? [f.geometry.coordinates] : (f.geometry.coordinates as unknown[]);
  return polys.flatMap((poly) => (Array.isArray(poly) ? poly.map(pts) : [])).filter((ring) => ring.length > 2);
}

export const wardFeatures = (wardGeometry as unknown as { features: Feature[] }).features;

const all = wardFeatures.flatMap((f) => rings(f).flat());
const xs = all.map((p) => p[0]), ys = all.map((p) => p[1]);
const minX = Math.min(...xs), maxX = Math.max(...xs), minY = Math.min(...ys), maxY = Math.max(...ys);
const k = Math.cos((((minY + maxY) / 2) * Math.PI) / 180);

export const WIDTH = 1000;
export const HEIGHT = Math.round((WIDTH * (maxY - minY)) / ((maxX - minX) * k));
/** lng, lat to x, y of the 1000-wide drawing. */
export const project = ([x, y]: Pos): [number, number] => [((x - minX) / (maxX - minX)) * WIDTH, ((maxY - y) / (maxY - minY)) * HEIGHT];
export const pathOf = (f: Feature) => rings(f).map((r) => "M" + r.map((p) => project(p).map((v) => v.toFixed(1)).join(",")).join("L") + "Z").join("");
