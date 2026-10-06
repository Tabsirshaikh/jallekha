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
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<{ tone: "ok" | "error"; text: string } | null>(null);

  async function build(event: FormEvent) {
    event.preventDefault();
    if (busy) return;
    if (!/^\d{4}-\d{2}-\d{2}$/.test(day) || day < FIRST_DAY || day > LAST_DAY) return setNote({ tone: "error", text: "Choose a day in 2025." });
    setBusy(true);
    setNote(null);
    try {
      const built = await apiFetch<{ plan_id: string }>("/plans", { method: "POST", body: { day, unit: "section", capacity, weights } });
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
      <button className="button button-primary" type="submit" disabled={busy || !day}>Build plan by section</button>
      {busy && <p className="plan-message" role="status">Building the plan…</p>}
      {note && <p className={`plan-message ${note.tone}`} role={note.tone === "error" ? "alert" : "status"}>{note.text}</p>}
    </form>
  );
}
