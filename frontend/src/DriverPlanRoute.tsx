import { Suspense, lazy, useEffect, useState } from "react";
import { ApiError, apiFetch } from "./api";
import { useApi } from "./useApi";
import type { BookingView } from "./BookingExperience";
import type { MapTrip } from "./DriverLiveMap";
import type { LatLng } from "./routeGeo";
import "./DriverPlanRoute.css";

// the map (and Leaflet with it) loads only when a driver opens a route
const DriverLiveMap = lazy(() => import("./DriverLiveMap"));

// U4: the driver's day from the approved plan by section (GET /driver/tankers, /driver/route). Trips
// for bookings made through JalLekha carry the delivery-code steps (F12); estimated loads (from
// monthly totals) have no person behind them and need no code. English only for now.

type Trip = { n: number; kind: string; name: string; depart: string; arrive: string; back: string; km: number; booking: BookingView | null; stop_id: string | null; group: string; lat: number | null; lng: number | null };
type Route = { day: string; plan_id: string; tanker_id: string; station_id: string; station: { station_id: string; lat: number; lng: number }; finish: string; km: number; trips: Trip[] };
type Tankers = { day: string; plan_id: string; tankers_total: number; items: { tanker_id: string; station_id: string; trips: number; real_bookings: number; first_depart: string }[] };
type DeliveryView = { delivery_id: string; otp_issued: boolean; otp_verified: boolean; outcome_status: string };
type VerifyResult = { result: string; location: { status: string; distance_m: number | null }; delivery: DeliveryView };

const KIND: Record<string, string> = { booked: "Booking", scheduled: "Water on a schedule", outage: "Water cut", critical: "Hospital in a water cut" };
const today = () => new Date(Date.now() + 5.5 * 3600 * 1000).toISOString().slice(0, 10); // Hyderabad date
const errorText = (cause: unknown) => (cause instanceof ApiError ? (cause.status === 0 ? "The server could not be reached." : cause.message) : "Something went wrong.");

function position(): Promise<{ lat: number; lon: number } | null> {
  return new Promise((resolve) => {
    if (!navigator.geolocation) return resolve(null);
    navigator.geolocation.getCurrentPosition(({ coords }) => resolve({ lat: coords.latitude, lon: coords.longitude }), () => resolve(null), { enableHighAccuracy: true, timeout: 15000, maximumAge: 0 });
  });
}

export default function DriverPlanRoute() {
  const [day, setDay] = useState(today);
  const [tanker, setTanker] = useState("");
  const [testMode, setTestMode] = useState(false);
  const list = useApi<Tankers>(`/driver/tankers?day=${day}`);
  const routeApi = useApi<Route>(tanker ? `/driver/route?day=${day}&tanker_id=${encodeURIComponent(tanker)}` : null);
  // Keep the last route on screen while it reloads, so a delivery's messages are not lost.
  const [kept, setKept] = useState<Route | null>(null);
  if (routeApi.data && routeApi.data !== kept) setKept(routeApi.data);
  const shownRoute = routeApi.data ?? (routeApi.loading && kept?.tanker_id === tanker ? kept : null);
  const route = { ...routeApi, data: shownRoute };
  useEffect(() => { apiFetch<{ test_mode: boolean }>("/sms/test-mode").then((r) => setTestMode(r.test_mode)).catch(() => setTestMode(false)); }, []);
  const tankers = list.data?.items ?? [];

  return (
    <section className="driver-plan" aria-labelledby="driver-plan-title">
      <div className="driver-plan-head">
        <div><p className="eyebrow">From the approved plan</p><h2 id="driver-plan-title">My trips today</h2></div>
        <label>Day <input type="date" value={day} onChange={(e) => { setDay(e.target.value); setTanker(""); }} /></label>
        <label>My tanker <input list="driver-plan-tankers" value={tanker} placeholder="T0001" onChange={(e) => setTanker(e.target.value.trim().toUpperCase())} />
          <datalist id="driver-plan-tankers">{tankers.map((t) => <option key={t.tanker_id} value={t.tanker_id}>{`${t.station_id} · ${t.real_bookings} booking(s) · leaves ${t.first_depart}`}</option>)}</datalist></label>
      </div>
      {list.loading && <p className="muted" role="status">Looking for today's approved plan…</p>}
      {list.error && <p className="muted">{list.error.status === 404 ? "No approved plan by section for this day yet. The officer approves the plan; then your trips appear here." : errorText(list.error)}</p>}
      {list.data && !tanker && <p className="muted">{tankers.length > 0 ? `${tankers.length} tankers carry bookings made through JalLekha today (of ${list.data.tankers_total} on the road). Pick yours: ${tankers.slice(0, 6).map((t) => t.tanker_id).join(", ")}${tankers.length > 6 ? "…" : ""}` : "No booking made through JalLekha is in today's plan; your trips are estimated loads."}</p>}
      {route.error && <p className="plan-message error" role="alert">{route.error.status === 404 ? `Tanker ${tanker} has no trips in today's plan.` : errorText(route.error)}</p>}
      {route.data && <RouteView key={`${route.data.day}|${route.data.tanker_id}`} route={route.data} testMode={testMode} onDone={route.reload} />}
    </section>
  );
}

const finished = (t: Trip) => t.booking?.status === "DELIVERED" || t.booking?.status === "NOT_CONFIRMED";
const doneKey = (r: Route) => `jallekha-driver-done:${r.day}:${r.tanker_id}`;
function savedDone(r: Route): number[] { try { return JSON.parse(localStorage.getItem(doneKey(r)) ?? "[]") as number[]; } catch { return []; } }

/** One tanker's day: the map, the next stop and the trips. A trip is finished when its booking is delivered (the server knows), or, for an estimated load that has no booker, when the driver taps "Delivered here" (kept on this phone only). */
function RouteView({ route, testMode, onDone }: { route: Route; testMode: boolean; onDone: () => void }) {
  const [picked, setPicked] = useState<number | null>(null);
  const [byHand, setByHand] = useState<number[]>(() => savedDone(route));
  const [gps, setGps] = useState<LatLng | null>(null);
  const [gpsNote, setGpsNote] = useState<string | null>(null);
  useEffect(() => {
    if (!gpsNote || gpsNote !== "on" || !navigator.geolocation) return;
    const id = navigator.geolocation.watchPosition((p) => setGps([p.coords.latitude, p.coords.longitude]), () => setGpsNote("Your position could not be read."), { enableHighAccuracy: true, maximumAge: 5000 });
    return () => navigator.geolocation.clearWatch(id);
  }, [gpsNote]);
  const isDone = (t: Trip) => finished(t) || byHand.includes(t.n);
  const next = route.trips.find((t) => !isDone(t)) ?? null;
  const current = picked !== null && route.trips.some((t) => t.n === picked && !isDone(t)) ? picked : next?.n ?? 0;
  const trip = route.trips.find((t) => t.n === current) ?? null;
  const mark = (n: number) => { const all = [...byHand, n]; setByHand(all); setPicked(null); try { localStorage.setItem(doneKey(route), JSON.stringify(all)); } catch { /* kept for this visit only */ } };
  const trips: MapTrip[] = route.trips.map((t) => ({ n: t.n, kind: t.kind, name: t.name, lat: t.lat, lng: t.lng, depart: t.depart, done: isDone(t) }));

  return <>
    <p className="muted small">Station {route.station_id} · {route.trips.length} trips · {route.km} km · back by {route.finish}. Fill at the station before each trip: one booking is one full tanker.</p>
    <div className="driver-plan-map">
      <p className="driver-plan-next" role="status">{trip
        ? <>{picked !== null && trip.n !== next?.n ? "Showing" : "Next stop"}: <b>trip {trip.n}, {trip.name}</b> · leave the station at {trip.depart}, arrive {trip.arrive}</>
        : "All of today's trips are finished. Well done."}</p>
      <Suspense fallback={<p className="muted" role="status">Loading the map…</p>}>
        <DriverLiveMap station={route.station} trips={trips} current={current} gps={gps} testMode={testMode} onChoose={setPicked} />
      </Suspense>
      <div className="driver-plan-gps">
        <button className="button button-secondary" onClick={() => { setGpsNote("on"); if (!navigator.geolocation) setGpsNote("This phone cannot give its position."); }}>{gps ? "Following my position" : "Show my position on the map"}</button>
        {gpsNote && gpsNote !== "on" && <span className="muted small">{gpsNote}</span>}
      </div>
      <p className="muted small">This is the route the officer's plan gave this tanker: fill at the station, drive to the stop, come back, fill again. A stop disappears when it is delivered, and the road behind you disappears as you drive. Tap a stop or a trip to see its road. The station's place is a stand-in.</p>
    </div>
    <ol className="driver-plan-trips">{route.trips.map((t) => <li key={t.n} className={`${t.booking ? "real" : ""}${t.n === current ? " chosen" : ""}${isDone(t) ? " finished" : ""}`}>
      <div className="driver-plan-trip-head" role="button" tabIndex={0} onClick={() => setPicked(t.n)} onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); setPicked(t.n); } }}><b>{t.n}</b><span>{t.depart} → {t.arrive}</span><strong>{t.name}</strong><small>{KIND[t.kind] ?? t.kind}{t.booking ? ` · ${t.booking.priority}` : " · estimated load, no code needed"}</small></div>
      {t.booking && t.stop_id && <DeliverBooking key={t.booking.booking_id} booking={t.booking} stopId={t.stop_id} tanker={route.tanker_id} testMode={testMode} onDone={onDone} />}
      {!t.booking && !isDone(t) && <button className="button button-secondary driver-plan-hand" onClick={() => mark(t.n)}>Delivered here: next stop</button>}
      {!t.booking && byHand.includes(t.n) && <p className="driver-plan-done">✓ Marked delivered (kept on this phone only, no booker to confirm).</p>}
    </li>)}</ol>
  </>;
}

function DeliverBooking({ booking, stopId, tanker, testMode, onDone }: { booking: BookingView; stopId: string; tanker: string; testMode: boolean; onDone: () => void }) {
  const [delivery, setDelivery] = useState<DeliveryView | null>(null);
  const [code, setCode] = useState("");
  const [atStop, setAtStop] = useState(false);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<{ tone: "ok" | "error"; text: string } | null>(null);
  const id = booking.delivery?.delivery_id ?? delivery?.delivery_id ?? null;
  const status = booking.status;

  async function run(action: () => Promise<void>) {
    setBusy(true); setNote(null);
    try { await action(); } catch (cause) { setNote({ tone: "error", text: errorText(cause) }); } finally { setBusy(false); }
  }
  const start = () => run(async () => {
    const made = await apiFetch<DeliveryView>("/deliveries", { method: "POST", body: { delivery_id: crypto.randomUUID(), stop_id: stopId, driver_id: tanker } });
    setDelivery(made);
    const sent = await apiFetch<DeliveryView>(`/deliveries/${made.delivery_id}/otp`, { method: "POST", body: { representative_id: `${stopId}-rep` } });
    setDelivery(sent);
    setNote({ tone: "ok", text: `Code sent to the booker's phone (ends in ${booking.phone_last2}). Ask them for it at the door.` });
  });
  const verify = () => run(async () => {
    const where = atStop ? { lat: booking.lat, lon: booking.lon } : await position();
    const result = await apiFetch<VerifyResult>(`/deliveries/${id}/otp/verify`, { method: "POST", body: { code: code.trim(), lat: where?.lat ?? null, lon: where?.lon ?? null } });
    setDelivery(result.delivery);
    const text: Record<string, string> = {
      verified: "Code is right. The booker is now asked: did you get water?",
      wrong_code: "Wrong code. Ask the booker to read it again.",
      outside_geofence: `You are not at the booking's place (${result.location.distance_m !== null ? Math.round(result.location.distance_m) + " m away" : "too far"}). Go to the address and try again.`,
      no_otp: "No code was sent yet.", expired: "The code expired: send a new one.", locked: "Too many wrong codes: call your dispatcher.",
      invalid_location: "Your position could not be read.", already_verified: "Already verified.",
    };
    setNote({ tone: result.result === "verified" || result.result === "already_verified" ? "ok" : "error", text: text[result.result] ?? result.result });
    onDone();
  });

  if (status === "DELIVERED" || status === "NOT_CONFIRMED") return <p className={status === "DELIVERED" ? "driver-plan-done" : "plan-message error"}>{status === "DELIVERED" ? "✓ Delivered and confirmed by the booker." : `Not confirmed (${booking.delivery?.outcome}).`}</p>;
  if (status === "CHECKING") return <p className="muted small">Code verified. Waiting for the booker to answer "did you get water?".</p>;
  return (
    <div className="driver-plan-proof">
      {!id ? <button className="button button-primary" disabled={busy} onClick={() => void start()}>Start delivery and send the code</button> : <>
        <label>Code from the booker<input inputMode="numeric" maxLength={8} value={code} onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))} /></label>
        {testMode && <label className="driver-plan-test"><input type="checkbox" checked={atStop} onChange={(e) => setAtStop(e.target.checked)} /> TEST MODE: use the booking's place as my position (I am testing away from the address)</label>}
        <button className="button button-primary" disabled={busy || code.length < 4} onClick={() => void verify()}>Check the code</button>
      </>}
      {note && <p className={`plan-message ${note.tone}`} role={note.tone === "error" ? "alert" : "status"}>{note.text}</p>}
    </div>
  );
}
