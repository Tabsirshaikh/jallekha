import { useState } from "react";
import { ApiError, apiFetch } from "./api";
import type { BookingView } from "./BookingExperience";
import { useApi } from "./useApi";

// U7: bookings made through JalLekha, for the officer: how many wait for tonight's plan, how far
// the others got, and the hospital / care home / school claims to check (a checked claim moves the
// booking to the front of its station's queue). English only for now.

type Page = { items: BookingView[]; total: number; claims_to_check: number };
const STATUS: Record<string, string> = { WAITING: "Waiting", EXPIRED: "Expired", ASSIGNED: "Tanker given", ON_THE_WAY: "On the way", CHECKING: "Code given", DELIVERED: "Delivered", NOT_CONFIRMED: "Not confirmed", CANCELLED: "Cancelled" };

export default function PlanBookings({ officerId: signedId }: { officerId: string }) {
  const api = useApi<Page>("/bookings?limit=200");
  const [typedId, setTypedId] = useState("");
  const officerId = signedId || typedId.trim();
  const [reason, setReason] = useState("");
  const [note, setNote] = useState<string | null>(null);
  const [open, setOpen] = useState(false);
  if (!api.data) return api.error ? <p className="muted small">Bookings could not be loaded.</p> : null;
  const items = api.data.items;
  const counts = items.reduce<Record<string, number>>((c, b) => ({ ...c, [b.status]: (c[b.status] ?? 0) + 1 }), {});
  const claims = items.filter((b) => b.claim_status === "CLAIMED");

  async function decide(b: BookingView, decision: "VERIFIED" | "REJECTED") {
    if (!officerId || !reason.trim()) return setNote("Enter your officer id and a reason first.");
    try {
      await apiFetch(`/bookings/${encodeURIComponent(b.booking_id)}/claim`, { method: "POST", body: { decision, officer_id: officerId, reason: reason.trim() } });
      setNote(`${b.facility_name ?? b.booking_id}: ${decision === "VERIFIED" ? "verified, it goes first in the next plan" : "rejected, it stays in the fair turns"}.`);
      api.reload();
    } catch (cause) {
      setNote(cause instanceof ApiError ? cause.message : "The check could not be saved.");
    }
  }

  return (
    <section className="plan-panel plan-bookings" aria-labelledby="plan-bookings-title">
      <div className="plan-panel-title"><div><p className="eyebrow">Bookings through JalLekha</p><h2 id="plan-bookings-title">{counts.WAITING ?? 0} waiting for the next plan</h2></div></div>
      <p className="plan-threshold">Real bookings from the resident app. When you build a plan by section, a section with real bookings is planned from them; other sections use the month's totals. Approving the plan gives each served booking its tanker.</p>
      <div className="plan-bookings-counts">{Object.entries(STATUS).filter(([k]) => counts[k]).map(([k, label]) => <span key={k}><b>{counts[k]}</b> {label}</span>)}{items.length === 0 && <span>No booking yet.</span>}</div>
      {claims.length > 0 && <div className="plan-bookings-claims">
        <h3>{claims.length} claim{claims.length === 1 ? "" : "s"} to check</h3>
        {!signedId && <label>Officer id<input value={typedId} maxLength={64} onChange={(e) => setTypedId(e.target.value)} /></label>}
        <label>Reason (used for each claim you decide)<input value={reason} maxLength={500} placeholder="e.g. On the hospital list / visited" onChange={(e) => setReason(e.target.value)} /></label>
        <ul>{claims.map((b) => <li key={b.booking_id}><div><strong>{b.facility_name}</strong><small>{b.category.replace("_", " ")} · {b.section_name} · {b.booking_id}</small></div>
          <button className="button button-primary" onClick={() => void decide(b, "VERIFIED")}>Verify</button><button className="button button-secondary" onClick={() => void decide(b, "REJECTED")}>Reject</button></li>)}</ul>
      </div>}
      {note && <p className="plan-message" role="status">{note}</p>}
      {items.length > 0 && <button className="text-button" onClick={() => setOpen(!open)}>{open ? "Hide the bookings" : `Show all ${items.length} bookings`}</button>}
      {open && <table className="plan-routes-table"><thead><tr><th>Booking</th><th>Section</th><th>For</th><th>Priority</th><th>Status</th><th>Tanker</th></tr></thead>
        <tbody>{items.map((b) => <tr key={b.booking_id}><td>{b.booking_id}</td><td>{b.section_name}</td><td>{b.facility_name ?? b.category.replace("_", " ")}</td><td>{b.priority}</td><td>{STATUS[b.status] ?? b.status}</td><td>{b.tanker_id ? `${b.tanker_id} · ${b.depart}` : "—"}</td></tr>)}</tbody></table>}
    </section>
  );
}
