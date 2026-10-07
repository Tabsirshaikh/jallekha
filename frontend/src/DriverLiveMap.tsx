import { useEffect, useMemo, useRef, useState } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { KIND } from "./planColours";
import { fetchRoad, pointAlong, remaining, type LatLng } from "./routeGeo";

// U4: the driver's street map (Leaflet + OpenStreetMap). The filling station, the stops still to do
// (numbered), and the road of the trip in hand: station -> stop -> station. A finished stop and the
// road already driven disappear. The road comes from OSRM (OpenStreetMap roads); if it cannot be
// reached the map draws straight lines and says so. English only for now.

export type MapTrip = { n: number; kind: string; name: string; lat: number | null; lng: number | null; depart: string; done: boolean };
type Station = { station_id: string; lat: number; lng: number };
type Road = { key: string; line: LatLng[]; km: number } | null;

const colour = (kind: string) => KIND[kind]?.colour ?? "#1f7560";
const pin = (html: string, cls: string, size: number) => L.divIcon({ html, className: `driver-pin ${cls}`, iconSize: [size, size], iconAnchor: [size / 2, size / 2] });

export default function DriverLiveMap({ station, trips, current, gps, testMode, onChoose }: { station: Station; trips: MapTrip[]; current: number; gps: LatLng | null; testMode: boolean; onChoose: (n: number) => void }) {
  const box = useRef<HTMLDivElement>(null);
  const map = useRef<L.Map | null>(null);
  const layer = useRef<L.LayerGroup | null>(null);
  const [road, setRoad] = useState<Road>(null);
  const [drive, setDrive] = useState(0); // TEST MODE: how far along the road the pretend driver is (0 to 1)

  const home: LatLng = useMemo(() => [station.lat, station.lng], [station]);
  const placed = useMemo(() => trips.filter((t) => t.lat !== null && t.lng !== null) as (MapTrip & { lat: number; lng: number })[], [trips]);
  const now = placed.find((t) => t.n === current && !t.done) ?? null;
  const key = now ? `${station.station_id}|${now.lat},${now.lng}` : "";

  // the road of the trip in hand (station -> stop -> station); one request, kept per trip
  useEffect(() => {
    if (!now) return;
    let alive = true;
    void fetchRoad([home, [now.lat, now.lng], home]).then((r) => { if (alive) setRoad(r ? { key, ...r } : { key, line: [], km: 0 }); });
    return () => { alive = false; };
  }, [key, home, now]);
  const roadHere = road && road.key === key ? road : null;
  const fetched = roadHere ? roadHere.line.length > 1 : false;
  const full: LatLng[] = useMemo(() => now ? (fetched && roadHere ? roadHere.line : [home, [now.lat, now.lng], home]) : [], [now, fetched, roadHere, home]);
  const simulated = testMode && drive > 0 && full.length > 1 ? pointAlong(full, drive) : null;
  const position = gps ?? simulated;
  const ahead = useMemo(() => remaining(full, position), [full, position]);

  useEffect(() => {
    if (!box.current || map.current) return;
    const m = L.map(box.current, { zoomControl: true, attributionControl: true }).setView(home, 13);
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", { maxZoom: 19, attribution: "© OpenStreetMap contributors" }).addTo(m);
    layer.current = L.layerGroup().addTo(m);
    map.current = m;
    return () => { m.remove(); map.current = null; layer.current = null; };
  }, [home]);

  // what is drawn: later stops, the road ahead, the stop in hand, the station, the driver
  useEffect(() => {
    const g = layer.current;
    if (!g) return;
    g.clearLayers();
    for (const t of placed) {
      if (t.done || t.n === current) continue;
      L.polyline([home, [t.lat, t.lng]], { color: colour(t.kind), weight: 2, opacity: 0.4, dashArray: "4 6" }).addTo(g);
      L.marker([t.lat, t.lng], { icon: pin(String(t.n), "stop", 28), title: `Trip ${t.n}: ${t.name}` }).on("click", () => onChoose(t.n)).addTo(g);
    }
    if (now && ahead.length > 1) {
      L.polyline(ahead, { color: "#ffffff", weight: 10, opacity: 0.9, lineCap: "round" }).addTo(g);
      L.polyline(ahead, { color: colour(now.kind), weight: 6, opacity: 0.95, lineCap: "round", dashArray: fetched ? undefined : "10 8" }).addTo(g);
    }
    if (now) L.marker([now.lat, now.lng], { icon: pin(String(now.n), "stop now", 40), title: `Trip ${now.n}: ${now.name}`, zIndexOffset: 500 }).bindTooltip(`${now.n}. ${now.name}`, { permanent: true, direction: "top", offset: [0, -18] }).addTo(g);
    L.marker(home, { icon: pin("⛽", "station", 34), title: `Filling station ${station.station_id}`, zIndexOffset: 400 }).bindTooltip(`Filling station ${station.station_id}`, { direction: "bottom", offset: [0, 14] }).addTo(g);
    if (position) L.marker(position, { icon: pin("", "driver", 20), title: "You are here", zIndexOffset: 1000 }).addTo(g);
  }, [placed, current, now, ahead, fetched, home, station, position, onChoose]);

  // zoom to what is left to do whenever the trip in hand (or its road) changes, not at every step
  useEffect(() => {
    const m = map.current;
    if (!m) return;
    const points: LatLng[] = full.length > 1 ? full : [home, ...placed.filter((t) => !t.done).map((t): LatLng => [t.lat, t.lng])];
    try { m.fitBounds(L.latLngBounds(points), { padding: [40, 40], maxZoom: 16 }); } catch { /* the map has no size yet */ }
  }, [full, placed, home]);

  const left = trips.filter((t) => !t.done).length;
  return (
    <div className="driver-live">
      <div ref={box} className="driver-live-map" role="region" aria-label="Map of the route" />
      <p className="muted small driver-live-basis">
        {!now ? "Every stop is done." : fetched ? `Road: ${roadHere!.km} km out and back, from OpenStreetMap roads (OSRM).` : roadHere ? "Straight lines: the road service could not be reached, so this is not the road." : "Finding the road…"}
        {` ${left} stop${left === 1 ? "" : "s"} left.`}
      </p>
      {testMode && now && <label className="driver-plan-test"><span>TEST MODE: drive along the road</span>
        <input type="range" min={0} max={100} value={Math.round(drive * 100)} onChange={(e) => setDrive(Number(e.target.value) / 100)} aria-label="Pretend driving along the road" /></label>}
    </div>
  );
}
