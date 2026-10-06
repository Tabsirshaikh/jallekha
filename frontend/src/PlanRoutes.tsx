import { useMemo, useState } from "react";
import { useApi } from "./useApi";
import { HEIGHT, WIDTH, pathOf, project, wardFeatures, type Feature } from "./mapGeo";
import sectionGeometry from "./data/u5SectionGeometry.json";
import sectionEvidence from "./data/u5SectionEvidence.json";
import "./PlanRoutes.css";

// Tanker routes of a plan by section (GET /plans/{id}/routes): the day's tankers, who drives where
// and when, drawn from the filling station to each section it serves. English only for now.

type Trip = { n: number; kind: string; group: string; name: string; booking_id: string | null; lat: number | null; lng: number | null; depart: string; arrive: string; unloaded: string; back: string; km: number; minutes: number; leg_basis: string };
type Tanker = { tanker_id: string; station_id: string; trips: Trip[]; km: number; finish: string; sections_reached: number };
type StationRow = { station_id: string; lat: number; lng: number; tankers: number; tankers_used: number; capacity_trips: number; trips: number; special_trips: number; km: number; finish: string | null; unscheduled: number };
type Summary = { tankers: number; fleet: number; stations: number; trips: number; special_trips: number; unscheduled: number; total_km: number; sections_reached: number; legs_estimated: number; latest_finish: string | null; average_trips_per_tanker: number };
type Routes = { summary: Summary; stations: StationRow[]; tankers: Tanker[]; unscheduled: { kind: string; name: string; reason: string; station_id: string }[]; unscheduled_total: number; basis: Record<string, string> };

const COLOUR: Record<string, string> = { booked: "#1f7560", scheduled: "#c9783f", outage: "#2f6fb0", critical: "#c4473a" };
const KIND: Record<string, string> = { booked: "Booked", scheduled: "Scheduled supply (F9)", outage: "Outage (F10)", critical: "Critical facility (F10)" };
const nf = new Intl.NumberFormat("en", { maximumFractionDigits: 0 });
const sectionShapes = (sectionGeometry as unknown as { features: Feature[] }).features.map((f) => ({ id: f.properties.ward_id, d: pathOf(f) }));
const sectionName = new Map((sectionEvidence as unknown as { wards: { id: string; name: string }[] }).wards.map((w) => [w.id, w.name]));

export default function PlanRoutes({ planId }: { planId: string }) {
  const [station, setStation] = useState<string | null>(null);
  const [tanker, setTanker] = useState<string | null>(null);
  const [showAll, setShowAll] = useState(false);
  const base = `/plans/${encodeURIComponent(planId)}/routes`;
  const overview = useApi<Routes>(base);
  const detail = useApi<Routes>(station ? `${base}?station=${encodeURIComponent(station)}` : null);
  const data = overview.live ? overview.data : null;
  const chosen = station && detail.live ? detail.data : null;

  const tankers = useMemo(() => chosen?.tankers ?? [], [chosen]);
  const current = tankers.find((t) => t.tanker_id === tanker) ?? null;
  const stationRow = data?.stations.find((s) => s.station_id === station) ?? null;
  const base_paths = useMemo(() => wardFeatures.map((f) => pathOf(f)), []);
  // Sections this station serves (all its tankers), and the ones the chosen tanker visits.
  const served = useMemo(() => new Set(tankers.flatMap((t) => t.trips.map((x) => x.group.replace(/^section:/, "")))), [tankers]);
  const visited = useMemo(() => new Set((current?.trips ?? []).map((x) => x.group.replace(/^section:/, ""))), [current]);

  if (overview.loading) return <section className="plan-panel"><p className="plan-empty" role="status">Working out the tanker routes…</p></section>;
  if (!data) return <section className="plan-panel"><p className="plan-message error" role="alert">The tanker routes could not be loaded.</p></section>;
  const s = data.summary;
  const stations = showAll ? data.stations : data.stations.slice(0, 10);

  return (
    <section className="plan-panel plan-routes" aria-labelledby="plan-routes-title">
      <div className="plan-panel-title"><div><p className="eyebrow">Routes</p><h2 id="plan-routes-title">Tankers on the road</h2></div></div>
      <p className="plan-threshold">Each booking is one tanker load, so a trip goes from the filling station to the section and back. Loads leave in priority order: critical facilities, cut sections, scheduled supply, then the booked queue. {nf.format(s.legs_estimated)} of {nf.format(s.trips)} trips use a straight-line estimate of the road because OSRM distances were not built for that place.</p>
      <div className="plan-summary">
        <article><span>Tankers on the road</span><strong>{nf.format(s.tankers)}</strong><small>of a fleet of {nf.format(s.fleet)}</small></article>
        <article><span>Trips</span><strong>{nf.format(s.trips)}</strong><small>{nf.format(s.special_trips)} for scheduled supply or outages</small></article>
        <article><span>Distance driven</span><strong>{nf.format(s.total_km)} km</strong><small>{s.average_trips_per_tanker} trips per tanker</small></article>
        <article><span>Last tanker back</span><strong>{s.latest_finish ?? "—"}</strong><small>{nf.format(s.sections_reached)} sections reached{s.unscheduled > 0 ? ` · ${nf.format(s.unscheduled)} loads do not fit the day` : ""}</small></article>
      </div>

      <div className="plan-routes-grid">
        <div className="plan-routes-side">
          <h3>Filling stations</h3>
          <table className="plan-routes-table">
            <thead><tr><th>Station</th><th>Tankers</th><th>Trips</th><th>km</th><th>Back by</th></tr></thead>
            <tbody>{stations.map((r) => <tr key={r.station_id} className={r.station_id === station ? "selected" : ""}>
              <td><button onClick={() => { setStation(r.station_id); setTanker(null); }}>{r.station_id}</button></td>
              <td>{r.tankers_used}</td><td>{nf.format(r.trips)}</td><td>{nf.format(r.km)}</td><td>{r.finish ?? "—"}{r.unscheduled > 0 ? ` (${r.unscheduled} left)` : ""}</td></tr>)}</tbody>
          </table>
          <button className="text-button" onClick={() => setShowAll(!showAll)}>{showAll ? "Show fewer" : `Show all ${data.stations.length} stations`}</button>
        </div>

        <div className="plan-routes-map">
          <svg viewBox={`-10 -10 ${WIDTH + 20} ${HEIGHT + 20}`} role="group" aria-label="Tanker routes map">
            {base_paths.map((d, i) => <path key={i} d={d} fill="#f1f3f0" stroke="#fff" strokeWidth="1" vectorEffect="non-scaling-stroke" />)}
            {sectionShapes.map(({ id, d }) => {
              const name = sectionName.get(id) ?? "";
              if (!served.has(name)) return null;
              return <path key={"s" + id} d={d} fill={visited.has(name) ? "#1f7560" : "#86c2a8"} fillOpacity={visited.has(name) ? 0.55 : 0.4} stroke="#fff" strokeWidth="1" vectorEffect="non-scaling-stroke"><title>{name}</title></path>;
            })}
            {tankers.flatMap((t) => (current && t.tanker_id !== current.tanker_id ? t.trips : []).map((trip, i) => {
              if (trip.lat === null || trip.lng === null || !stationRow) return null;
              const [x1, y1] = project([stationRow.lng, stationRow.lat]);
              const [x2, y2] = project([trip.lng, trip.lat]);
              return <line key={t.tanker_id + i} x1={x1} y1={y1} x2={x2} y2={y2} stroke={COLOUR[trip.kind]} strokeOpacity="0.35" strokeWidth="1.2" vectorEffect="non-scaling-stroke" />;
            }))}
            {!current && tankers.flatMap((t) => t.trips.map((trip, i) => {
              if (trip.lat === null || trip.lng === null || !stationRow) return null;
              const [x1, y1] = project([stationRow.lng, stationRow.lat]);
              const [x2, y2] = project([trip.lng, trip.lat]);
              return <line key={"a" + t.tanker_id + i} x1={x1} y1={y1} x2={x2} y2={y2} stroke={COLOUR[trip.kind]} strokeOpacity="0.45" strokeWidth="1.4" vectorEffect="non-scaling-stroke" />;
            }))}
            {current && stationRow && current.trips.map((trip) => {
              if (trip.lat === null || trip.lng === null) return null;
              const [x1, y1] = project([stationRow.lng, stationRow.lat]);
              const [x2, y2] = project([trip.lng, trip.lat]);
              return <g key={trip.n}><line x1={x1} y1={y1} x2={x2} y2={y2} stroke={COLOUR[trip.kind]} strokeWidth="2.6" vectorEffect="non-scaling-stroke" /><circle cx={x2} cy={y2} r="9" fill={COLOUR[trip.kind]} stroke="#fff" /><text x={x2} y={y2 + 4} textAnchor="middle" className="plan-routes-n">{trip.n}</text></g>;
            })}
            {data.stations.map((r) => {
              const [x, y] = project([r.lng, r.lat]);
              return <circle key={r.station_id} cx={x} cy={y} r={r.station_id === station ? 9 : 4.5} fill={r.station_id === station ? "#0d4c43" : "#2b3a37"} stroke="#fff" strokeWidth="1.5" role="button" tabIndex={0} aria-label={`Station ${r.station_id}`} style={{ cursor: "pointer" }}
                onClick={() => { setStation(r.station_id); setTanker(null); }} onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); setStation(r.station_id); setTanker(null); } }}><title>{`${r.station_id}: ${r.tankers_used} tankers, ${r.trips} trips`}</title></circle>;
            })}
          </svg>
          <div className="plan-routes-legend">{Object.entries(COLOUR).map(([k, c]) => <span key={k}><i style={{ background: c }} />{KIND[k]}</span>)}<span><i className="area" />Sections this station serves</span><span><i className="dot" />Filling station (stand-in position)</span></div>
        </div>
      </div>

      {!station && <p className="plan-empty">Pick a filling station (in the table or on the map) to see its tankers and where each one goes.</p>}
      {station && detail.loading && <p className="plan-empty" role="status">Loading the tankers of {station}…</p>}
      {station && chosen && <div className="plan-routes-detail">
        <h3>{station}: {tankers.length} tankers, {nf.format(stationRow?.trips ?? 0)} trips</h3>
        <div className="plan-routes-tankers" role="list">{tankers.map((t) => <button key={t.tanker_id} role="listitem" className={t.tanker_id === tanker ? "active" : ""} onClick={() => setTanker(t.tanker_id === tanker ? null : t.tanker_id)}>
          <strong>{t.tanker_id}</strong><span>{t.trips.length} trips · {t.sections_reached} sections · {nf.format(t.km)} km · back {t.finish}</span></button>)}</div>
        {current && <table className="plan-routes-table plan-routes-trips">
          <thead><tr><th>#</th><th>Leaves</th><th>Arrives</th><th>Back</th><th>Goes to</th><th>Kind</th><th>km</th></tr></thead>
          <tbody>{current.trips.map((trip) => <tr key={trip.n}><td>{trip.n}</td><td>{trip.depart}</td><td>{trip.arrive}</td><td>{trip.back}</td><td>{trip.name}</td><td><span style={{ color: COLOUR[trip.kind] }}>{KIND[trip.kind]}</span></td><td>{trip.km}{trip.leg_basis === "OSRM" ? "" : " (est.)"}</td></tr>)}</tbody>
        </table>}
        {!current && <p className="muted small">Pick a tanker to see its day and its trips numbered on the map.</p>}
      </div>}
      <p className="muted small">{data.basis.legs}. {data.basis.times}. Station positions are stand-ins (HMWSSB publishes none), so distances are between assumed places.</p>
    </section>
  );
}
