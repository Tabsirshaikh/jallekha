/** Maps the API's ward report card (`GET /wards/{ward_id}/report-card`) and SMS summary into the
 * ward page's view. A live block (`deliveries`, `debt`, `schedule`) is {value, basis, reason}: when
 * `value` is null the view keeps the reason and carries no numbers. */

import evidence from "./data/u5Evidence.json";

function wardNumber(name: string): number {
  const match = /^Ward (\d+)/.exec(name);
  return match ? Number(match[1]) : Number.MAX_SAFE_INTEGER;
}

type ApiBlock<T> = { value: T | null; basis: string; reason: string | null };

export type ApiWardCard = {
  ward_id: string;
  ward_name: string;
  geography_version?: string;
  quality_flags?: string[];
  need: { service_class: string; need_weight: number | null; need_basis: string; class_basis?: string };
  bookings: { period: { from: string; to: string; missing_months?: string[] }; bookings: number | null; bookings_per_1000?: number | null; basis: string; mapping_status?: string };
  deliveries: ApiBlock<{
    window_days: number;
    started: number;
    stops: { stop_id: string; basis?: string; ward_basis?: string }[];
    by_outcome: Partial<Record<DeliveryOutcome, number>>;
    from?: string;
    to?: string;
    confirmed_litres?: number;
  }>;
  debt: ApiBlock<{
    debt_litres: number;
    debt_loads: number;
    days_in_debt: number;
    alert_raised: boolean;
    settled_through?: string | null;
    last_day?: { day?: string; alert?: boolean } | null;
    cap_litres?: number;
    in_debt_since?: string | null;
  }>;
  schedule: ApiBlock<{
    plan_id: string;
    day: string;
    status: string;
    source: string;
    booked?: { group?: string; served: number; waiting: number } | null;
    stops: { stop_id: string; loads: number; litres?: number }[];
  }>;
};

export type ApiSmsSummary = { ward_id: string; lang_requested: string; lang_used: string; text: string };

export type DeliveryOutcome = "Confirmed" | "Disputed" | "Unconfirmed" | "Failed" | "open";
export const DELIVERY_OUTCOMES: DeliveryOutcome[] = ["Confirmed", "Disputed", "Unconfirmed", "Failed", "open"];

/** Every ward of the evidence snapshot, in ward-number order, for the picker: residents cannot list wards (that route is for officers). */
export const liveWards: { id: string; name: string }[] = evidence.wards
  .map((ward) => ({ id: ward.id, name: ward.name }))
  .sort((a, b) => wardNumber(a.name) - wardNumber(b.name) || a.name.localeCompare(b.name));

/** The ward the card opens on. */
export const defaultWardId = "relation/7848824";

/** A view block: `data` is null exactly when the API had no value; `reason` then says why. */
export type ViewBlock<T> = { badge: string; reason: string | null; data: T | null };

export type WardCardView = {
  wardId: string;
  wardName: string;
  need: { serviceClass: string; needWeight: number | null; basis: string };
  bookings: { count: number | null; from: string; to: string; basis: string };
  deliveries: ViewBlock<{ windowDays: number; started: number; stops: number; outcomes: Record<DeliveryOutcome, number> }>;
  debt: ViewBlock<{ loads: number; litres: number; daysInDebt: number; alertRaised: boolean; lastClosedDay: string | null }>;
  schedule: ViewBlock<{ day: string; status: string; source: string; served: number | null; waiting: number | null; stopLoads: { stopId: string; loads: number }[] }> & { basis: string };
};

/** "MIXED (REAL and SYNTHETIC stops)" -> "MIXED"; a plain sentence has no label (null). */
export function badgeLabel(basis: string): string | null {
  return /^([A-Z][A-Z_]+)(?![a-z])/.exec(basis)?.[1] ?? null;
}

/** Which source-tag colour a label gets: real, derived (also mixed) or simulation (everything else). */
export function badgeKind(label: string): "real" | "derived" | "simulation" {
  if (label === "REAL") return "real";
  if (label.startsWith("DERIVED") || label === "MIXED") return "derived";
  return "simulation";
}

function block<A, B>(source: ApiBlock<A>, build: (value: A) => B, badge: (value: A | null) => string): ViewBlock<B> {
  return { badge: badge(source.value), reason: source.reason ?? null, data: source.value === null ? null : build(source.value) };
}

export function wardCardFromApi(answer: ApiWardCard): WardCardView {
  const deliveries = block(
    answer.deliveries,
    (v) => ({
      windowDays: v.window_days,
      started: v.started,
      stops: v.stops.length,
      outcomes: Object.fromEntries(DELIVERY_OUTCOMES.map((outcome) => [outcome, v.by_outcome[outcome] ?? 0])) as Record<DeliveryOutcome, number>,
    }),
    () => badgeLabel(answer.deliveries.basis) ?? answer.deliveries.basis,
  );
  const debt = block(
    answer.debt,
    (v) => ({ loads: v.debt_loads, litres: v.debt_litres, daysInDebt: v.days_in_debt, alertRaised: v.alert_raised, lastClosedDay: v.settled_through ?? v.last_day?.day ?? null }),
    () => badgeLabel(answer.debt.basis) ?? answer.debt.basis,
  );
  const schedule = {
    // The plan's own basis is a sentence, so the label comes from where the plan's bookings came from.
    ...block(
      answer.schedule,
      (v) => ({ day: v.day, status: v.status, source: v.source, served: v.booked?.served ?? null, waiting: v.booked?.waiting ?? null, stopLoads: v.stops.map((stop) => ({ stopId: stop.stop_id, loads: stop.loads })) }),
      (v) => (v === null ? "UNAVAILABLE" : v.source === "supplied_bookings" ? "DERIVED" : "SIMULATION"),
    ),
    basis: answer.schedule.basis,
  };
  return {
    wardId: answer.ward_id,
    wardName: answer.ward_name,
    need: { serviceClass: answer.need.service_class, needWeight: answer.need.need_weight, basis: answer.need.need_basis },
    bookings: { count: answer.bookings.bookings, from: answer.bookings.period.from, to: answer.bookings.period.to, basis: answer.bookings.basis },
    deliveries,
    debt,
    schedule,
  };
}
