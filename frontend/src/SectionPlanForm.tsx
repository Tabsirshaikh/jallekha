import { useState, type FormEvent } from "react";
import { ApiError, apiFetch } from "./api";
import type { Weights } from "./planAdapter";

// Build a plan by section from one month's real booking totals divided by the days of the month.
// English only for now.

const FIRST_DAY = "2025-01-01";
const LAST_DAY = "2025-12-31";

export default function SectionPlanForm({ weights, onBuilt }: { weights: Weights; onBuilt: (planId: string) => void }) {
  const [day, setDay] = useState("");
  const [capacity, setCapacity] = useState<"fleet" | "tight">("fleet");
  const [priority, setPriority] = useState(true);
  const [carryOver, setCarryOver] = useState(true);
  const [scheduled, setScheduled] = useState<"f4" | "none">("f4");
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<{ tone: "ok" | "error"; text: string } | null>(null);

  async function build(event: FormEvent) {
    event.preventDefault();
    if (busy) return;
    if (!/^\d{4}-\d{2}-\d{2}$/.test(day) || day < FIRST_DAY || day > LAST_DAY) return setNote({ tone: "error", text: "Choose a day in 2025." });
    setBusy(true);
    setNote(null);
    try {
      const built = await apiFetch<{ plan_id: string }>("/plans", { method: "POST", body: { day, unit: "section", capacity, weights, priority, scheduled, carry_over: carryOver } });
      onBuilt(built.plan_id);
      setNote({ tone: "ok", text: `Plan for ${day} is ready below.` });
    } catch (cause) {
      const status = cause instanceof ApiError ? cause.status : 0;
      setNote({ tone: "error", text: status === 404 ? "No plan can be made for that day (2025 only)." : status === 0 ? "The server could not be reached." : cause instanceof ApiError ? cause.message : "The plan could not be built." });
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="plan-build plan-by-section" noValidate onSubmit={(event) => void build(event)}>
      <strong>Plan by section</strong>
      <small>A day of 2025 planned for every HMWSSB section: the real booking total of that month divided by its days (all bookings counted as ordinary domestic ones). Sections whose need is an estimate are flagged for your check.</small>
      <label htmlFor="section-plan-day">Day</label>
      <input id="section-plan-day" type="date" min={FIRST_DAY} max={LAST_DAY} value={day} onChange={(event) => setDay(event.target.value)} />
      <label htmlFor="section-plan-capacity">Tankers available</label>
      <select id="section-plan-capacity" value={capacity} onChange={(event) => setCapacity(event.target.value as "fleet" | "tight")}>
        <option value="fleet">Whole fleet: 1,150 tankers x 9 trips a day (from news)</option>
        <option value="tight">Tight: the trips behind the real Jun–Aug 2026 delivered share</option>
      </select>
      <small>With the whole fleet nearly every booking is served on a normal 2025 day; the tight setting shows who waits and why.</small>
      <label className="plan-check"><input type="checkbox" checked={priority} onChange={(event) => setPriority(event.target.checked)} /> Serve hospitals first, then homes without water on premises (estimated)</label>
      <small>HMWSSB does not publish booking types, so this is an estimate: every mapped hospital or care home counts as one of its section’s bookers, and the Census share of homes fetching water from outside counts as the no-water group.</small>
      <label className="plan-check"><input type="checkbox" checked={carryOver} onChange={(event) => setCarryOver(event.target.checked)} /> Carry waiting bookings over from the days before</label>
      <label htmlFor="section-plan-scheduled">Tankers for sections that should have booked</label>
      <select id="section-plan-scheduled" value={scheduled} onChange={(event) => setScheduled(event.target.value as "f4" | "none")}>
        <option value="f4">Yes: sections the field-check screen flags get a reserved share of the trips</option>
        <option value="none">No scheduled supply</option>
      </select>
      <small>A supply cut (a notice entered for that day) is added automatically: critical facilities first, then every cut section to the minimum.</small>
      <button className="button button-primary" type="submit" disabled={busy || !day}>Build plan by section</button>
      {busy && <p className="plan-message" role="status">Building the plan…</p>}
      {note && <p className={`plan-message ${note.tone}`} role={note.tone === "error" ? "alert" : "status"}>{note.text}</p>}
    </form>
  );
}
