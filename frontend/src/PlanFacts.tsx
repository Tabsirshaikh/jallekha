import type { PlanFacts as Facts } from "./planAdapter";

// The day's plan by section in numbers: one row per figure with what it means in plain words and
// where it comes from. English only for now.

const nf = new Intl.NumberFormat("en", { maximumFractionDigits: 0 });
const pct = (part: number, whole: number) => (whole > 0 ? `${Math.round((100 * part) / whole)}%` : "—");
const MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];

type Source = "real" | "estimate" | "assumption" | "result";
const SOURCE: Record<Source, string> = { real: "Real data", estimate: "Estimate", assumption: "Assumption", result: "Plan result" };
type Row = { what: string; value: string; note?: string; meaning: string; source: Source; strong?: boolean };

export default function PlanFacts({ facts, day, capacity }: { facts: Facts; day: string; capacity: string | null }) {
  const [y, m] = day.split("-").map(Number);
  const days = new Date(y, m, 0).getDate();
  const month = `${MONTHS[m - 1]} ${y}`;
  const fresh = facts.bookings - facts.carried;
  const [t0, t1, t2] = facts.tiers;
  const [s0, s1, s2] = facts.servedTiers;
  const tight = capacity === "tight";

  const groups: { title: string; rows: Row[] }[] = [
    {
      title: "Bookings",
      rows: [
        { what: "Bookings to serve today", value: nf.format(facts.bookings), strong: true, source: "real",
          meaning: `${nf.format(fresh)} new today (each section's real ${month} total ÷ ${days} days) + ${nf.format(facts.carried)} still waiting from the days before.` },
        { what: "1st: hospitals and care homes", value: nf.format(t0), note: `${nf.format(s0)} served`, source: "estimate",
          meaning: "Served before anyone else. One booking a day for each hospital or care home on the map." },
        { what: "2nd: homes with no water at home", value: nf.format(t1), note: `${nf.format(s1)} served`, source: "estimate",
          meaning: "Served next. The share of homes that fetch water from outside (Census 2011) in each section." },
        { what: "3rd: everyone else", value: nf.format(t2), note: `${nf.format(s2)} served`, source: "estimate",
          meaning: "Served in fair turns, so a busy section cannot take every tanker; sections with more need get more turns." },
        { what: "Of these, commercial", value: nf.format(facts.commercial), source: "estimate",
          meaning: "Shops, hotels, offices. About 32% of tanker trips were commercial in HMWSSB's 2022 RTI answer." },
      ],
    },
    {
      title: "Tankers",
      rows: [
        { what: "Tanker trips available", value: nf.format(facts.trips), strong: true, source: "assumption",
          meaning: tight
            ? "Tight day: as few trips as HMWSSB really delivered in Jun–Aug 2026. One trip = one full tanker (5,000 litres)."
            : `Whole fleet: ${nf.format(facts.fleetTankers)} tankers × ${facts.tripsPerTanker} trips a day (from news). One trip = one full tanker (5,000 litres).` },
        { what: "Kept for areas that book too little", value: nf.format(facts.reserveTrips), note: `${nf.format(facts.reserveUsedTrips)} needed`, source: "assumption",
          meaning: facts.scheduledSections > 0
            ? `5% of trips are kept for ${facts.scheduledSections} sections that get water on a schedule. They need ${nf.format(facts.reserveUsedTrips)} loads; the other ${nf.format(Math.max(0, facts.reserveTrips - facts.reserveUsedTrips))} are not passed back to bookings yet.`
            : "No section gets water on a schedule in this plan." },
        { what: "Kept for water cuts", value: nf.format(facts.outageTrips), source: "assumption",
          meaning: facts.cutSections > 0
            ? `${facts.cutSections} sections have a water cut today: hospitals there first, then every home up to the minimum.`
            : "No water-cut notice for this day, so no trips are kept for it." },
        { what: "Trips left for bookings", value: nf.format(facts.bookedTrips), source: "result",
          meaning: `Shared over ${facts.stations} filling stations. A station with spare trips lends them to a busy neighbour.` },
      ],
    },
    {
      title: "Result",
      rows: [
        { what: "Bookings served today", value: nf.format(facts.served), note: pct(facts.served, facts.bookings), strong: true, source: "result",
          meaning: "Hospitals first, then homes with no water at home, then fair turns until the trips run out." },
        { what: "Bookings waiting", value: nf.format(facts.waiting), note: pct(facts.waiting, facts.bookings), source: "result",
          meaning: "They are planned again tomorrow. A booking still waiting after 3 days drops out." },
      ],
    },
  ];

  return (
    <section className="plan-panel plan-facts" aria-labelledby="plan-facts-title">
      <div className="plan-panel-title"><div><p className="eyebrow">Plan for {day}</p><h2 id="plan-facts-title">Today's plan in numbers</h2></div></div>
      <table className="plan-facts-table">
        <thead><tr><th scope="col">What</th><th scope="col" className="num">Number</th><th scope="col">What it means</th><th scope="col">Source</th></tr></thead>
        {groups.map((g) => <tbody key={g.title}>
          <tr className="plan-facts-group"><th colSpan={4} scope="colgroup">{g.title}</th></tr>
          {g.rows.map((r) => <tr key={r.what} className={r.strong ? "strong" : undefined}>
            <th scope="row">{r.what}</th>
            <td className="num"><b>{r.value}</b>{r.note && <small>{r.note}</small>}</td>
            <td>{r.meaning}</td>
            <td><span className={`plan-source plan-source-${r.source}`}>{SOURCE[r.source]}</span></td>
          </tr>)}
        </tbody>)}
      </table>
    </section>
  );
}
