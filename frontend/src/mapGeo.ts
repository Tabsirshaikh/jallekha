import wardGeometry from "./data/u5Geometry.json";
import sectionGeometry from "./data/u5SectionGeometry.json";
import sectionEvidence from "./data/u5SectionEvidence.json";
import wardEvidence from "./data/u5Evidence.json";

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

// --- sections (plans by section) ---------------------------------------------------------------


/** One drawn area: its path, plan group id and a centre point (drawing units) for labels. */
export type Shape = { id: string; name: string; group: string; d: string; centre: [number, number] };

function centreOf(f: Feature): [number, number] {
  const ring = rings(f).sort((a, b) => b.length - a.length)[0] ?? [];
  const pts = ring.map(project);
  const n = pts.length || 1;
  return [pts.reduce((s, p) => s + p[0], 0) / n, pts.reduce((s, p) => s + p[1], 0) / n];
}

const sectionNames = new Map((sectionEvidence as unknown as { wards: { id: string; name: string }[] }).wards.map((w) => [w.id, w.name]));
const wardNames = new Map((wardEvidence as unknown as { wards: { id: string; name: string }[] }).wards.map((w) => [w.id, w.name]));

export const sectionShapes: Shape[] = (sectionGeometry as unknown as { features: Feature[] }).features.map((f) => {
  const name = sectionNames.get(f.properties.ward_id) ?? f.properties.ward_name;
  return { id: f.properties.ward_id, name, group: `section:${name}`, d: pathOf(f), centre: centreOf(f) };
});
export const wardShapes: Shape[] = wardFeatures.map((f) => ({
  id: f.properties.ward_id, name: wardNames.get(f.properties.ward_id) ?? f.properties.ward_name, group: `ward:${f.properties.ward_id}`, d: pathOf(f), centre: centreOf(f),
}));
export const shapeByGroup = new Map(sectionShapes.map((s) => [s.group, s]));

/** x, y of the 1000-wide drawing back to lng, lat (inverse of `project`). */
export const unproject = ([x, y]: [number, number]): Pos => [minX + (x / WIDTH) * (maxX - minX), maxY - (y / HEIGHT) * (maxY - minY)];
