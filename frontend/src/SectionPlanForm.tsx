import { useState, type FormEvent } from "react";
import { ApiError, apiFetch } from "./api";
import type { Weights } from "./planAdapter";

// Build a plan by section from one month's real booking totals divided by the days of the month.
// English only for now.

const FIRST_DAY = "2025-01-01";
const LAST_DAY = "2030-12-31";

export default function SectionPlanForm({ weights, onBuilt }: { weights: Weights; onBuilt: (planId: string) => void }) {
  const [day, setDay] = useState("");
  const [capacity, setCapacity] = useState<"fleet" | "tight">("tight");
  const [priority, setPriority] = useState(true);
  const [carryOver, setCarryOver] = useState(true);
  const [scheduled, setScheduled] = useState(true);
  const [responsive, setResponsive] = useState(true);
  const [rebalance, setRebalance] = useState(true);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<{ tone: "ok" | "error"; text: string } | null>(null);

  async function build(event: FormEvent) {
    event.preventDefault();
    if (busy) return;
    if (!/^\d{4}-\d{2}-\d{2}$/.test(day) || day < FIRST_DAY || day > LAST_DAY) return setNote({ tone: "error", text: "Choose a day from 2025 on." });
    setBusy(true);
    setNote(null);
    try {
      const built = await apiFetch<{ plan_id: string }>("/plans", { method: "POST", body: { day, unit: "section", capacity, weights, priority, scheduled: scheduled ? "f4" : "none", carry_over: carryOver, responsive, rebalance } });
      onBuilt(built.plan_id);
      setNote({ tone: "ok", text: `Plan for ${day} is ready below.` });
    } catch (cause) {
      const status = cause instanceof ApiError ? cause.status : 0;
      setNote({ tone: "error", text: status === 404 ? "No plan can be made for that day." : status === 0 ? "The server could not be reached." : cause instanceof ApiError ? cause.message : "The plan could not be built." });
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="plan-panel plan-section-form" noValidate onSubmit={(event) => void build(event)} aria-labelledby="section-plan-title">
      <div className="plan-panel-title"><div><p className="eyebrow">New plan</p><h2 id="section-plan-title">Plan a day for every section</h2></div></div>
      <p className="plan-threshold">Each HMWSSB section's real bookings for the month, spread over its days, shared out over the tankers available.</p>
      <div className="plan-form-row">
        <label className="plan-field" htmlFor="section-plan-day"><span>Day</span>
          <input id="section-plan-day" type="date" min={FIRST_DAY} max={LAST_DAY} value={day} onChange={(event) => setDay(event.target.value)} />
          <small>A day of 2025, or today: real bookings made through JalLekha are used, other sections use the same month of 2025.</small>
        </label>
        <div className="plan-field" role="group" aria-labelledby="section-plan-capacity"><span id="section-plan-capacity">Tankers available</span>
          <div className="plan-segment">
            <button type="button" aria-pressed={capacity === "tight"} onClick={() => setCapacity("tight")}><b>Tight day</b><span>As few trips as HMWSSB really managed in summer 2026: shows who waits and why.</span></button>
            <button type="button" aria-pressed={capacity === "fleet"} onClick={() => setCapacity("fleet")}><b>Whole fleet</b><span>1,150 tankers × 9 trips a day (news): almost every booking is served.</span></button>
          </div>
        </div>
      </div>
      <fieldset className="plan-options"><legend>Rules</legend>
        <label className="plan-option"><input type="checkbox" checked={priority} onChange={(event) => setPriority(event.target.checked)} /><b>Hospitals first, then homes with no water at home</b><small>Estimated: HMWSSB does not publish who booked.</small></label>
        <label className="plan-option"><input type="checkbox" checked={carryOver} onChange={(event) => setCarryOver(event.target.checked)} /><b>Bring forward bookings still waiting from the days before</b><small>A booking drops out after 3 days.</small></label>
        <label className="plan-option"><input type="checkbox" checked={scheduled} onChange={(event) => setScheduled(event.target.checked)} /><b>Send water to areas that book too little</b><small>12 sections the field-check list flags get water on a schedule.</small></label>
        <label className="plan-option"><input type="checkbox" checked={responsive} onChange={(event) => setResponsive(event.target.checked)} /><b>Areas that got water this week wait their turn</b><small>A section served well in the last 7 days gets fewer turns (down to ¼); one left waiting gets more (up to 4×). The Census need stays the base.</small></label>
        <label className="plan-option"><input type="checkbox" checked={rebalance} onChange={(event) => setRebalance(event.target.checked)} /><b>Move trips to stations where bookings pile up</b><small>Same total trips; each station gets between half and double its usual trips, by the bookings waiting there.</small></label>
      </fieldset>
      <p className="muted small">A water-cut notice entered for the day is added on its own: hospitals there first, then every cut home up to the minimum.</p>
      <div className="plan-form-actions">
        <button className="button button-primary" type="submit" disabled={busy || !day}>{busy ? "Building…" : "Build plan by section"}</button>
        {note && <p className={`plan-message ${note.tone}`} role={note.tone === "error" ? "alert" : "status"}>{note.text}</p>}
      </div>
    </form>
  );
}
