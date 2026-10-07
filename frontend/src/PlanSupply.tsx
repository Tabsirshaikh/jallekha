import type { PlanOverview, SectionRow } from "./planAdapter";
import { CATEGORY } from "./planColours";

// Water sent without bookings in a plan by section: scheduled supply for sections that book far
// too little (F9) and emergency water where a supply notice cuts the pipes (F10). English only.

const nf = new Intl.NumberFormat("en", { maximumFractionDigits: 0 });

function Compare({ own, peers }: { own: number; peers: number }) {
  const max = Math.max(own, peers, 1);
  return <div className="plan-compare" aria-hidden="true">
    <span>This section</span><span className="plan-bar"><i style={{ width: `${(100 * own) / max}%`, background: CATEGORY.scheduled.colour }} /></span><b>{nf.format(own)}</b>
    <span>Similar sections</span><span className="plan-bar"><i style={{ width: `${(100 * peers) / max}%`, background: "#9aa8a2" }} /></span><b>{nf.format(peers)}</b>
  </div>;
}

function ScheduledCard({ row, lpcd }: { row: SectionRow; lpcd: number }) {
  const w = row.scheduled!;
  const times = row.bookingsPer1000 && row.peerBookingsPer1000 ? row.peerBookingsPer1000 / row.bookingsPer1000 : null;
  return <article className="plan-water-card" style={{ borderInlineStartColor: CATEGORY.scheduled.colour }}>
    <header><h3>{row.name}</h3><span className={w.full ? "plan-chip ok" : "plan-chip warn"}>{w.full ? "Fully covered" : "Partly covered"}</span></header>
    {row.bookingsPer1000 !== null && row.peerBookingsPer1000 !== null && <>
      <p>Tankers booked last year per 1,000 homes{times && times >= 1.5 ? <>: similar sections nearby booked <b>{times.toFixed(1)}×</b> more.</> : "."}</p>
      <Compare own={row.bookingsPer1000} peers={row.peerBookingsPer1000} />
    </>}
    <div className="plan-water-figures">
      <div><strong>{nf.format(w.litres)}</strong><span>litres sent today</span></div>
      <div><strong>{w.loads}</strong><span>tanker loads</span></div>
      <div><strong>{nf.format(w.people)}</strong><span>people, {lpcd} litres each</span></div>
    </div>
  </article>;
}

export function PlanScheduled({ overview }: { overview: PlanOverview }) {
  const rows = overview.sections.filter((r) => r.scheduled && r.scheduled.litres > 0).sort((a, b) => b.scheduled!.litres - a.scheduled!.litres);
  const lpcd = overview.facts.litresPerPerson;
  return (
    <section className="plan-panel plan-water" aria-labelledby="plan-scheduled-title">
      <div className="plan-panel-title"><div><p className="eyebrow">Water on a schedule</p><h2 id="plan-scheduled-title">Areas that book too little still get water</h2></div></div>
      <div className="plan-water-explain">
        <p>Some sections book far fewer tankers than similar sections nearby. Often that is not because they have enough water: people may not know how to book, have no phone, or cannot pay. So we do not wait for their bookings and send water anyway.</p>
        <ol className="plan-howto">
          <li><b>Spot</b> sections that book much less than similar ones (the field-check list).</li>
          <li><b>Count</b> the people there who have no water at home.</li>
          <li><b>Send</b> {lpcd} litres a day for each of them, from trips kept aside for this.</li>
        </ol>
        <p className="muted small">The drop point is the centre of the section until an officer registers real points. A field visit should confirm each section.</p>
      </div>
      {rows.length === 0 ? <p className="plan-empty">No section gets water on a schedule in this plan.</p>
        : <div className="plan-water-grid">{rows.map((r) => <ScheduledCard key={r.group} row={r} lpcd={lpcd} />)}</div>}
    </section>
  );
}

export function PlanOutage({ overview }: { overview: PlanOverview }) {
  const rows = overview.sections.filter((r) => r.outage).sort((a, b) => (b.outage!.hoursCutOff ?? 0) - (a.outage!.hoursCutOff ?? 0));
  const critical = overview.facts.criticalStops;
  return (
    <section className="plan-panel plan-water" aria-labelledby="plan-outage-cards-title">
      <div className="plan-panel-title"><div><p className="eyebrow">Water cut</p><h2 id="plan-outage-cards-title">Areas whose pipes are cut today</h2></div></div>
      <div className="plan-water-explain">
        <p>When the water board announces a supply cut (pipeline work, a burst main), the sections it covers get emergency water before any booking:</p>
        <ol className="plan-howto">
          <li><b>Hospitals and care homes</b> in the cut area get a full tanker first.</li>
          <li><b>Every home</b> then gets at least 10–15 litres per person, more for areas cut off longer.</li>
          <li><b>Bookings</b> share the trips that are left.</li>
        </ol>
      </div>
      {rows.length === 0 ? <p className="plan-empty plan-water-none">No water-cut notice covers this day, so no emergency water is needed. When a supply-cut notice is entered for a day (notices API), that day's plan shows the cut sections here.</p>
        : <>
          {critical > 0 && <p className="plan-threshold"><b>{critical}</b> hospitals and care homes in cut areas get a tanker first.</p>}
          <div className="plan-water-grid">{rows.map((r) => <article key={r.group} className="plan-water-card" style={{ borderInlineStartColor: CATEGORY.cut.colour }}>
            <header><h3>{r.name}</h3><span className={r.outage!.full ? "plan-chip ok" : "plan-chip warn"}>{r.outage!.full ? "Fully covered" : "Minimum only"}</span></header>
            <div className="plan-water-figures">
              <div><strong>{r.outage!.hoursCutOff !== null ? nf.format(r.outage!.hoursCutOff) : "—"}</strong><span>hours without water</span></div>
              <div><strong>{nf.format(r.outage!.litres)}</strong><span>litres sent today</span></div>
              <div><strong>{r.outage!.loads}</strong><span>tanker loads</span></div>
              <div><strong>{nf.format(r.outage!.people)}</strong><span>people</span></div>
            </div>
          </article>)}</div>
        </>}
    </section>
  );
}
