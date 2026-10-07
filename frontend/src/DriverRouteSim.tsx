import { memo, useEffect, useMemo, useState } from "react";
import { HEIGHT, WIDTH, project, sectionShapes, shapeByGroup, wardShapes } from "./mapGeo";
import { KIND, KINDS } from "./planColours";
import { FILL, clock, minute, spotAt, type Leg } from "./routePlay";
import "./PlanRoutes.css";
import "./DriverRouteSim.css";

// U4: the driver's day from the approved plan, played on the same map as the officer's route
// screen (PlanRoutes): fill at the filling station, drive to stop 1, empty the tank, drive back,
// fill again, drive to stop 2, and so on. The times are the plan's; the lines are straight (the
// street map tab draws the road). A stop the driver confirmed is ticked whatever the clock says.
// English only for now.

export type SimTrip = { n: number; kind: string; name: string; group: string; lat: number | null; lng: number | null; depart: string; arrive: string; unloaded: string; back: string; km: number; booked: boolean; done: boolean };
type Station = { station_id: string; lat: number; lng: number };
type Box = { x: number; y: number; w: number; h: number };

const colour = (kind: string) => KIND[kind]?.colour ?? "#1f7560";
const RATIO = (WIDTH + 20) / (HEIGHT + 20);

/** Where a trip is drawn: a booker's own place, else the middle of its section, else its point. */
function placeOf(t: SimTrip): [number, number] | null {
  if (!t.booked && t.kind !== "critical") { const shape = shapeByGroup.get(t.group); if (shape) return shape.centre; }
  return t.lat !== null && t.lng !== null ? project([t.lng, t.lat]) : null;
}

/** A box around the station and the stops, padded, with the map's shape. */
function boxAround(points: [number, number][]): Box {
  const xs = points.map((p) => p[0]), ys = points.map((p) => p[1]);
  let x0 = Math.min(...xs), x1 = Math.max(...xs), y0 = Math.min(...ys), y1 = Math.max(...ys);
  const pad = Math.max(40 - (x1 - x0) / 2, 40 - (y1 - y0) / 2, 0.25 * Math.max(x1 - x0, y1 - y0), 12);
  x0 -= pad; x1 += pad; y0 -= pad; y1 += pad;
  let w = x1 - x0, h = y1 - y0;
  if (w / h < RATIO) { const nw = h * RATIO; x0 -= (nw - w) / 2; w = nw; } else { const nh = w / RATIO; y0 -= (nh - h) / 2; h = nh; }
  return { x: x0, y: y0, w, h };
}

const Base = memo(function Base({ groups, done }: { groups: Set<string>; done: Set<string> }) {
  return <g>
    {wardShapes.map((w) => <path key={w.id} d={w.d} className="plan-routes-ward" />)}
    {sectionShapes.map((s) => groups.has(s.group) ? <path key={s.id} d={s.d} className={done.has(s.group) ? "plan-routes-section visited" : "plan-routes-section"}><title>{s.name}</title></path> : null)}
  </g>;
});

/** One step of the day, in words, for the list beside the map. */
type Step = { from: number; to: number; text: string; trip: number; where: "station" | "road" | "stop" };

function stepsOf(trips: SimTrip[], station: string): Step[] {
  return trips.flatMap((t, i) => {
    const dep = minute(t.depart), arr = minute(t.arrive), unl = minute(t.unloaded), back = minute(t.back);
    return [
      { from: dep - FILL, to: dep, text: `Fill the tank at filling station ${station}`, trip: i, where: "station" as const },
      { from: dep, to: arr, text: `Drive to stop ${t.n}: ${t.name}`, trip: i, where: "road" as const },
      { from: arr, to: unl, text: `Empty the tank at stop ${t.n} and take the residents' codes`, trip: i, where: "stop" as const },
      { from: unl, to: back, text: `Drive back to filling station ${station}${i + 1 < trips.length ? " to fill again" : " (day done)"}`, trip: i, where: "road" as const },
    ];
  });
}

export default function DriverRouteSim({ station, trips, current, onChoose }: { station: Station; trips: SimTrip[]; current: number; onChoose: (n: number) => void }) {
  const placed = useMemo(() => trips.map((t) => ({ t, at: placeOf(t) })).filter((p): p is { t: SimTrip; at: [number, number] } => p.at !== null), [trips]);
  const home = useMemo(() => project([station.lng, station.lat]), [station]);
  const legs: Leg[] = useMemo(() => placed.map(({ t, at }) => ({ x: at[0], y: at[1], dep: minute(t.depart), arr: minute(t.arrive), unl: minute(t.unloaded), back: minute(t.back), kind: Math.max(0, KINDS.indexOf(t.kind as (typeof KINDS)[number])) })), [placed]);
  const start = legs.length ? legs[0].dep - FILL - 5 : 6 * 60;
  const end = legs.length ? legs[legs.length - 1].back + 5 : 22 * 60;
  const [now, setNow] = useState(start);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(4); // minutes of the day per second

  useEffect(() => {
    if (!playing) return;
    let raf = 0, last = performance.now();
    const tick = (t: number) => {
      const dt = (t - last) / 1000;
      last = t;
      setNow((m) => { const next = m + dt * speed; if (next >= end) { setPlaying(false); return end; } return next; });
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [playing, speed, end]);

  const box = useMemo(() => boxAround([home, ...placed.map((p) => p.at)]), [home, placed]);
  const k = box.w / (WIDTH + 20); // keeps marks the same size on screen
  const spot = spotAt(legs, home, now);
  const steps = useMemo(() => stepsOf(placed.map((p) => p.t), station.station_id), [placed, station]);
  const step = steps.find((s) => now >= s.from && now < s.to) ?? null;
  const groups = useMemo(() => new Set(trips.map((t) => t.group)), [trips]);
  const doneGroups = useMemo(() => new Set(trips.filter((t) => t.done).map((t) => t.group)), [trips]);

  // places: several trips can go to one section; one mark per place with all their numbers
  const places = new Map<string, { x: number; y: number; kind: string; name: string; trips: SimTrip[] }>();
  for (const { t, at } of placed) {
    const key = `${at[0].toFixed(1)},${at[1].toFixed(1)}`;
    const p = places.get(key) ?? { x: at[0], y: at[1], kind: t.kind, name: t.name, trips: [] };
    p.trips.push(t);
    places.set(key, p);
  }
  const reachedInPlay = (t: SimTrip) => now >= minute(t.unloaded);
  const playTrip = spot ? placed[spot.i]?.t ?? null : null;
  const truckColour = playTrip ? colour(playTrip.kind) : "#1f7560";
  const doneCount = trips.filter((t) => t.done).length;
  const jump = (t: SimTrip) => { setPlaying(false); setNow(minute(t.depart) - FILL); onChoose(t.n); };

  const status = !spot
    ? now < start + 5 ? `The day starts at ${clock(start + 5)}: fill at filling station ${station.station_id}.` : "Every trip is driven: the tanker is back at the station."
    : spot.state === "fill" ? `Filling the tank at station ${station.station_id} for stop ${playTrip?.n}`
    : spot.state === "out" ? `Driving to stop ${playTrip?.n}: ${playTrip?.name}`
    : spot.state === "unload" ? `Emptying the tank at stop ${playTrip?.n}`
    : `Driving back to station ${station.station_id} to fill again`;

  return (
    <div className="driver-sim">
      <div className="plan-routes-player">
        <button className="button button-primary" onClick={() => { if (now >= end) setNow(start); setPlaying(!playing); }}>{playing ? "⏸ Pause" : now >= end ? "↺ Play my day again" : "▶ Play my day"}</button>
        <span className="plan-routes-clock" aria-live="off">{clock(now)}</span>
        <input type="range" min={start} max={end} step={1} value={Math.round(now)} aria-label="Time of day" onChange={(e) => { setPlaying(false); setNow(Number(e.target.value)); }} />
        <label>Speed <select value={speed} onChange={(e) => setSpeed(Number(e.target.value))}><option value={2}>slow</option><option value={4}>normal</option><option value={12}>fast</option></select></label>
      </div>
      <div className="plan-routes-map driver-sim-map">
        <svg viewBox={`${box.x} ${box.y} ${box.w} ${box.h}`} role="group" aria-label={`Route simulation from filling station ${station.station_id}`}>
          <Base groups={groups} done={doneGroups} />
          {[...places.values()].map((p, i) => {
            const mine = p.trips.some((t) => t.n === current);
            const allDone = p.trips.every((t) => t.done);
            return <line key={"l" + i} x1={home[0]} y1={home[1]} x2={p.x} y2={p.y} stroke={allDone ? "#8a9a93" : colour(p.kind)} strokeOpacity={mine ? 0.95 : 0.5} strokeWidth={mine ? 4 : 2} strokeDasharray={allDone || mine ? undefined : "6 5"} vectorEffect="non-scaling-stroke" />;
          })}
          {spot && (spot.state === "out" || spot.state === "back") && <line x1={spot.state === "out" ? home[0] : legs[spot.i].x} y1={spot.state === "out" ? home[1] : legs[spot.i].y} x2={spot.x} y2={spot.y} stroke={truckColour} strokeWidth={6} strokeLinecap="round" strokeOpacity={0.9} vectorEffect="non-scaling-stroke" />}
          {[...places.values()].map((p, i) => {
            const allDone = p.trips.every((t) => t.done);
            const reached = p.trips.every(reachedInPlay);
            const mine = p.trips.some((t) => t.n === current);
            const r = (mine ? 20 : 16) * k;
            return <g key={"p" + i} className="driver-sim-stop" role="button" tabIndex={0} aria-label={`Stop ${p.trips.map((t) => t.n).join(", ")}: ${p.name}`}
              onClick={() => jump(p.trips.find((t) => !t.done) ?? p.trips[0])} onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); jump(p.trips.find((t) => !t.done) ?? p.trips[0]); } }}>
              <circle cx={p.x} cy={p.y} r={r} fill={allDone ? "#1f6046" : reached ? "#fff" : colour(p.kind)} stroke={allDone ? "#fff" : colour(p.kind)} strokeWidth={mine ? 3 : 2} vectorEffect="non-scaling-stroke" />
              <text x={p.x} y={p.y + 5 * k} textAnchor="middle" fontSize={14 * k} className={allDone || !reached ? "plan-routes-n" : "plan-routes-n dark"}>{allDone ? "✓" : p.trips.map((t) => t.n).join(",")}</text>
              <text x={p.x} y={p.y + r + 16 * k} textAnchor="middle" fontSize={14 * k} className="plan-routes-label">{p.name}</text>
              <title>{p.trips.map((t) => `Stop ${t.n}: arrive ${t.arrive}${t.done ? " · confirmed" : ""}`).join("\n")}</title>
            </g>;
          })}
          <rect x={home[0] - 18 * k} y={home[1] - 18 * k} width={36 * k} height={36 * k} rx={8 * k} className="plan-routes-station on" />
          <text x={home[0]} y={home[1] + 7 * k} textAnchor="middle" fontSize={19 * k} className="driver-sim-pump">⛽</text>
          <text x={home[0]} y={home[1] - 26 * k} textAnchor="middle" fontSize={14 * k} className="plan-routes-label">{`Filling station ${station.station_id}`}</text>
          {spot && spot.state === "fill" && <circle cx={home[0]} cy={home[1]} r={28 * k} className="plan-routes-fill" />}
          {spot && spot.state === "unload" && <circle cx={spot.x} cy={spot.y} r={30 * k} className="plan-routes-drop" />}
          {spot && <g className="driver-sim-truck">
            <circle cx={spot.x} cy={spot.y} r={12 * k} fill={spot.state === "back" ? "#fff" : truckColour} stroke={truckColour} strokeWidth={3} vectorEffect="non-scaling-stroke" />
            <title>{status}</title>
          </g>}
        </svg>
        <div className="plan-routes-overlay">
          <span><b>{clock(now)}</b></span>
          <span>{status}</span>
        </div>
        <div className="plan-routes-legend">
          <span><i className="dot" />Filling station (stand-in place)</span>
          <span><i style={{ background: truckColour }} />Tanker, full</span>
          <span><i className="hollow" />Tanker, driving back empty</span>
          <span><i style={{ background: "#1f6046" }} />Stop confirmed by residents' codes</span>
        </div>
      </div>
      <ol className="driver-sim-steps" aria-label="My day, step by step">
        {steps.map((s, i) => {
          const t = placed[s.trip].t;
          const state = t.done && s.where !== "station" ? "done" : step === s ? "now" : now >= s.to ? "past" : "";
          return <li key={i} className={`${state} ${s.where}`}><button onClick={() => { setPlaying(false); setNow(s.from); onChoose(t.n); }}><span>{clock(s.from)}</span>{s.text}{s.where === "stop" && t.done ? " ✓" : ""}</button></li>;
        })}
      </ol>
      <p className="muted small">{doneCount} of {trips.length} stops confirmed. Times and stops come from the officer's approved plan: one full tanker per stop, so the tanker goes back to the filling station to fill again after each one. Lines are straight; the Street map tab shows the road.</p>
    </div>
  );
}
