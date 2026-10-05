import type { ReactNode } from "react";
import { badgeKind, DELIVERY_OUTCOMES, liveWards, type ApiSmsSummary, type DeliveryOutcome, type ViewBlock, type WardCardView } from "./wardCardAdapter";
import type { ApiState } from "./useApi";

const outcomeKey: Record<DeliveryOutcome, string> = { Confirmed: "outConfirmed", Disputed: "outDisputed", Unconfirmed: "outUnconfirmed", Failed: "outFailed", open: "outOpen" };

function fill(template: string, values: Record<string, string | number>): string {
  return template.replace(/\{(\w+)\}/g, (whole, name: string) => (name in values ? String(values[name]) : whole));
}

const classKey: Record<string, string> = { piped_regularity_unknown: "classPipedRegularityUnknown", piped_normal: "classPipedNormal", piped_intermittent: "classPipedIntermittent", no_connection: "classNoConnection" };

/** Plain words for a service type; an unknown code is shown as it is. */
function serviceClassLabel(code: string, words: Record<string, string>): string {
  return words[classKey[code]] ?? code;
}

/** The ward picker, with a retry button when the card could not be loaded. */
export function WardPicker({ words, wardId, onChange, onRetry }: { words: Record<string, string>; wardId: string; onChange: (id: string) => void; onRetry?: () => void }) {
  return (
    <div className="u10-ward-picker"><label htmlFor="u10-live-ward">{words.chooseWard}</label><select id="u10-live-ward" value={wardId} onChange={(event) => onChange(event.target.value)}>{liveWards.map((ward) => <option value={ward.id} key={ward.id}>{ward.name}</option>)}</select>{onRetry && <button className="button button-secondary" type="button" onClick={onRetry}>{words.retry}</button>}</div>
  );
}

function Tag({ label }: { label: string }) {
  return <small className={`source-tag ${badgeKind(label)}`}>{label}</small>;
}

function Row({ label, value }: { label: string; value: string }) {
  return <div className="u10-row"><span>{label}</span><strong>{value}</strong></div>;
}

/** One live block: its rows when it has a value, otherwise the API's reason and no numbers. */
function Block<T>({ title, block, words, basisNote, rows }: { title: string; block: ViewBlock<T>; words: Record<string, string>; basisNote?: string; rows: (data: T) => { label: string; value: string }[] }) {
  return (
    <section className="u10-block" aria-label={title}>
      <div className="u10-block-head"><h2>{title}</h2><Tag label={block.badge} /></div>
      {block.data === null
        ? <p className="u10-reason">{block.reason ? fill(words.whyLabel, { reason: block.reason }) : words.noValue}</p>
        : <>{rows(block.data).map((row) => <Row key={row.label} label={row.label} value={row.value} />)}{basisNote && <small className="u10-basis">{basisNote}</small>}</>}
    </section>
  );
}

type Props = {
  view: WardCardView | null;
  sms: Pick<ApiState<ApiSmsSummary>, "data" | "loading">;
  words: Record<string, string>;
  locale: string;
  wardId: string;
  onWardChange: (id: string) => void;
  copyState: string;
  onCopy: (text: string) => void;
  chip: ReactNode;
};

/** The live ward report card (F20). `view` is null while the card is loading. */
export default function WardCardLive({ view, sms, words, locale, wardId, onWardChange, copyState, onCopy, chip }: Props) {
  const number = new Intl.NumberFormat(locale);
  const statusWords: Record<string, string> = { APPROVED: words.statusApproved, DRAFT: words.statusDraft };
  const sourceWords: Record<string, string> = { supplied_bookings: words.sourceSupplied };
  const smsText = sms.data?.text ?? null;
  return (
    <section className="resident-ward-card">
      <div className="u10-chip-row"><p className="eyebrow">F20 · {words.liveTitle}</p>{chip}</div>
      <h1>{view?.wardName ?? liveWards.find((ward) => ward.id === wardId)?.name ?? wardId}</h1>
      <p>{words.liveIntro}</p>
      <WardPicker words={words} wardId={wardId} onChange={onWardChange} />
      {view === null ? <p role="status" className="muted">{words.loadingCard}</p> : <>
        <div className="u10-data-grid">
          <article><span>{words.needScore}</span><strong>{view.need.needWeight === null ? words.noValue : view.need.needWeight.toFixed(2)}</strong><small>{words.serviceClass}: <span>{serviceClassLabel(view.need.serviceClass, words)}</span></small><Tag label={view.need.basis} /></article>
          <article><span>{fill(words.bookingsPeriod, { from: view.bookings.from, to: view.bookings.to })}</span><strong>{view.bookings.count === null ? words.noValue : number.format(view.bookings.count)}</strong><Tag label={view.bookings.basis} /></article>
        </div>
        <Block title={words.deliveriesTitle} block={view.deliveries} words={words} rows={(d) => [
          { label: words.period, value: fill(words.lastDays, { days: d.windowDays }) },
          { label: words.started, value: number.format(d.started) },
          ...DELIVERY_OUTCOMES.map((outcome) => ({ label: words[outcomeKey[outcome]], value: number.format(d.outcomes[outcome]) })),
          { label: words.stopsCount, value: number.format(d.stops) },
        ]} />
        <Block title={words.debtTitle} block={view.debt} words={words} rows={(d) => [
          { label: words.debtLoads, value: number.format(d.loads) },
          { label: words.debtLitres, value: number.format(d.litres) },
          { label: words.daysInDebt, value: number.format(d.daysInDebt) },
          { label: words.alertRaised, value: d.alertRaised ? words.yes : words.no },
          { label: words.lastClosed, value: d.lastClosedDay ?? words.none },
        ]} />
        <Block title={words.scheduleTitle} block={view.schedule} words={words} basisNote={view.schedule.data ? view.schedule.basis : undefined} rows={(d) => [
          { label: words.planDay, value: d.day },
          { label: words.planStatus, value: statusWords[d.status] ?? d.status },
          { label: words.basedOn, value: sourceWords[d.source] ?? words.sourceReplay },
          ...(d.served === null || d.waiting === null ? [] : [{ label: words.tripsServed, value: number.format(d.served) }, { label: words.tripsWaiting, value: number.format(d.waiting) }]),
          ...d.stopLoads.map((stop) => ({ label: stop.stopId, value: fill(words.loadsForStop, { loads: number.format(stop.loads) }) })),
        ]} />
      </>}
      <div className="u10-sms">
        <div>
          <p className="eyebrow">{words.sms}</p>
          {smsText !== null ? <p>{smsText}</p> : <p role="status">{sms.loading ? words.loadingSms : words.smsUnavailable}</p>}
          {sms.data && sms.data.lang_used !== sms.data.lang_requested && <p role="note" className="u10-sms-note">{words.smsEnglish}</p>}
        </div>
        {smsText !== null && <button className="button button-secondary" onClick={() => onCopy(smsText)}>{copyState || words.copy}</button>}
      </div>
      <p className="resident-privacy-note">{words.liveNote}</p>
    </section>
  );
}
