import { useMemo, useState } from "react";
import { HEIGHT, WIDTH, sectionShapes, wardShapes, type Shape } from "./mapGeo";
import type { LivePlan, PlanOverview, SectionCategory, SectionRow } from "./planAdapter";
import { CATEGORY } from "./planColours";

// Two small maps of a plan by section, side by side: what kind of area each section is (F7: which
// service it gets) and how much of its bookings the plan serves today. Clicking a section on
// either map shows its card. English only for now.

const nf = new Intl.NumberFormat("en", { maximumFractionDigits: 0 });

const ORDER: SectionCategory[] = ["cut", "scheduled", "heavy", "normal", "unknown"];
const GREEN = "#86c2a8", AMBER = "#e3a64a", RED = "#c4473a", NONE = "#eceeeb";

function coverColour(served: number, waiting: number) {
  if (served + waiting === 0) return NONE;
  const share = served / (served + waiting);
  return share >= 0.995 ? GREEN : share >= 0.9 ? AMBER : RED;
}

function MiniMap({ title, label, shapes, fill, selected, onSelect, base }: { title: string; label: string; shapes: Shape[]; fill: (s: Shape) => string; selected: string | null; onSelect: (s: Shape) => void; base?: boolean }) {
  const [hover, setHover] = useState<string | null>(null);
  const hovered = shapes.find((s) => s.id === hover);
  return (
    <div className="plan-mini-map">
      <svg viewBox={`-10 -10 ${WIDTH + 20} ${HEIGHT + 20}`} role="group" aria-label={label}>
        {base && wardShapes.map((w) => <path key={"b" + w.id} d={w.d} className="plan-mini-base" />)}
        {shapes.map((s) => <path key={s.id} d={s.d} fill={fill(s)} role="button" tabIndex={0} aria-label={s.name}
          className={(selected === s.group ? "selected " : "") + (hover === s.id ? "hover" : "")}
          onClick={() => onSelect(s)} onMouseEnter={() => setHover(s.id)} onMouseLeave={() => setHover(null)}
          onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onSelect(s); } }}><title>{s.name}</title></path>)}
      </svg>
      <span className="plan-mini-title">{title}</span>
      {hovered && <span className="plan-mini-tip">{hovered.name}</span>}
    </div>
  );
}

function SectionCard({ row, onClose }: { row: SectionRow; onClose: () => void }) {
  const c = CATEGORY[row.category];
  const share = row.bookings > 0 ? Math.round((100 * row.served) / row.bookings) : null;
  return (
    <div className="plan-section-card" role="status">
      <div className="plan-section-card-head">
        <strong>{row.name}</strong>
        <span className="plan-chip" style={{ background: c.colour, color: row.category === "normal" || row.category === "unknown" ? "#173c3a" : "#fff" }}>{c.label}</span>
        <button className="text-button" onClick={onClose} aria-label="Close section card">✕</button>
      </div>
      <p>{c.meaning}</p>
      <dl>
        <div><dt>Bookings today</dt><dd>{nf.format(row.bookings)}{row.carried > 0 && <small> ({nf.format(row.carried)} from earlier days)</small>}</dd></div>
        <div><dt>Served today</dt><dd>{nf.format(row.served)}{share !== null && <small> ({share}%)</small>}</dd></div>
        <div><dt>Waiting</dt><dd>{nf.format(row.waiting)}</dd></div>
        {row.turnFactor !== null && row.turnFactor !== 1 && <div><dt>Turns this week</dt><dd>{row.turnFactor.toFixed(2)}× its Census turns<small> ({row.turnFactor < 1 ? "got water lately" : "left waiting lately"})</small></dd></div>}
        <div><dt>Hospitals · no water at home · others</dt><dd>{row.tiers.map((t) => nf.format(t)).join(" · ")}</dd></div>
        {row.bookingsPer1000 !== null && <div><dt>Tankers a year per 1,000 homes</dt><dd>{nf.format(row.bookingsPer1000)}{row.peerBookingsPer1000 !== null && <small> (similar sections: {nf.format(row.peerBookingsPer1000)})</small>}</dd></div>}
        {row.scheduled && <div><dt>Water sent on schedule</dt><dd>{nf.format(row.scheduled.litres)} litres · {row.scheduled.loads} loads</dd></div>}
        {row.outage && <div><dt>Emergency water</dt><dd>{nf.format(row.outage.litres)} litres · {row.outage.loads} loads</dd></div>}
      </dl>
      {row.needEstimated && <p className="muted small">Its need or connection count is an estimate: an officer checks it before approval.</p>}
    </div>
  );
}

export default function PlanMaps({ plan, overview }: { plan: LivePlan; overview: PlanOverview }) {
  const [selected, setSelected] = useState<string | null>(null);
  const [cover, setCover] = useState<"sections" | "wards">("sections");
  const rows = useMemo(() => new Map(overview.sections.map((r) => [r.group, r])), [overview.sections]);
  const counts = useMemo(() => {
    const out: Record<SectionCategory, number> = { cut: 0, scheduled: 0, heavy: 0, normal: 0, unknown: 0 };
    for (const s of sectionShapes) out[rows.get(s.group)?.category ?? "unknown"] += 1;
    return out;
  }, [rows]);
  const pick = selected ? rows.get(selected) ?? null : null;
  const total = { served: overview.facts.served, waiting: overview.facts.waiting };
  const worst = useMemo(() => [...overview.sections].filter((r) => r.waiting > 0).sort((a, b) => b.waiting - a.waiting).slice(0, 5), [overview.sections]);

  const coverFill = (s: Shape) => {
    if (cover === "wards") { const t = plan.wardTotals?.[s.id]; return t ? coverColour(t.served, t.waiting) : NONE; }
    const r = rows.get(s.group);
    return r ? coverColour(r.served, r.waiting) : NONE;
  };
  const choose = (s: Shape) => { if (s.group.startsWith("section:")) setSelected(s.group === selected ? null : s.group); };

  return (
    <section className="plan-panel plan-maps" aria-labelledby="plan-maps-title">
      <div className="plan-panel-title"><div><p className="eyebrow">On the map</p><h2 id="plan-maps-title">What kind of area, and who gets water today</h2></div></div>
      <div className="plan-maps-grid">
        <figure>
          <MiniMap title="Kind of area" label="Map of service types by section" shapes={sectionShapes} base selected={selected} onSelect={choose} fill={(s) => CATEGORY[rows.get(s.group)?.category ?? "unknown"].colour} />
          <figcaption className="plan-maps-legend">{ORDER.map((k) => <span key={k}><i style={{ background: CATEGORY[k].colour }} />{CATEGORY[k].label} <b>{counts[k]}</b></span>)}</figcaption>
        </figure>
        <figure>
          <MiniMap title={cover === "wards" ? "Served today, by ward (estimate)" : "Served today"} label="Map of bookings served today" shapes={cover === "wards" ? wardShapes : sectionShapes} base={cover === "sections"} selected={selected} onSelect={choose} fill={coverFill} />
          <figcaption className="plan-maps-legend">
            <span><i style={{ background: GREEN }} />All served</span><span><i style={{ background: AMBER }} />90–99%</span><span><i style={{ background: RED }} />Under 90%</span><span><i style={{ background: NONE }} />No bookings</span>
            <span className="plan-map-switch" role="tablist" aria-label="Served map by">{(["sections", "wards"] as const).map((v) => <button key={v} role="tab" aria-selected={cover === v} className={cover === v ? "active" : ""} onClick={() => setCover(v)}>{v === "sections" ? "Sections" : "Wards"}</button>)}</span>
          </figcaption>
        </figure>
      </div>
      <div className="plan-maps-foot">
        {pick ? <SectionCard row={pick} onClose={() => setSelected(null)} /> : <p className="muted">Click a section on either map to see its bookings and why it is that kind of area.</p>}
        <div className="plan-maps-totals">
          <p><strong>{nf.format(total.served)}</strong> served · <strong>{nf.format(total.waiting)}</strong> waiting</p>
          {worst.length > 0 && <><span className="muted">Most waiting</span><ol>{worst.map((r) => <li key={r.group}><button onClick={() => setSelected(r.group)}>{r.name}</button><span>{nf.format(r.waiting)}</span></li>)}</ol></>}
        </div>
      </div>
    </section>
  );
}
