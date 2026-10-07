import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent, type MouseEvent } from "react";
import { ApiError, apiFetch } from "./api";
import { useLocale } from "./i18n";
import { HEIGHT, WIDTH, project, sectionShapes, unproject, wardShapes } from "./mapGeo";
import "./BookingExperience.css";

// U2 booking: a resident (or a field worker for them) books a tanker. The server decides the
// section from the location; a hospital, care home or school is a claim an officer checks once.
// "My bookings" follows each booking from waiting to delivered. English only for now.

type Category = "home" | "apartment" | "hospital" | "care_home" | "school" | "commercial";
type Place = { inside: boolean; section: string | null; section_name: string | null; ward_name: string | null };
type Delivery = { delivery_id: string; otp_issued: boolean; otp_verified: boolean; asked_residents: number; replies: number; outcome: string | null; counts_toward_debt: boolean | null };
export type BookingView = {
  booking_id: string; arrived_at: string; section_name: string; lat: number; lon: number; category: Category; facility_name: string | null;
  water_at_home: string; claim_status: string; tier: number; priority: string; status: string; plan_id: string | null; tanker_id: string | null;
  station_id: string | null; trip_n: number | null; depart: string | null; arrive: string | null; delivery: Delivery | null; phone_last2: string; basis: string;
};
type Message = { at: string; template: string; text: string; code: string | null };

const KINDS: { id: Category; label: string; hint: string }[] = [
  { id: "home", label: "My home", hint: "A house or a flat" },
  { id: "apartment", label: "Apartment building", hint: "For the whole building" },
  { id: "hospital", label: "Hospital or clinic", hint: "Served first once an officer checks it" },
  { id: "care_home", label: "Care home", hint: "Old-age home, orphanage" },
  { id: "school", label: "School", hint: "Served early once an officer checks it" },
  { id: "commercial", label: "Shop, hotel or office", hint: "Commercial rate" },
];
const CLAIMS: Category[] = ["hospital", "care_home", "school"];
const STORE = "jallekha.bookings";
const STEPS = [
  { id: "WAITING", label: "Booked" },
  { id: "ASSIGNED", label: "Tanker given" },
  { id: "ON_THE_WAY", label: "On the way" },
  { id: "CHECKING", label: "Code given" },
  { id: "DELIVERED", label: "Water received" },
];
const STATUS_TEXT: Record<string, string> = {
  WAITING: "Waiting for a tanker. Tonight's plan decides who gets one tomorrow, in priority order.",
  EXPIRED: "No tanker could be sent within 3 days, so this booking has expired. Please book again.",
  ASSIGNED: "A tanker is planned for you.",
  ON_THE_WAY: "The driver has started your delivery. Keep your phone near: you will get a code.",
  CHECKING: "The driver checked your code. Please answer the message: did you get water?",
  DELIVERED: "Delivered and confirmed by you. Thank you.",
  NOT_CONFIRMED: "The delivery was not confirmed. Your area's water debt stays, so it gets more turns.",
  CANCELLED: "Cancelled.",
};

function savedIds(): string[] {
  try { return JSON.parse(localStorage.getItem(STORE) ?? "[]") as string[]; } catch { return []; }
}
function saveIds(ids: string[]) {
  try { localStorage.setItem(STORE, JSON.stringify(ids.slice(0, 20))); } catch { /* private window: list lives for this visit only */ }
}
const errorText = (cause: unknown) => (cause instanceof ApiError ? (cause.status === 0 ? "The server could not be reached. Try again." : cause.message) : "Something went wrong. Try again.");

function PinMap({ pin, onPick }: { pin: [number, number] | null; onPick: (lat: number, lon: number) => void }) {
  const svg = useRef<SVGSVGElement>(null);
  function click(event: MouseEvent<SVGSVGElement>) {
    const el = svg.current;
    const matrix = el?.getScreenCTM();
    if (!el || !matrix) return;
    const pt = new DOMPoint(event.clientX, event.clientY).matrixTransform(matrix.inverse());
    const [lng, lat] = unproject([pt.x, pt.y]);
    onPick(lat, lng);
  }
  const at = pin ? project([pin[1], pin[0]]) : null;
  return (
    <svg ref={svg} className="booking-map" viewBox={`-10 -10 ${WIDTH + 20} ${HEIGHT + 20}`} role="img" aria-label="Map of the city: click where the water is needed" onClick={click}>
      {wardShapes.map((w) => <path key={w.id} d={w.d} className="booking-map-ward" />)}
      {sectionShapes.map((s) => <path key={s.id} d={s.d} className="booking-map-section"><title>{s.name}</title></path>)}
      {at && <g transform={`translate(${at[0]} ${at[1]})`} className="booking-map-pin"><path d="M0 0 C-9 -14 -13 -20 -13 -27 A13 13 0 1 1 13 -27 C13 -20 9 -14 0 0Z" /><circle cy="-27" r="5" fill="#fff" /></g>}
    </svg>
  );
}

export default function BookingExperience() {
  const { locale } = useLocale();
  const [pin, setPin] = useState<[number, number] | null>(null);
  const [place, setPlace] = useState<Place | null>(null);
  const [locating, setLocating] = useState(false);
  const [kind, setKind] = useState<Category>("home");
  const [facility, setFacility] = useState("");
  const [water, setWater] = useState<"yes" | "no" | "unknown">("unknown");
  const [phone, setPhone] = useState("+91");
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<{ tone: "ok" | "error"; text: string } | null>(null);
  const [ids, setIds] = useState<string[]>(() => savedIds());

  async function pick(lat: number, lon: number) {
    setPin([lat, lon]);
    setPlace(null);
    setLocating(true);
    try { setPlace(await apiFetch<Place>(`/bookings/locate?lat=${lat.toFixed(6)}&lon=${lon.toFixed(6)}`)); }
    catch (cause) { setNote({ tone: "error", text: errorText(cause) }); }
    finally { setLocating(false); }
  }
  function useMyLocation() {
    if (!navigator.geolocation) return setNote({ tone: "error", text: "This device cannot share its location. Click on the map instead." });
    navigator.geolocation.getCurrentPosition(
      ({ coords }) => void pick(coords.latitude, coords.longitude),
      () => setNote({ tone: "error", text: "Location was not shared. Click on the map instead." }),
      { enableHighAccuracy: true, timeout: 15000 },
    );
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!pin || !place?.inside) return setNote({ tone: "error", text: "Choose a place inside the city first." });
    if (!/^\+[1-9]\d{7,14}$/.test(phone)) return setNote({ tone: "error", text: "Enter the phone number with the country code, like +919812345678." });
    if (CLAIMS.includes(kind) && !facility.trim()) return setNote({ tone: "error", text: "Enter the name of the hospital, care home or school." });
    setBusy(true);
    setNote(null);
    try {
      const made = await apiFetch<BookingView>("/bookings", { method: "POST", body: { lat: pin[0], lon: pin[1], category: kind, water_at_home: water, phone, language: locale, facility_name: CLAIMS.includes(kind) ? facility.trim() : null } });
      const next = [made.booking_id, ...ids.filter((x) => x !== made.booking_id)];
      setIds(next);
      saveIds(next);
      setNote({ tone: "ok", text: `Booked: ${made.booking_id}. You can follow it below.` });
    } catch (cause) {
      setNote({ tone: "error", text: errorText(cause) });
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="booking-page">
      <header><p className="eyebrow">Tanker booking</p><h1>Book a water tanker</h1><p className="muted">One booking is one full tanker (5,000 litres). Hospitals go first, then homes with no water, then everyone in fair turns.</p></header>
      <form className="booking-card" onSubmit={(event) => void submit(event)} noValidate>
        <section className="booking-step">
          <h2><span>1</span>Where is the water needed?</h2>
          <div className="booking-where">
            <PinMap pin={pin} onPick={(lat, lon) => void pick(lat, lon)} />
            <div className="booking-where-side">
              <button type="button" className="button button-secondary" onClick={useMyLocation}>Use my location</button>
              <p className="muted small">or click the place on the map.</p>
              {locating && <p className="muted" role="status">Finding your section…</p>}
              {place && (place.inside
                ? <div className="booking-section" role="status"><span>Your section</span><strong>{place.section_name}</strong>{place.ward_name && <small>{place.ward_name}</small>}<small className="muted">Found from the location (approximate section areas).</small></div>
                : <p className="plan-message error" role="alert">This place is outside the HMWSSB sections we know. Move the pin inside the city.</p>)}
            </div>
          </div>
        </section>
        <section className="booking-step">
          <h2><span>2</span>Who is it for?</h2>
          <div className="booking-kinds" role="radiogroup" aria-label="Who is it for">
            {KINDS.map((k) => <button type="button" role="radio" aria-checked={kind === k.id} key={k.id} className={kind === k.id ? "on" : ""} onClick={() => setKind(k.id)}><b>{k.label}</b><small>{k.hint}</small></button>)}
          </div>
          {CLAIMS.includes(kind) && <label className="booking-field">Name of the {kind === "school" ? "school" : kind === "care_home" ? "care home" : "hospital or clinic"}<input value={facility} maxLength={120} onChange={(e) => setFacility(e.target.value)} /><small>An officer checks it once. Until then it waits like a home booking.</small></label>}
        </section>
        <section className="booking-step">
          <h2><span>3</span>Do you have water at home right now?</h2>
          <p className="muted small">Running tap water or a working borewell. Homes without any water are served before others.</p>
          <div className="booking-yesno" role="radiogroup" aria-label="Water at home">
            {([["no", "No water at all"], ["yes", "Some water"], ["unknown", "Not sure"]] as const).map(([v, label]) => <button type="button" role="radio" aria-checked={water === v} key={v} className={water === v ? "on" : ""} onClick={() => setWater(v)}>{label}</button>)}
          </div>
        </section>
        <section className="booking-step">
          <h2><span>4</span>Your phone number</h2>
          <label className="booking-field">Phone (with country code)<input type="tel" inputMode="tel" value={phone} onChange={(e) => setPhone(e.target.value.replace(/[^\d+]/g, ""))} /><small>The delivery code comes to this number. Give it to the driver at your door. One open booking per number.</small></label>
        </section>
        <div className="booking-submit">
          <button className="button button-primary" type="submit" disabled={busy || !place?.inside}>{busy ? "Booking…" : "Book the tanker"}</button>
          {note && <p className={`plan-message ${note.tone}`} role={note.tone === "error" ? "alert" : "status"}>{note.text}</p>}
        </div>
      </form>
      <MyBookings ids={ids} />
    </div>
  );
}

function MyBookings({ ids }: { ids: string[] }) {
  const [items, setItems] = useState<Record<string, BookingView | null>>({});
  const [testMode, setTestMode] = useState(false);
  const load = useCallback(async () => {
    const pairs = await Promise.all(ids.map(async (id) => [id, await apiFetch<BookingView>(`/bookings/${encodeURIComponent(id)}`).catch(() => null)] as const));
    setItems(Object.fromEntries(pairs));
  }, [ids]);
  useEffect(() => {
    const first = window.setTimeout(() => void load(), 0);
    apiFetch<{ test_mode: boolean }>("/sms/test-mode").then((r) => setTestMode(r.test_mode)).catch(() => setTestMode(false));
    const id = window.setInterval(() => void load(), 8000);
    return () => { window.clearTimeout(first); window.clearInterval(id); };
  }, [load]);
  if (ids.length === 0) return null;
  return (
    <section className="booking-mine" aria-labelledby="booking-mine-title">
      <h2 id="booking-mine-title">My bookings</h2>
      {ids.map((id) => items[id] ? <BookingCard key={id} b={items[id]!} testMode={testMode} onChange={() => void load()} /> : <p key={id} className="muted">{id}: loading…</p>)}
    </section>
  );
}

function BookingCard({ b, testMode, onChange }: { b: BookingView; testMode: boolean; onChange: () => void }) {
  const reached = useMemo(() => {
    const order = ["WAITING", "ASSIGNED", "ON_THE_WAY", "CHECKING", "DELIVERED"];
    return b.status === "NOT_CONFIRMED" ? 3 : Math.max(0, order.indexOf(b.status));
  }, [b.status]);
  return (
    <article className="booking-status">
      <header><div><strong>{b.booking_id}</strong><small>{b.section_name} · {KINDS.find((k) => k.id === b.category)?.label}{b.facility_name ? ` · ${b.facility_name}` : ""}</small></div><span className={`booking-tier tier-${b.tier}`}>{b.priority}</span></header>
      <ol className="booking-steps">{STEPS.map((s, i) => <li key={s.id} className={i <= reached ? (b.status === "NOT_CONFIRMED" && i === 3 ? "bad" : "done") : ""}><i />{s.label}</li>)}</ol>
      <p>{STATUS_TEXT[b.status] ?? b.status}</p>
      {b.tanker_id && <p className="muted small">Tanker {b.tanker_id} from station {b.station_id}: leaves about {b.depart}, reaches you about {b.arrive}.</p>}
      {b.claim_status === "CLAIMED" && <p className="muted small">Waiting for an officer to check that this is a {b.category.replace("_", " ")}.</p>}
      {b.delivery?.outcome && <p className="muted small">Delivery result: {b.delivery.outcome}.</p>}
      {testMode && <TestPhone b={b} onChange={onChange} />}
    </article>
  );
}

/** SMS test mode: what was "sent" to this booking's phone, and the yes/no answer. */
function TestPhone({ b, onChange }: { b: BookingView; onChange: () => void }) {
  const [phone, setPhone] = useState("+91");
  const [msgs, setMsgs] = useState<Message[] | null>(null);
  const [note, setNote] = useState("");
  const read = useCallback(async () => {
    if (!/^\+\d{8,15}$/.test(phone) || !phone.endsWith(b.phone_last2)) return;
    try { setMsgs((await apiFetch<{ items: Message[] }>(`/sms/outbox?phone=${encodeURIComponent(phone)}`)).items); } catch { setMsgs(null); }
  }, [phone, b.phone_last2]);
  useEffect(() => {
    const first = window.setTimeout(() => void read(), 0);
    const id = window.setInterval(() => void read(), 5000);
    return () => { window.clearTimeout(first); window.clearInterval(id); };
  }, [read, b.status]);
  async function answer(text: "1" | "2") {
    try { await apiFetch("/sms/outbox/reply", { method: "POST", body: { phone, text } }); setNote(text === "1" ? "You answered: yes, I got water." : "You answered: no water."); onChange(); }
    catch (cause) { setNote(errorText(cause)); }
  }
  const asked = b.status === "CHECKING";
  return (
    <div className="booking-test">
      <p className="booking-test-badge">TEST MODE · no SMS is sent; the messages show here</p>
      <label>Phone number of this booking (ends in {b.phone_last2})<input value={phone} onChange={(e) => setPhone(e.target.value.replace(/[^\d+]/g, ""))} /></label>
      {msgs && msgs.length === 0 && <p className="muted small">No message yet.</p>}
      {msgs && msgs.slice(0, 3).map((m) => <p key={m.at} className="booking-sms">{m.code ? <>Code <b>{m.code}</b> · </> : null}{m.text}</p>)}
      {asked && <div className="booking-answer"><button className="button button-primary" onClick={() => void answer("1")}>1 · Yes, I got water</button><button className="button button-secondary" onClick={() => void answer("2")}>2 · No</button></div>}
      {note && <p className="muted small" role="status">{note}</p>}
    </div>
  );
}
