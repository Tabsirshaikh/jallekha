import { useRef, useState, type FormEvent } from "react";
import { apiFetch } from "./api";
import { useAuth } from "./auth";
import { useLocale } from "./i18n";
import { useApi } from "./useApi";

import { weeklyCopy, weeklyDaysCopy, weeklySourceCopy, type WeeklyRow } from "./weeklyPriorityCopy";

export default function WeeklyPriorityPanel({ sectionId, onSaved }: { sectionId?: string; onSaved?: () => void }) {
  const { locale } = useLocale();
  const { status, role } = useAuth();
  const enabled = status === "signed-in" && (role === "officer" || role === "field_worker");
  const w = weeklyCopy[locale];
  const api = useApi<{ items: WeeklyRow[] }>(enabled ? `/field-checks/weekly-priority${sectionId ? `?section_id=${encodeURIComponent(sectionId)}` : ""}` : null);
  const rows = Array.isArray(api.data?.items) ? api.data.items : [];
  const [selected, setSelected] = useState("");
  const row = rows.find(r => r.section_id === (sectionId || selected)) ?? rows[0];
  const [supply, setSupply] = useState("unknown");
  const [share, setShare] = useState(50);
  const [yesterday] = useState(() => new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Kolkata", year: "numeric", month: "2-digit", day: "2-digit" }).format(new Date(Date.now() - 24 * 60 * 60 * 1000)));
  const [through, setThrough] = useState(yesterday);
  const [complete, setComplete] = useState(false);
  const [reason, setReason] = useState("unclear");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const retry = useRef<{ body: string; id: string } | null>(null);
  const number = new Intl.NumberFormat(locale, { maximumFractionDigits: 2 });
  const fmt = (v: number | null) => v === null ? "—" : number.format(v);
  async function save(event: FormEvent) {
    event.preventDefault();
    if (!row || busy) return;
    setBusy(true);
    const data = { section_id: row.section_id, checked_on: through, supply, tanker_share: supply === "adequate" ? 0 : supply === "unavailable" ? 1 : share / 100, records_complete: complete, booking_reason: reason, note };
    const body = JSON.stringify(data);
    if (retry.current?.body !== body) retry.current = { body, id: crypto.randomUUID() };
    try {
      const result = await apiFetch<{ ledger_missing: boolean }>("/field-checks/supply-reviews", { method: "POST", body: { ...data, id: retry.current.id } });
      setMessage(result.ledger_missing ? w.pending : w.saved);
      if (!result.ledger_missing) { retry.current = null; api.reload(); onSaved?.(); }
    } catch { setMessage(w.error); }
    finally { setBusy(false); }
  }
  if (!enabled) return null;
  return <section className="atlas-checks section-outcome-form">
    <h3>{w.title}</h3><p>{w.intro}</p>
    {api.loading ? <p>{w.loading}</p> : !row ? <p>{w.loadError}</p> : <>
      {!sectionId && <label>{w.section}<select disabled={busy} value={row.section_id} onChange={e => { setSelected(e.target.value); setSupply("unknown"); setComplete(false); setNote(""); setMessage(""); retry.current = null; }}>{rows.map(r => <option key={r.section_id} value={r.section_id}>{r.section}</option>)}</select></label>}
      <p>{row.window_start} – {row.window_end}</p>
      <p>{row.source === "BOOKINGS" && row.status !== "UNKNOWN" ? weeklySourceCopy[locale].bookings.replace("{d}", String(row.bookings_delivered ?? 0)).replace("{n}", String(row.bookings_not_delivered ?? 0)).replace("{u}", String(row.bookings_unknown ?? 0)) : row.source === "OFFICER_CHECK" ? weeklySourceCopy[locale].officer : weeklySourceCopy[locale].none}</p>
      {row.status === "UNKNOWN" && <p>{w.unknown}</p>}
      {row.status === "UNKNOWN" && <p>{weeklyDaysCopy[locale].unknown}</p>}
      <dl className="atlas-facts">{([[w.population, row.population_estimate], [w.baseline, row.baseline_need_weight], [w.current, row.status === "UNKNOWN" ? null : row.current_need_weight], [w.requirement, row.weekly_requirement_litres], [w.delivered, row.confirmed_litres], [w.shortfall, row.shortfall_litres], [weeklyDaysCopy[locale].label, row.days_below_minimum ?? null]] as const).map(([label, v]) => <div key={label}><dt>{label}</dt><dd>{fmt(v)}</dd></div>)}</dl>
      <p>{w.apply}</p>
      <details open={!sectionId}><summary>{w.verify}</summary><form onSubmit={e => void save(e)}>
        <label>{w.supply}<select value={supply} disabled={busy} onChange={e => setSupply(e.target.value)}><option value="unknown">{w.unclear}</option><option value="adequate">{w.adequate}</option><option value="insufficient">{w.insufficient}</option><option value="unavailable">{w.unavailable}</option></select></label>
        {supply === "insufficient" && <label>{w.share}<input type="number" min={1} max={99} required disabled={busy} value={share} onChange={e => setShare(Number(e.target.value))} /></label>}
        <label>{w.date}<input type="date" required max={yesterday} disabled={busy} value={through} onChange={e => setThrough(e.target.value)} /></label><p>{w.dateHelp}</p>
        <label><input type="checkbox" checked={complete} disabled={busy} onChange={e => setComplete(e.target.checked)} />{w.complete}</label>
        <label>{w.reason}<select value={reason} disabled={busy} onChange={e => setReason(e.target.value)}><option value="unclear">{w.unclear}</option><option value="other_supply">{w.other}</option><option value="access_difficulty">{w.access}</option></select></label>
        <label>{w.note}<textarea required maxLength={2000} disabled={busy} value={note} onChange={e => setNote(e.target.value)} /></label>
        <button type="submit" disabled={busy}>{w.save}</button>
      </form></details>
    </>}
    {message && <p role="status">{message}</p>}
  </section>;
}
