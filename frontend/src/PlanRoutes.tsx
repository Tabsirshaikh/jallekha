import { memo, useEffect, useMemo, useRef, useState } from "react";
import { useApi } from "./useApi";
import { HEIGHT, WIDTH, project, sectionShapes, shapeByGroup, wardShapes } from "./mapGeo";
import { KIND, KINDS } from "./planColours";
import { FILL, clock, minute, spotAt, type Leg, type Spot } from "./routePlay";
import "./PlanRoutes.css";

// Tanker routes of a plan by section (GET /plans/{id}/routes): the day of every tanker played on
// the map. The whole city first; click a filling station to zoom in on its tankers, then a tanker
// for its numbered route and the driver's route sheet. English only for now.

type Trip = { n: number; kind: string; group: string; name: string; booking_id: string | null; lat: number | null; lng: number | null; depart: string; arrive: string; unloaded: string; back: string; km: number; minutes: number; leg_basis: string };
type Tanker = { tanker_id: string; station_id: string; trips: Trip[]; km: number; finish: string; sections_reached: number };
type StationRow = { station_id: string; lat: number; lng: number; tankers: number; tankers_used: number; capacity_trips: number; trips: number; special_trips: number; km: number; finish: string | null; unscheduled: number };
type Summary = { tankers: number; fleet: number; stations: number; trips: number; special_trips: number; unscheduled: number; total_km: number; sections_reached: number; legs_estimated: number; latest_finish: string | null; average_trips_per_tanker: number };
/** [lat, lng, depart, arrive, unloaded, back, kind] in minutes after midnight (compact_paths). */
type Compact = [number, number, number, number, number, number, number];
type Path = { tanker_id: string; station_id: string; trips: Compact[] };
type Routes = { day: string; summary: Summary; stations: StationRow[]; tankers: Tanker[]; paths: Path[] | null; unscheduled: { kind: string; name: string; reason: string; station_id: string }[]; unscheduled_total: number; basis: Record<string, string> };
type Box = { x: number; y: number; w: number; h: number };
/** Stops drivers confirmed in local test mode (GET /driver/visits, SIMULATION). */
type Visits = { plan_id: string; items: { tanker_id: string; n: number; visited_at: string }[] };
type Seen = Map<string, Map<number, string>>;

const nf = new Intl.NumberFormat("en", { maximumFractionDigits: 0 });
const DAY_START = 6 * 60, DAY_END = 22 * 60;
const CITY: Box = { x: -10, y: -10, w: WIDTH + 20, h: HEIGHT + 20 };

/** Where a trip is drawn: the middle of its section (the home is somewhere inside it), else its point. */
function placeOf(trip: Trip): [number, number] | null {
  if (trip.kind !== "critical") { const shape = shapeByGroup.get(trip.group); if (shape) return shape.centre; }
  return trip.lat !== null && trip.lng !== null ? project([trip.lng, trip.lat]) : null;
}

function legsOf(t: Tanker): Leg[] {
  return t.trips.flatMap((x) => {
    const at = placeOf(x);
    return at ? [{ x: at[0], y: at[1], dep: minute(x.depart), arr: minute(x.arrive), unl: minute(x.unloaded), back: minute(x.back), kind: Math.max(0, KINDS.indexOf(x.kind as (typeof KINDS)[number])) }] : [];
  });
}
const legsOfCompact = (trips: Compact[]): Leg[] => trips.map(([lat, lng, dep, arr, unl, back, kind]) => { const [x, y] = project([lng, lat]); return { x, y, dep, arr, unl, back, kind }; });

/** "MADHAPUR -2|2025-05-14|322" -> "booking 322 of 14 May" (the id says the day it was made). */
function bookingLabel(id: string | null): string {
  const m = id?.match(/\|(\d{4})-(\d{2})-(\d{2})\|(\d+)$/);
  if (!m) return id ? `booking ${id}` : "";
  const month = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"][Number(m[2]) - 1];
  return `booking ${m[4]} of ${Number(m[3])} ${month}`;
}

/** A viewBox that glides to its target. */
function useGlide(target: Box): Box {
  const [box, setBox] = useState(target);
  const from = useRef(target);
  useEffect(() => {
    const start = performance.now();
    const a = from.current;
    let raf = 0;
    const tick = (now: number) => {
      const f = Math.min(1, (now - start) / 450);
      const e = 1 - Math.pow(1 - f, 3);
      const next = { x: a.x + (target.x - a.x) * e, y: a.y + (target.y - a.y) * e, w: a.w + (target.w - a.w) * e, h: a.h + (target.h - a.h) * e };
      from.current = next;
      setBox(next);
      if (f < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [target]);
  return box;
}

/** The map underneath: wards for context, sections the chosen station serves highlighted. */
const BaseMap = memo(function BaseMap({ served, visited }: { served: Set<string>; visited: Set<string> }) {
  return <g>
    {wardShapes.map((w) => <path key={w.id} d={w.d} className="plan-routes-ward" />)}
    {sectionShapes.map((s) => served.has(s.group) || visited.has(s.group)
      ? <path key={s.id} d={s.d} className={visited.has(s.group) ? "plan-routes-section visited" : "plan-routes-section"}><title>{s.name}</title></path>
      : null)}
  </g>;
});

function Player({ minuteNow, setMinute, playing, setPlaying, speed, setSpeed }: { minuteNow: number; setMinute: (m: number) => void; playing: boolean; setPlaying: (p: boolean) => void; speed: number; setSpeed: (s: number) => void }) {
  return <div className="plan-routes-player">
    <button className="button button-primary" onClick={() => { if (minuteNow >= DAY_END) setMinute(DAY_START); setPlaying(!playing); }}>{playing ? "⏸ Pause" : minuteNow >= DAY_END ? "↺ Play the day again" : "▶ Play the day"}</button>
    <span className="plan-routes-clock" aria-live="off">{clock(minuteNow)}</span>
    <input type="range" min={DAY_START} max={DAY_END} step={1} value={minuteNow} aria-label="Time of day" onChange={(e) => { setPlaying(false); setMinute(Number(e.target.value)); }} />
    <label>Speed <select value={speed} onChange={(e) => setSpeed(Number(e.target.value))}><option value={10}>slow</option><option value={25}>normal</option><option value={60}>fast</option></select></label>
  </div>;
}

export default function PlanRoutes({ planId }: { planId: string }) {
  const [station, setStation] = useState<string | null>(null);
  const [tanker, setTanker] = useState<string | null>(null);
  const [now, setNow] = useState(8 * 60);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(25); // minutes of the day per second
  const base = `/plans/${encodeURIComponent(planId)}/routes`;
  const overview = useApi<Routes>(`${base}?compact=true`);
  const detail = useApi<Routes>(station ? `${base}?station=${encodeURIComponent(station)}` : null);
  const data = overview.live ? overview.data : null;
  const chosen = station && detail.live ? detail.data : null;
  // what drivers confirmed (local test mode only; elsewhere this answers 404 and nothing shows)
  const visitsApi = useApi<Visits>(data ? `/driver/visits?day=${data.day}` : null);
  const reloadVisits = visitsApi.reload;
  useEffect(() => { if (!data) return; const id = setInterval(reloadVisits, 10000); return () => clearInterval(id); }, [data, reloadVisits]);
  const [visits, setVisits] = useState<Visits | null>(null);
  if (visitsApi.data && visitsApi.data !== visits) setVisits(visitsApi.data);
  const seen: Seen = useMemo(() => {
    const m: Seen = new Map();
    if (visits && visits.plan_id === planId) for (const v of visits.items) { const t = m.get(v.tanker_id) ?? new Map<number, string>(); t.set(v.n, v.visited_at); m.set(v.tanker_id, t); }
    return m;
  }, [visits, planId]);
  const confirmed = [...seen.values()].reduce((sum, t) => sum + t.size, 0);

  // the clock
  useEffect(() => {
    if (!playing) return;
    let raf = 0, last = performance.now();
    const tick = (t: number) => {
      const dt = (t - last) / 1000;
      last = t;
      setNow((m) => { const next = m + dt * speed; if (next >= DAY_END) { setPlaying(false); return DAY_END; } return next; });
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [playing, speed]);

  const stationXY = useMemo(() => new Map((data?.stations ?? []).map((s) => [s.station_id, project([s.lng, s.lat])])), [data]);
  const tankers = useMemo(() => chosen?.tankers ?? [], [chosen]);
  const current = tankers.find((t) => t.tanker_id === tanker) ?? null;
  const stationRow = data?.stations.find((s) => s.station_id === station) ?? null;
  const served = useMemo(() => new Set(tankers.flatMap((t) => t.trips.map((x) => x.group))), [tankers]);
  const visited = useMemo(() => new Set((current?.trips ?? []).map((x) => x.group)), [current]);

  // what moves: every tanker of the city, or the chosen station's
  const movers = useMemo(() => {
    if (station && chosen) return tankers.map((t) => ({ id: t.tanker_id, home: stationXY.get(t.station_id) ?? [0, 0] as [number, number], legs: legsOf(t) }));
    return (data?.paths ?? []).map((p) => ({ id: p.tanker_id, home: stationXY.get(p.station_id) ?? [0, 0] as [number, number], legs: legsOfCompact(p.trips) }));
  }, [station, chosen, tankers, data, stationXY]);

  const target = useMemo<Box>(() => {
    if (!station || !stationRow) return CITY;
    const pts: [number, number][] = [project([stationRow.lng, stationRow.lat])];
    for (const t of tankers) for (const x of t.trips) { const at = placeOf(x); if (at) pts.push(at); }
    const xs = pts.map((p) => p[0]), ys = pts.map((p) => p[1]);
    let x0 = Math.min(...xs), x1 = Math.max(...xs), y0 = Math.min(...ys), y1 = Math.max(...ys);
    const pad = Math.max(60 - (x1 - x0) / 2, 60 - (y1 - y0) / 2, 0.2 * Math.max(x1 - x0, y1 - y0), 25);
    x0 -= pad; x1 += pad; y0 -= pad; y1 += pad;
    // keep the map's shape so it does not stretch
    const ratio = CITY.w / CITY.h;
    let w = x1 - x0, h = y1 - y0;
    if (w / h < ratio) { const nw = h * ratio; x0 -= (nw - w) / 2; w = nw; } else { const nh = w / ratio; y0 -= (nh - h) / 2; h = nh; }
    return { x: x0, y: y0, w, h };
  }, [station, stationRow, tankers]);
  const box = useGlide(target);
  const k = box.w / CITY.w; // drawing units per screen unit: keeps dots the same size when zoomed

  if (overview.loading) return <section className="plan-panel"><p className="plan-empty" role="status">Working out the tanker routes…</p></section>;
  if (!data) return <section className="plan-panel"><p className="plan-message error" role="alert">The tanker routes could not be loaded.</p></section>;
  const s = data.summary;

  const spots = movers.map((m) => ({ id: m.id, spot: spotAt(m.legs, m.home, now) })).filter((x) => x.spot !== null) as { id: string; spot: Spot }[];
  const onRoad = spots.filter((x) => x.spot.state !== "fill").length;
  const filling = spots.length - onRoad;
  const delivered = movers.reduce((sum, m) => sum + m.legs.filter((l) => l.arr <= now).length, 0);
  const totalLegs = movers.reduce((sum, m) => sum + m.legs.length, 0);
  const pick = (id: string | null) => { setStation(id); setTanker(null); };

  // destinations of the chosen station: one spoke per place, numbered for the chosen tanker
  const places = new Map<string, { x: number; y: number; kind: string; trips: number; name: string; nums: number[]; seen: number }>();
  if (station && stationRow) for (const t of tankers) for (const x of t.trips) {
    const at = placeOf(x);
    if (!at) continue;
    const key = `${x.kind}:${at[0].toFixed(1)},${at[1].toFixed(1)}`;
    const p = places.get(key) ?? { x: at[0], y: at[1], kind: x.kind, trips: 0, name: x.name, nums: [], seen: 0 };
    p.trips += 1;
    if (t.tanker_id === tanker) { p.nums.push(x.n); if (seen.get(t.tanker_id)?.has(x.n)) p.seen += 1; }
    places.set(key, p);
  }
  const home = stationRow ? project([stationRow.lng, stationRow.lat]) : null;
  const topStations = data.stations.slice(0, 12);

  return (
    <section className="plan-panel plan-routes" aria-labelledby="plan-routes-title">
      <div className="plan-panel-title"><div><p className="eyebrow">Routes</p><h2 id="plan-routes-title">Tankers on the road</h2></div></div>
      <div className="plan-routes-stats">
        <div><strong>{nf.format(s.tankers)}</strong><span>tankers out, of {nf.format(s.fleet)}</span></div>
        <div><strong>{nf.format(s.trips)}</strong><span>trips ({nf.format(s.special_trips)} without booking)</span></div>
        <div><strong>{s.average_trips_per_tanker}</strong><span>trips per tanker</span></div>
        <div><strong>{nf.format(s.total_km)} km</strong><span>driven in all</span></div>
        <div><strong>{s.latest_finish ?? "—"}</strong><span>last tanker back</span></div>
      </div>
      <ol className="plan-routes-how" aria-label="How a tanker's day works">
        <li><b>Fill</b><span>at its filling station (about {FILL} min)</span></li>
        <li><b>Drive</b><span>to the section and empty the tank at the home (about 30 min)</span></li>
        <li><b>Come back</b><span>and fill again for the next booking</span></li>
      </ol>
      <p className="plan-threshold">One booking fills a whole tanker (5,000 litres) for one home, so a tanker returns to refill after every delivery. A driver's route is the day's loop: station → section → station → next section. The plan sends the most urgent loads in the first round and gives each load to the tanker that is free first, so no tanker stands idle while bookings wait.</p>

      <Player minuteNow={now} setMinute={setNow} playing={playing} setPlaying={setPlaying} speed={speed} setSpeed={setSpeed} />
      <div className="plan-routes-grid">
        <div className="plan-routes-map">
          <svg viewBox={`${box.x} ${box.y} ${box.w} ${box.h}`} role="group" aria-label={station ? `Tankers of station ${station}` : "Tankers of the whole city"}>
            <BaseMap served={served} visited={visited} />
            {home && [...places.values()].map((p, i) => {
              const dim = tanker !== null && p.nums.length === 0;
              return <line key={"sp" + i} x1={home[0]} y1={home[1]} x2={p.x} y2={p.y} stroke={KIND[p.kind]?.colour ?? "#1f7560"} strokeOpacity={dim ? 0.15 : 0.55} strokeWidth={tanker && !dim ? 3 : 1 + Math.min(3, p.trips / 4)} vectorEffect="non-scaling-stroke" />;
            })}
            {home && [...places.values()].map((p, i) => <text key={"t" + i} x={p.x} y={p.y + 22 * k} textAnchor="middle" fontSize={11 * k} className="plan-routes-label">{p.name}</text>)}
            {home && [...places.values()].filter((p) => p.nums.length > 0).map((p, i) => <g key={"n" + i}>
              <circle cx={p.x} cy={p.y} r={11 * k} fill={p.seen === p.nums.length ? "#1f6046" : KIND[p.kind]?.colour ?? "#1f7560"} stroke="#fff" strokeWidth={1.5} vectorEffect="non-scaling-stroke" />
              <text x={p.x} y={p.y + 4 * k} textAnchor="middle" fontSize={11 * k} className="plan-routes-n">{p.seen === p.nums.length ? "✓" : p.nums.join(",")}</text>
              <title>{`${p.name}: trip ${p.nums.join(", ")}${p.seen > 0 ? ` · ${p.seen} confirmed by the driver` : ""}`}</title></g>)}
            {data.stations.map((r) => {
              const [x, y] = stationXY.get(r.station_id)!;
              const on = r.station_id === station;
              const size = (station ? (on ? 13 : 5) : 4 + Math.sqrt(r.trips) / 3) * k;
              return <rect key={r.station_id} x={x - size} y={y - size} width={2 * size} height={2 * size} rx={size / 3} className={on ? "plan-routes-station on" : "plan-routes-station"} role="button" tabIndex={0} aria-label={`Station ${r.station_id}`}
                onClick={() => pick(r.station_id)} onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); pick(r.station_id); } }}><title>{`${r.station_id}: ${r.tankers_used} tankers, ${r.trips} trips`}</title></rect>;
            })}
            {spots.map(({ id, spot }) => {
              const mine = tanker === null || id === tanker;
              const colour = KIND[KINDS[spot.kind]]?.colour ?? "#1f7560";
              if (spot.state === "fill") return station && mine ? <circle key={id} cx={spot.x} cy={spot.y} r={14 * k} className="plan-routes-fill" /> : null;
              return <g key={id} opacity={mine ? 1 : 0.25}>
                {spot.state === "unload" && <circle cx={spot.x} cy={spot.y} r={(station ? 16 : 9) * k} className="plan-routes-drop" />}
                <circle cx={spot.x} cy={spot.y} r={(station ? (id === tanker ? 8 : 6) : 4) * k} fill={spot.state === "back" ? "#fff" : colour} stroke={colour} strokeWidth={station ? 2.5 : 1.5} vectorEffect="non-scaling-stroke" />
              </g>;
            })}
          </svg>
          <div className="plan-routes-overlay">
            <span><b>{clock(now)}</b></span>
            <span>{nf.format(onRoad)} on the road</span>
            {station && <span>{nf.format(filling)} filling</span>}
            <span>{nf.format(delivered)} of {nf.format(totalLegs)} delivered</span>
            {confirmed > 0 && <span>✓ {nf.format(confirmed)} stops confirmed by drivers (test mode)</span>}
          </div>
          {station && <button className="plan-routes-back button button-secondary" onClick={() => pick(null)}>← Whole city</button>}
          <div className="plan-routes-legend">
            {KINDS.map((kk) => <span key={kk}><i style={{ background: KIND[kk].colour }} />{KIND[kk].label}</span>)}
            <span><i className="hollow" />Driving back empty</span><span><i className="ripple" />Emptying the tank</span><span><i className="dot" />Filling station (stand-in place)</span>
          </div>
        </div>

        <div className="plan-routes-side">
          {!station ? <>
            <h3>Filling stations</h3>
            <p className="muted small">Click a station on the map or here to zoom in on its tankers.</p>
            <ol className="plan-routes-stations">{topStations.map((r) => <li key={r.station_id}><button onClick={() => pick(r.station_id)}><b>{r.station_id}</b><span>{r.tankers_used} tankers · {nf.format(r.trips)} trips · back by {r.finish ?? "—"}</span></button></li>)}</ol>
            <p className="muted small">{data.stations.length} stations in all; the busiest are listed.</p>
          </> : <>
            <h3>Station {station}</h3>
            {stationRow && <p className="muted small">{stationRow.tankers_used} tankers · {nf.format(stationRow.trips)} trips · {nf.format(stationRow.km)} km · last back {stationRow.finish ?? "—"}{stationRow.unscheduled > 0 ? ` · ${stationRow.unscheduled} loads do not fit the day` : ""}</p>}
            {detail.loading && <p className="plan-empty" role="status">Loading the tankers of {station}…</p>}
            <p className="muted small">Pick a tanker to follow its route.</p>
            <div className="plan-routes-tankers" role="list">{tankers.map((t) => <button key={t.tanker_id} role="listitem" className={t.tanker_id === tanker ? "active" : ""} onClick={() => setTanker(t.tanker_id === tanker ? null : t.tanker_id)}>
              <strong>{t.tanker_id}</strong><span>{t.trips.length} trips · {t.sections_reached} sections · back {t.finish}{seen.get(t.tanker_id)?.size ? ` · ✓ ${seen.get(t.tanker_id)!.size} confirmed` : ""}</span></button>)}</div>
          </>}
        </div>
      </div>

      {current && <DriverSheet tanker={current} day={planId} now={now} seen={seen.get(current.tanker_id) ?? null} />}
      <p className="muted small">Lines on the map are straight; the distances and times are road figures from OSRM where they were built ({nf.format(s.trips - s.legs_estimated)} of {nf.format(s.trips)} trips), else an estimate. Station places are stand-ins: HMWSSB does not publish them. {data.basis.times}.</p>
    </section>
  );
}

/** The tanker's day as a bar from 06:00 to 22:00: filling, driving out, emptying, driving back. */
function DayBar({ tanker, now }: { tanker: Tanker; now: number }) {
  const span = DAY_END - DAY_START;
  const x = (m: number) => (100 * (m - DAY_START)) / span;
  const parts: { from: number; to: number; cls: string; colour?: string; title: string }[] = [];
  for (const t of tanker.trips) {
    const dep = minute(t.depart), arr = minute(t.arrive), unl = minute(t.unloaded), back = minute(t.back), c = KIND[t.kind]?.colour;
    parts.push({ from: dep - FILL, to: dep, cls: "fill", title: `${clock(dep - FILL)} fill at the station` });
    parts.push({ from: dep, to: arr, cls: "drive", colour: c, title: `${t.depart} drive to ${t.name}` });
    parts.push({ from: arr, to: unl, cls: "unload", colour: c, title: `${t.arrive} empty the tank at ${t.name}` });
    parts.push({ from: unl, to: back, cls: "drive", colour: c, title: `${t.unloaded} drive back` });
  }
  const hours = Array.from({ length: (DAY_END - DAY_START) / 60 + 1 }, (_, i) => DAY_START + 60 * i);
  return <div className="plan-daybar" aria-label={`Day of tanker ${tanker.tanker_id}`}>
    <div className="plan-daybar-track">
      {parts.map((p, i) => <span key={i} className={`plan-daybar-${p.cls}`} title={p.title} style={{ left: `${x(p.from)}%`, width: `${Math.max(0.15, x(p.to) - x(p.from))}%`, background: p.cls === "fill" ? undefined : p.colour }} />)}
      {now > DAY_START && now < DAY_END && <i className="plan-daybar-now" style={{ left: `${x(now)}%` }} />}
    </div>
    <div className="plan-daybar-hours">{hours.filter((_, i) => i % 2 === 0).map((h) => <span key={h} style={{ left: `${x(h)}%` }}>{clock(h)}</span>)}</div>
    <div className="plan-daybar-key"><span><i className="plan-daybar-fill" />Filling</span><span><i className="plan-daybar-drive" style={{ background: KIND.booked.colour }} />Driving</span><span><i className="plan-daybar-unload" style={{ background: KIND.booked.colour }} />Emptying at the home</span></div>
  </div>;
}

function DriverSheet({ tanker, day, now, seen }: { tanker: Tanker; day: string; now: number; seen: Map<number, string> | null }) {
  const sheet = useRef<HTMLDivElement>(null);
  function print() {
    const w = window.open("", "_blank", "width=800,height=900");
    if (!w || !sheet.current) return;
    w.document.write(`<!doctype html><title>Route ${tanker.tanker_id}</title><style>body{font:14px system-ui;margin:24px}table{border-collapse:collapse;width:100%}td,th{border:1px solid #ccc;padding:6px;text-align:left}</style>${sheet.current.innerHTML}`);
    w.document.close();
    w.print();
  }
  return <div className="plan-driver-sheet">
    <div ref={sheet}>
      <h3>Route sheet for tanker {tanker.tanker_id} (station {tanker.station_id})</h3>
      <p>{tanker.trips.length} trips · {tanker.sections_reached} sections · {nf.format(tanker.km)} km · back by {tanker.finish} · plan {day}</p>
      <DayBar tanker={tanker} now={now} />
      <table className="plan-routes-table">
        <thead><tr><th>#</th><th>Fill and leave</th><th>Reach</th><th>Go to</th><th>For</th><th>Back at station</th><th>km</th>{seen && <th>Driver confirmed</th>}</tr></thead>
        <tbody>{tanker.trips.map((t) => <tr key={t.n}><td>{t.n}</td><td>{t.depart}</td><td>{t.arrive}</td><td>{t.name}</td><td><span style={{ color: KIND[t.kind]?.colour }}>{KIND[t.kind]?.label ?? t.kind}</span>{t.booking_id ? ` · ${bookingLabel(t.booking_id)}` : ""}</td><td>{t.back}</td><td>{t.km}{t.leg_basis === "OSRM" ? "" : " (est.)"}</td>{seen && <td>{seen.has(t.n) ? `✓ ${seen.get(t.n)!.slice(11, 16)} UTC` : "—"}</td>}</tr>)}</tbody>
      </table>
    </div>
    <button className="button button-secondary" onClick={print}>Print route sheet</button>
  </div>;
}
