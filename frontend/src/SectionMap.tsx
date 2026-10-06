import { useMemo, useState } from "react";
import sectionData from "./data/u5Sections.json";

// Section map (feat/section-need-map). Each section is an approximate area (Voronoi cell of its
// point, not an HMWSSB boundary). Bookings and connections are exact per section; need is the
// ward Census need carried onto the section by building share (scripts/evidence/build_section_map.py).
// English only for now (owner decision); the ward map keeps its four languages.

type Ring = [number, number][];
type SectionItem = {
  section_id: string;
  section: string;
  division: string;
  bookings: number;
  connections: number | null;
  rate: number | null;
  peer_rate: number | null;
  expected: number | null;
  ratio: number | null;
  peers: string[];
  flagged: boolean;
  status: string;
  need: { need_weight: number; wad: number; cad: number; hardship: number } | null;
  outline: Ring[];
};
type Layer = "need" | "wad" | "cad" | "hardship" | "bookings" | "ratio";

const items = (sectionData as { items: SectionItem[] }).items;
const SCALE = ["#e3f1ea", "#b9dccb", "#86c2a8", "#4f9e83", "#1f7560"];
const NO_DATA = "#eceeeb";
const FLAG = "#c4473a";

const LAYERS: { id: Layer; label: string; help: string }[] = [
  { id: "need", label: "Water need", help: "One score per section: 1 + 2 x homes fetching water from outside + homes with no phone + hardship. Census 2011, carried from the wards the section covers." },
  { id: "wad", label: "Fetch water outside", help: "Share of homes fetching water from outside the premises (Census 2011, from nearby wards)." },
  { id: "cad", label: "No phone", help: "Share of homes with no phone, who cannot book a tanker (Census 2011, from nearby wards)." },
  { id: "hardship", label: "Hardship", help: "Share of homes in hardship (Census 2011, from nearby wards)." },
  { id: "bookings", label: "Bookings", help: "Tankers booked in 2025 per 1,000 domestic connections. Darker means more bookings per connection." },
  { id: "ratio", label: "Booked vs similar sections", help: "How much a section booked compared with what similar sections book. Lighter means fewer bookings than similar sections." },
];

const nf = new Intl.NumberFormat("en", { maximumFractionDigits: 1 });
const n0 = new Intl.NumberFormat("en", { maximumFractionDigits: 0 });
const pct = (v: number) => `${n0.format(v * 100)}%`;

function metric(s: SectionItem, layer: Layer): number | null {
  if (layer === "bookings") return s.rate;
  if (layer === "ratio") return s.ratio;
  return s.need ? (layer === "need" ? s.need.need_weight : s.need[layer]) : null;
}

function classes(values: (number | null)[]) {
  const sorted = values.filter((v): v is number => v !== null).sort((a, b) => a - b);
  const cuts = [1, 2, 3, 4].map((k) => sorted[Math.floor((sorted.length * k) / 5)] ?? Infinity);
  return (v: number | null) => (v === null ? null : cuts.filter((c) => v >= c).length);
}

function verdict(s: SectionItem): { text: string; tone: "flag" | "plain" } {
  if (s.ratio === null || s.expected === null) return { text: "Not enough data to compare this section with similar ones.", tone: "plain" };
  const share = s.ratio;
  if (s.flagged) return { text: `Far fewer bookings than similar sections (${pct(share)} of what they book), in an area with high water need. Worth a visit to see whether people can book.`, tone: "flag" };
  if (share < 0.5) return { text: `Fewer bookings than similar sections (${pct(share)} of what they book), but not flagged: the area's need is not above the cohort's.`, tone: "plain" };
  if (share < 0.9) return { text: `A bit lower than similar sections (${pct(share)}), but not low enough to flag.`, tone: "plain" };
  if (share <= 1.5) return { text: "In line with similar sections.", tone: "plain" };
  return { text: `More bookings than similar sections (${pct(share)} of what they book).`, tone: "plain" };
}

export default function SectionMap() {
  const [layer, setLayer] = useState<Layer>("need");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [hover, setHover] = useState<string | null>(null);
  const [zoom, setZoom] = useState<{ x: number; y: number; w: number } | null>(null);
  const [query, setQuery] = useState("");

  const drawn = useMemo(() => items.filter((s) => s.outline.length > 0), []);
  const view = useMemo(() => {
    const pts = drawn.flatMap((s) => s.outline.flat());
    const xs = pts.map((p) => p[0]), ys = pts.map((p) => p[1]);
    const minX = Math.min(...xs), maxX = Math.max(...xs), minY = Math.min(...ys), maxY = Math.max(...ys);
    const k = Math.cos((((minY + maxY) / 2) * Math.PI) / 180);
    const width = 1000, height = Math.round((width * (maxY - minY)) / ((maxX - minX) * k));
    const project = ([x, y]: [number, number]) => `${(((x - minX) / (maxX - minX)) * width).toFixed(1)},${(((maxY - y) / (maxY - minY)) * height).toFixed(1)}`;
    return { width, height, paths: new Map(drawn.map((s) => [s.section_id, s.outline.map((r) => "M" + r.map(project).join("L") + "Z").join("")])) };
  }, [drawn]);

  const scaleOf = useMemo(() => classes(items.map((s) => metric(s, layer))), [layer]);
  const colour = (s: SectionItem) => {
    const c = scaleOf(metric(s, layer));
    return c === null ? NO_DATA : SCALE[c];
  };

  const full = view.width + 20, fullH = view.height + 20;
  const box = zoom ?? { x: -10, y: -10, w: full };
  const boxH = (box.w * fullH) / full;
  const selected = items.find((s) => s.section_id === selectedId) ?? null;
  const centre = (): [number, number] => {
    const d = selectedId ? view.paths.get(selectedId) : undefined;
    const nums = d ? (d.match(/-?\d+(\.\d+)?/g) ?? []).map(Number) : [];
    if (nums.length < 2) return [box.x + box.w / 2, box.y + boxH / 2];
    const xs = nums.filter((_, i) => i % 2 === 0), ys = nums.filter((_, i) => i % 2 === 1);
    return [(Math.min(...xs) + Math.max(...xs)) / 2, (Math.min(...ys) + Math.max(...ys)) / 2];
  };
  const zoomBy = (factor: number) => {
    const w2 = Math.min(full, Math.max(80, box.w * factor));
    if (w2 >= full) { setZoom(null); return; }
    const h2 = (w2 * fullH) / full;
    const [cx, cy] = centre();
    setZoom({ x: Math.min(Math.max(cx - w2 / 2, -10), full - 10 - w2), y: Math.min(Math.max(cy - h2 / 2, -10), fullH - 10 - h2), w: w2 });
  };

  const found = query.trim() ? items.filter((s) => s.section.toLowerCase().includes(query.trim().toLowerCase())).slice(0, 6) : [];
  const flagged = items.filter((s) => s.flagged);
  const chosen = LAYERS.find((l) => l.id === layer)!;
  const hovered = items.find((s) => s.section_id === hover);
  const undrawn = items.length - drawn.length;

  return (
    <div className="atlas-page">
      <header className="atlas-head">
        <div><h1>Sections map</h1><p className="muted">Each area is an HMWSSB section. Bookings and connections are exact per section; the shape of each area and its need are estimates.</p></div>
        <div className="atlas-search">
          <input aria-label="Find a section" placeholder="Find a section" value={query} onChange={(e) => setQuery(e.target.value)} />
          {query.trim() && <ul>{found.length ? found.map((s) => <li key={s.section_id}><button onClick={() => { setSelectedId(s.section_id); setQuery(""); }}>{s.section}</button></li>) : <li className="muted">No section found</li>}</ul>}
        </div>
      </header>

      <div className="atlas-toolbar">
        <div className="atlas-chips" role="radiogroup">{LAYERS.map((l) => <button key={l.id} role="radio" aria-checked={layer === l.id} className={layer === l.id ? "active" : ""} onClick={() => setLayer(l.id)}>{l.label}</button>)}</div>
        <p className="atlas-help">{chosen.help}</p>
        <p className="atlas-stat"><strong>{flagged.length}</strong> sections flagged for a field visit (red outline)</p>
      </div>

      <section className="atlas-stage">
        <svg className="atlas-map" viewBox={`${box.x} ${box.y} ${box.w} ${boxH}`} role="group" aria-label="Sections map">
          {drawn.map((s) => (
            <path key={s.section_id} d={view.paths.get(s.section_id)} fill={colour(s)} role="button" tabIndex={0} aria-label={s.section}
              className={(selectedId === s.section_id ? "selected " : "") + (hover === s.section_id ? "hover" : "")}
              style={s.flagged && selectedId !== s.section_id ? { stroke: FLAG, strokeWidth: 2.5 } : undefined}
              onClick={() => setSelectedId(s.section_id)} onMouseEnter={() => setHover(s.section_id)} onMouseLeave={() => setHover(null)}
              onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); setSelectedId(s.section_id); } }}><title>{s.section}</title></path>
          ))}
        </svg>
        <div className="atlas-overlay atlas-zoom"><button aria-label="Zoom in" title="Zoom in" onClick={() => zoomBy(0.7)}>+</button><button aria-label="Zoom out" title="Zoom out" onClick={() => zoomBy(1.4)}>−</button><button aria-label="Reset zoom" title="Reset zoom" onClick={() => setZoom(null)}>⤢</button></div>
        {hovered && <div className="atlas-tooltip">{hovered.section}</div>}
        <div className="atlas-overlay atlas-legend"><span>Less</span>{SCALE.map((c) => <i key={c} style={{ background: c }} />)}<span>More</span><i style={{ background: NO_DATA }} /><span>No data</span></div>
      </section>
      <p className="muted small">{undrawn} of {items.length} sections are not drawn because no usable location was found. Section areas are approximate, not official boundaries.</p>

      {selected && <section className="atlas-sheet" role="dialog" aria-label={selected.section}>
        <header><div><h2>{selected.section}</h2><span className={"atlas-pill " + (selected.flagged ? "bad" : "ok")}>{selected.flagged ? "Flagged for a field visit" : "Not flagged"}</span></div><button className="atlas-close" aria-label="Close" onClick={() => setSelectedId(null)}>×</button></header>
        <div className="atlas-sheet-grid">
          <div><h3>Need (Census 2011, estimated for this area)</h3>
            {selected.need ? <dl className="atlas-facts">
              <div><dt>Water need score</dt><dd>{selected.need.need_weight.toFixed(2)}</dd></div>
              <div><dt>Homes fetching water from outside</dt><dd>{pct(selected.need.wad)}</dd></div>
              <div><dt>Homes with no phone (cannot book)</dt><dd>{pct(selected.need.cad)}</dd></div>
              <div><dt>Homes in hardship</dt><dd>{pct(selected.need.hardship)}</dd></div>
              <div><dt>Domestic connections</dt><dd>{selected.connections === null ? "—" : n0.format(selected.connections)}</dd></div>
              <div><dt>Division</dt><dd>{selected.division}</dd></div>
            </dl> : <p className="muted">No need estimate: this section has no usable location or building data.</p>}
          </div>
          <div><h3>Booking check (2025)</h3>
            <div className="atlas-bars">
              <p>Booked {n0.format(selected.bookings)} tankers in 2025</p>
              <div className="atlas-bar"><i className="seen" style={{ width: `${Math.max(1, (selected.bookings / Math.max(selected.bookings, selected.expected ?? 0, 1)) * 100)}%` }} /></div>
              {selected.expected !== null && <>
                <p>Similar sections book about {nf.format((selected.peer_rate ?? 0) / 1000)} per connection, so about {n0.format(selected.expected)} here</p>
                <div className="atlas-bar"><i className="peer" style={{ width: `${Math.max(1, (selected.expected / Math.max(selected.bookings, selected.expected, 1)) * 100)}%` }} /></div>
              </>}
              <p className={"atlas-verdict " + verdict(selected).tone}>{verdict(selected).text}</p>
            </div>
          </div>
          <div><h3>Similar sections</h3>
            {selected.peers.length > 0 ? <ul className="atlas-clues">{selected.peers.map((p) => <li key={p} className="info">{p}</li>)}</ul> : <p className="muted">None found.</p>}
            <p className="muted small">Same division, similar number of connections and flats. Not yet checked on the ground.</p>
          </div>
        </div>
      </section>}

    </div>
  );
}
