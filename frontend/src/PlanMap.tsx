import { useMemo, useState } from "react";
import type { LivePlan } from "./planAdapter";
import sectionGeometry from "./data/u5SectionGeometry.json";
import sectionEvidence from "./data/u5SectionEvidence.json";
import wardGeometry from "./data/u5Geometry.json";
import wardEvidence from "./data/u5Evidence.json";
import "./PlanMap.css";

// Coverage map of a daily plan: how much of each area's bookings the plan serves. A plan by section
// shows the sections and, as an estimate, the wards (each section's bookings shared over wards by
// building share). English only for now.

type Pos = [number, number];
type Feature = { geometry: { type: string; coordinates: unknown }; properties: { ward_id: string; ward_name: string } };
type Area = { id: string; name: string; served: number; waiting: number; flagged: boolean; checked: boolean };

const GREEN = "#86c2a8", AMBER = "#e3a64a", RED = "#c4473a", NONE = "#eceeeb";

function pts(v: unknown): Pos[] {
  if (!Array.isArray(v)) return [];
  if (typeof v[0] === "number" && typeof v[1] === "number") return [[v[0], v[1]]];
  return v.flatMap(pts);
}
function rings(f: Feature): Pos[][] {
  const polys = f.geometry.type === "Polygon" ? [f.geometry.coordinates] : (f.geometry.coordinates as unknown[]);
  return polys.flatMap((poly) => (Array.isArray(poly) ? poly.map(pts) : [])).filter((ring) => ring.length > 2);
}

const sectionFeatures = (sectionGeometry as unknown as { features: Feature[] }).features;
const wardFeatures = (wardGeometry as unknown as { features: Feature[] }).features;
const sectionNames = new Map((sectionEvidence as unknown as { wards: { id: string; name: string }[] }).wards.map((w) => [w.id, w.name]));
const wardNames = new Map((wardEvidence as unknown as { wards: { id: string; name: string }[] }).wards.map((w) => [w.id, w.name]));
const nf = new Intl.NumberFormat("en", { maximumFractionDigits: 0 });

function colour(a: Area | undefined) {
  if (!a || a.served + a.waiting === 0) return NONE;
  const share = a.served / (a.served + a.waiting);
  return share >= 0.995 ? GREEN : share >= 0.9 ? AMBER : RED;
}

export default function PlanMap({ plan }: { plan: LivePlan }) {
  const bySection = plan.unit === "section";
  const [view, setView] = useState<"sections" | "wards">(bySection ? "sections" : "wards");
  const [selected, setSelected] = useState<string | null>(null);
  const [hover, setHover] = useState<string | null>(null);
  const shown: "sections" | "wards" = bySection ? view : "wards";

  const flagged = useMemo(() => new Set(plan.flags.map((f) => f.group)), [plan.flags]);
  const checked = useMemo(() => new Set(plan.flags.filter((f) => f.checked).map((f) => f.group)), [plan.flags]);

  // One Area per drawn shape, from this plan's totals.
  const { features, areas } = useMemo(() => {
    const map = new Map<string, Area>();
    if (shown === "sections") {
      for (const f of sectionFeatures) {
        const id = f.properties.ward_id;
        const name = sectionNames.get(id) ?? f.properties.ward_name;
        const group = `section:${name}`;
        const t = plan.groupTotals[group];
        map.set(id, { id, name, served: t?.served ?? 0, waiting: t?.waiting ?? 0, flagged: flagged.has(group), checked: checked.has(group) });
      }
      return { features: sectionFeatures, areas: map };
    }
    for (const f of wardFeatures) {
      const id = f.properties.ward_id;
      const t = bySection ? plan.wardTotals?.[id] : plan.groupTotals[`ward:${id}`];
      map.set(id, { id, name: wardNames.get(id) ?? f.properties.ward_name, served: t?.served ?? 0, waiting: t?.waiting ?? 0, flagged: flagged.has(`ward:${id}`), checked: checked.has(`ward:${id}`) });
    }
    return { features: wardFeatures, areas: map };
  }, [shown, plan.groupTotals, plan.wardTotals, bySection, flagged, checked]);

  const geo = useMemo(() => {
    const all = wardFeatures.flatMap((f) => rings(f).flat());
    const xs = all.map((p) => p[0]), ys = all.map((p) => p[1]);
    const minX = Math.min(...xs), maxX = Math.max(...xs), minY = Math.min(...ys), maxY = Math.max(...ys);
    const k = Math.cos((((minY + maxY) / 2) * Math.PI) / 180);
    const width = 1000, height = Math.round((width * (maxY - minY)) / ((maxX - minX) * k));
    const project = ([x, y]: Pos) => `${(((x - minX) / (maxX - minX)) * width).toFixed(1)},${(((maxY - y) / (maxY - minY)) * height).toFixed(1)}`;
    return { width, height, d: (f: Feature) => rings(f).map((r) => "M" + r.map(project).join("L") + "Z").join("") };
  }, []);

  const base = useMemo(() => (shown === "sections" ? wardFeatures.map((f) => geo.d(f)) : []), [shown, geo]);
  const paths = useMemo(() => features.map((f) => ({ id: f.properties.ward_id, d: geo.d(f) })), [features, geo]);
  const total = [...areas.values()].reduce((s, a) => ({ served: s.served + a.served, waiting: s.waiting + a.waiting }), { served: 0, waiting: 0 });
  const worst = [...areas.values()].filter((a) => a.waiting > 0).sort((a, b) => b.waiting - a.waiting).slice(0, 6);
  const pick = selected ? areas.get(selected) ?? null : null;

  return (
    <section className="plan-panel plan-map-panel" aria-labelledby="plan-map-title">
      <div className="plan-panel-title">
        <div><p className="eyebrow">Coverage</p><h2 id="plan-map-title">Who the plan serves, on the map</h2></div>
        {bySection && <div className="plan-map-switch" role="tablist" aria-label="Map by">
          {(["sections", "wards"] as const).map((v) => <button key={v} role="tab" aria-selected={view === v} className={view === v ? "active" : ""} onClick={() => { setView(v); setSelected(null); }}>{v === "sections" ? "Sections" : "Wards"}</button>)}
        </div>}
      </div>
      <p className="plan-threshold">
        Green: every booking of the area is served today. Amber: 90–99% served. Red: under 90% served. Grey: no bookings or not on the map.
        {shown === "wards" && bySection ? " Ward figures are an estimate: each section’s bookings are shared over wards by building share." : ""}
      </p>
      <div className="plan-map-stage">
        <svg viewBox={`-10 -10 ${geo.width + 20} ${geo.height + 20}`} role="group" aria-label="Plan coverage map">
          {base.map((d, i) => <path key={"b" + i} d={d} fill="#f1f3f0" pointerEvents="none" />)}
          {paths.map(({ id, d }) => {
            const a = areas.get(id);
            return <path key={id} d={d} fill={colour(a)} role="button" tabIndex={0} aria-label={a?.name ?? id}
              className={(selected === id ? "selected " : "") + (hover === id ? "hover" : "")}
              style={a?.flagged && !a.checked ? { stroke: "#9a4a1c", strokeWidth: 2.5 } : undefined}
              onClick={() => setSelected(id)} onMouseEnter={() => setHover(id)} onMouseLeave={() => setHover(null)}
              onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); setSelected(id); } }}><title>{a?.name ?? id}</title></path>;
          })}
        </svg>
        <div className="plan-map-legend"><i style={{ background: GREEN }} />all served<i style={{ background: AMBER }} />90–99%<i style={{ background: RED }} />under 90%<i style={{ background: NONE }} />none{shown === "sections" && <><i className="flag" />needs a check</>}</div>
        {hover && areas.get(hover) && <div className="plan-map-tip">{areas.get(hover)!.name}</div>}
      </div>
      <div className="plan-map-side">
        <p><strong>{nf.format(total.served)}</strong> served, <strong>{nf.format(total.waiting)}</strong> waiting
          {bySection && plan.wardUnplaced && shown === "wards" && plan.wardUnplaced.served + plan.wardUnplaced.waiting > 0 ? ` · ${nf.format(plan.wardUnplaced.served + plan.wardUnplaced.waiting)} bookings sit in sections no ward could take` : ""}
          {total.served + total.waiting === 0 ? " · nothing to show" : ""}</p>
        {pick && <div className="plan-map-pick"><strong>{pick.name}</strong>
          <span>{nf.format(pick.served)} served · {nf.format(pick.waiting)} waiting{pick.served + pick.waiting > 0 ? ` (${nf.format((100 * pick.served) / (pick.served + pick.waiting))}% served)` : ""}</span>
          {pick.flagged && <span>{pick.checked ? "Flagged and checked by an officer" : "Flagged: an officer must check it before approval"}</span>}</div>}
        {worst.length > 0 && <div><strong>Most waiting</strong><ol>{worst.map((a) => <li key={a.id}><button onClick={() => setSelected(a.id)}>{a.name}</button><span>{nf.format(a.waiting)}</span></li>)}</ol></div>}
        {worst.length === 0 && total.served > 0 && <p className="muted">Every booking is served today. Try the tight capacity to see who waits.</p>}
      </div>
    </section>
  );
}
