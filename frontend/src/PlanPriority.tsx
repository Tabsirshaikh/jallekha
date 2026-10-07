import { useEffect, useMemo, useState } from "react";
import type { PlanOverview, SectionRow, StationQueue } from "./planAdapter";
import { REASON_TIER, TIER } from "./planColours";

// Who gets a tanker first (F8), drawn: the three priority steps for the whole city, then one
// filling station's queue played back tanker by tanker in the order the plan served it, so the
// fair turns (deficit round robin) can be seen. English only for now.

const nf = new Intl.NumberFormat("en", { maximumFractionDigits: 0 });

function Bar({ served, total, colour }: { served: number; total: number; colour: string }) {
  const w = total > 0 ? (100 * served) / total : 0;
  return <span className="plan-bar" aria-hidden="true"><i style={{ width: `${w}%`, background: colour }} /></span>;
}

function StepList({ rows, tier, open }: { rows: SectionRow[]; tier: number; open: boolean }) {
  const ranked = rows.filter((r) => r.tiers[tier] > 0).sort((a, b) => b.tiers[tier] - a.tiers[tier] || a.name.localeCompare(b.name));
  const shown = open ? ranked : ranked.slice(0, 5);
  const why = (r: SectionRow) =>
    tier === 0 ? `${r.tiers[0]} hospital or care-home booking${r.tiers[0] === 1 ? "" : "s"}`
      : tier === 1 ? `${r.noWaterShare !== null ? Math.round(100 * r.noWaterShare) : "?"}% of homes have no water at home`
      : `${nf.format(r.servedTiers[2])} of ${nf.format(r.tiers[2])} served in turns`;
  return <ol className="plan-step-list">{shown.map((r, i) => <li key={r.group}><b>{i + 1}</b><span>{r.name}</span><small>{why(r)}</small></li>)}
    {ranked.length === 0 && <li className="muted">None today.</li>}</ol>;
}

/** The station whose queue shows fair turns best: several sections, some waiting, a hospital. */
function bestStation(stations: StationQueue[]): string | null {
  const score = (s: StationQueue) => {
    const groups = Object.values(s.bookings).filter((n) => n >= 3).length;
    const total = Object.values(s.bookings).reduce((a, b) => a + b, 0);
    const waiting = total - s.served.length;
    const tiers = new Set(s.served.map((b) => REASON_TIER[b.reason] ?? 2)).size;
    return (waiting > 0 ? 100 : 0) + Math.min(groups, 7) * 10 + tiers * 5 - Math.abs(s.served.length - 120) / 40;
  };
  return [...stations].filter((s) => s.served.length > 0).sort((a, b) => score(b) - score(a))[0]?.station ?? null;
}

const W = 640, H = 400, CX = 320, CY = 195, RING = 145;

function StationQueuePlayer({ queue, names }: { queue: StationQueue; names: Map<string, string> }) {
  const [step, setStep] = useState(0);
  const [playing, setPlaying] = useState(true);
  const [speed, setSpeed] = useState(2);
  const total = queue.served.length;

  // Sections of the station around it, biggest first, at most 9 (the rest are grouped as "others").
  const buckets = useMemo(() => {
    const entries = Object.entries(queue.bookings).sort((a, b) => b[1] - a[1]);
    const top = entries.slice(0, 9);
    const rest = entries.slice(9);
    const list = top.map(([group, n]) => ({ key: group, groups: [group], name: names.get(group) ?? group.replace(/^section:/, ""), booked: n }));
    if (rest.length) list.push({ key: "others", groups: rest.map((e) => e[0]), name: `${rest.length} other sections`, booked: rest.reduce((s, e) => s + e[1], 0) });
    const max = Math.max(1, ...list.map((b) => b.booked));
    return list.map((b, i) => {
      const angle = -Math.PI / 2 + (2 * Math.PI * i) / list.length;
      return { ...b, x: CX + RING * Math.cos(angle), y: CY + RING * Math.sin(angle), r: 14 + 22 * Math.sqrt(b.booked / max) };
    });
  }, [queue.bookings, names]);
  const bucketOf = useMemo(() => {
    const m = new Map<string, number>();
    buckets.forEach((b, i) => b.groups.forEach((g) => m.set(g, i)));
    return m;
  }, [buckets]);

  useEffect(() => {
    if (!playing || step >= total) return;
    const id = window.setTimeout(() => setStep((s) => Math.min(total, s + 1)), 520 / speed);
    return () => window.clearTimeout(id);
  }, [playing, step, total, speed]);

  const served = useMemo(() => {
    const out = buckets.map(() => [0, 0, 0]);
    for (const b of queue.served.slice(0, step)) {
      const i = bucketOf.get(b.group);
      if (i !== undefined) out[i][REASON_TIER[b.reason] ?? 2] += 1;
    }
    return out;
  }, [buckets, bucketOf, queue.served, step]);
  const recent = queue.served.slice(Math.max(0, step - 8), step).map((b, i) => ({ ...b, n: Math.max(0, step - 8) + i + 1 })).reverse();
  const flying = queue.served.slice(Math.max(0, step - 3), step).map((b, i) => ({ ...b, n: Math.max(0, step - 3) + i + 1 }));
  const bookedTotal = Object.values(queue.bookings).reduce((a, b) => a + b, 0);
  const done = step >= total;
  const phase = step === 0 ? null : REASON_TIER[queue.served[step - 1].reason] ?? 2;

  return (
    <div className="plan-player">
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`Queue of station ${queue.station} played back`}>
        {buckets.map((b) => <line key={"l" + b.key} x1={CX} y1={CY} x2={b.x} y2={b.y} className="plan-player-spoke" />)}
        {buckets.map((b, i) => {
          const got = served[i][0] + served[i][1] + served[i][2];
          const frac = Math.min(1, got / Math.max(1, b.booked));
          const c = 2 * Math.PI * (b.r - 3);
          return <g key={b.key}>
            <circle cx={b.x} cy={b.y} r={b.r} className="plan-player-bucket" />
            <circle cx={b.x} cy={b.y} r={b.r - 3} fill="none" stroke="#1f7560" strokeWidth="6" strokeDasharray={`${frac * c} ${c}`} transform={`rotate(-90 ${b.x} ${b.y})`} />
            <text x={b.x} y={b.y + 5} textAnchor="middle" className="plan-player-count">{got}/{b.booked}</text>
            <text x={b.x} y={b.y + b.r + 16} textAnchor="middle" className="plan-player-name">{b.name.length > 20 ? b.name.slice(0, 19) + "…" : b.name}</text>
          </g>;
        })}
        {flying.map((f) => {
          const b = buckets[bucketOf.get(f.group) ?? -1];
          if (!b) return null;
          return <circle key={f.n} cx={CX} cy={CY} r="8" fill={TIER[REASON_TIER[f.reason] ?? 2].colour} className="plan-player-token"
            style={{ ["--dx" as string]: `${b.x - CX}px`, ["--dy" as string]: `${b.y - CY}px`, animationDuration: `${Math.max(180, 480 / speed)}ms` }} />;
        })}
        <g>
          <circle cx={CX} cy={CY} r="30" className="plan-player-station" />
          <text x={CX} y={CY - 2} textAnchor="middle" className="plan-player-station-label">{queue.station}</text>
          <text x={CX} y={CY + 14} textAnchor="middle" className="plan-player-station-sub">{total - step} trips left</text>
        </g>
      </svg>
      <div className="plan-player-side">
        <div className="plan-player-controls">
          <button className="button button-primary" onClick={() => (done ? (setStep(0), setPlaying(true)) : setPlaying(!playing))}>{done ? "↺ Play again" : playing ? "⏸ Pause" : "▶ Play"}</button>
          <button className="button button-secondary" onClick={() => { setPlaying(false); setStep((s) => Math.min(total, s + 1)); }} disabled={done}>Next tanker</button>
          <label>Speed <select value={speed} onChange={(e) => setSpeed(Number(e.target.value))}><option value={1}>1×</option><option value={2}>2×</option><option value={5}>5×</option><option value={15}>15×</option></select></label>
        </div>
        <p className="plan-player-now">{step === 0 ? "Press play: tankers leave the station one by one." : <>Tanker <b>{step}</b> of {total}: <span style={{ color: TIER[phase ?? 2].colour }}>{TIER[phase ?? 2].label.toLowerCase()}</span></>}</p>
        <ol className="plan-player-log">{recent.map((r) => <li key={r.n}><i style={{ background: TIER[REASON_TIER[r.reason] ?? 2].colour }} /><b>{r.n}</b> {names.get(r.group) ?? r.group.replace(/^section:/, "")}<small>{TIER[REASON_TIER[r.reason] ?? 2].short}</small></li>)}</ol>
        {done && <p className="plan-player-end">{bookedTotal > total ? `Trips used up: ${nf.format(bookedTotal - total)} bookings at this station wait for tomorrow.` : "Every booking at this station is served today."}</p>}
      </div>
    </div>
  );
}

export default function PlanPriority({ overview }: { overview: PlanOverview }) {
  const [open, setOpen] = useState<number | null>(null);
  const [station, setStation] = useState<string | null>(() => bestStation(overview.stations));
  const { facts, sections } = overview;
  const names = useMemo(() => new Map(sections.map((r) => [r.group, r.name])), [sections]);
  const queue = overview.stations.find((s) => s.station === station) ?? null;
  const options = useMemo(() => [...overview.stations].filter((s) => s.served.length > 0).sort((a, b) => a.station.localeCompare(b.station, "en", { numeric: true })), [overview.stations]);
  const steps = [
    { title: "Hospitals and care homes", text: "Always first. A hospital without water cannot wait." },
    { title: "Homes with no water at home", text: "Next: families who must fetch every pot from outside (Census)." },
    { title: "Everyone else, in fair turns", text: "Sections take turns. More need = bigger turns, but nobody is skipped." },
  ];

  return (
    <section className="plan-panel plan-priority" aria-labelledby="plan-priority-title">
      <div className="plan-panel-title"><div><p className="eyebrow">Priority</p><h2 id="plan-priority-title">Who gets a tanker first</h2></div></div>
      <p className="plan-threshold">Every filling station serves its bookings in the same three steps. A step starts only when the one before it is done. The priority classes are estimates (HMWSSB does not publish booking types).</p>
      <div className="plan-steps">
        {steps.map((s, i) => <article key={s.title} className="plan-step" style={{ borderTopColor: TIER[i].colour }}>
          <header><span className="plan-step-n" style={{ background: TIER[i].colour }}>{i + 1}</span><div><h3>{s.title}</h3><p>{s.text}</p></div></header>
          <div className="plan-step-figures"><strong>{nf.format(facts.tiers[i])}</strong><span>bookings</span><strong>{nf.format(facts.servedTiers[i])}</strong><span>served</span>{facts.tiers[i] - facts.servedTiers[i] > 0 && <><strong>{nf.format(facts.tiers[i] - facts.servedTiers[i])}</strong><span>wait</span></>}</div>
          <Bar served={facts.servedTiers[i]} total={facts.tiers[i]} colour={TIER[i].colour} />
          <StepList rows={sections} tier={i} open={open === i} />
          <button className="text-button" onClick={() => setOpen(open === i ? null : i)}>{open === i ? "Show fewer" : "Show every section"}</button>
        </article>)}
      </div>

      <div className="plan-rr">
        <div className="plan-rr-head">
          <div><h3>Watch a station share its tankers</h3>
            <p>Each dot is one tanker load leaving the station, in the order the plan sends them. Red and amber go first; then the green fair turns go round the sections like cards dealt round a table: everyone gets a turn before anyone gets a second one, and a section with more need gets a bigger turn.</p></div>
          <label className="plan-rr-pick">Station <select value={station ?? ""} onChange={(e) => setStation(e.target.value)}>
            {options.map((s) => { const n = Object.values(s.bookings).reduce((a, b) => a + b, 0); return <option key={s.station} value={s.station}>{s.station} · {Object.keys(s.bookings).length} sections · {n} bookings · {s.served.length} trips</option>; })}
          </select></label>
        </div>
        {queue ? <StationQueuePlayer key={queue.station} queue={queue} names={names} /> : <p className="plan-empty">No station has bookings in this plan.</p>}
        <div className="plan-rr-legend">{TIER.map((t) => <span key={t.label}><i style={{ background: t.colour }} />{t.label}</span>)}<span><i className="ring" />Ring fills as a section's bookings are served</span></div>
      </div>
    </section>
  );
}
