/** U7: turns the plan routes (GET /plans, GET /plans/{id}, GET /plans/{id}/confidence; docs/api_shapes.md
 * sections 8-9 and docs/api_additions/plans.md) into the allocation plan screen's view types.
 * Unavailable values stay null, never zero; a malformed answer gives null so the screen does not
 * show part of a plan. */
import type { ApiError } from "./api";
import { reasonForError, type FallbackReason } from "./evidenceAdapter";

/** Days `POST /plans` can build: P2's committed A8 replay window. */
export const REPLAY_FIRST_DAY = "2025-03-01";
export const REPLAY_LAST_DAY = "2025-07-31";

/** The three need weights (F7): water access, phone access, hardship. */
export type Weights = { wad: number; cad: number; hardship: number };
export type PlanSummary = { id: string; day: string; status: string; flagsTotal: number | null; checkedTotal: number | null; simulation: boolean; weights: Weights | null; source: string | null };
/** `defaultWeights` and `maxWeight` are what the server will use and allow; null when it did not say. */
export type PlanList = { total: number; items: PlanSummary[]; defaultWeights: Weights | null; maxWeight: number | null };

export type FlagRow = { group: string; confidence: number | null; reason: string | null; checked: boolean; checkReason: string | null };
/** One booking group in the day's queue. `served` is null when the server cut a station's list short. */
export type QueueRow = { group: string; served: number | null; confidence: number | null; needsCheck: boolean; checked: boolean };
export type ScheduleRow = { wardId: string; litres: number | null; floor: number | null; status: string | null; unrouted: string | null };
export type OutageView = { critical: number | null; allocations: number | null; unusedLitres: number | null; countsTowardDebt: boolean | null; basis: Record<string, string> };
export type ConfidenceView = { threshold: number | null; thresholdBasis: string | null; calibrationStatus: string | null; groups: number; belowThreshold: number };

/** Served and waiting bookings of one group (section or ward) in the day's plan. */
export type GroupTotals = { served: number; waiting: number };

/** Service type of a section (F7): cut today, water on a schedule, heavy or normal booker. */
export type SectionCategory = "cut" | "scheduled" | "heavy" | "normal" | "unknown";
/** A plan by section in figures (GET /plans/{id} `overview`, plan_overview.py). */
export type PlanFacts = {
  bookings: number; carried: number; commercial: number; tiers: [number, number, number]; servedTiers: [number, number, number];
  served: number; waiting: number; trips: number; fleetTankers: number; tripsPerTanker: number; reserveTrips: number; reserveUsedTrips: number;
  outageTrips: number; bookedTrips: number; scheduledSections: number; cutSections: number; criticalStops: number; stations: number; loadLitres: number; litresPerPerson: number;
};
export type Water = { litres: number; people: number; loads: number; full: boolean; hoursCutOff: number | null };
export type SectionRow = {
  group: string; name: string; category: SectionCategory; bookings: number; carried: number; tiers: [number, number, number]; servedTiers: [number, number, number];
  served: number; waiting: number; bookingsPer1000: number | null; peerBookingsPer1000: number | null; station: string | null; needEstimated: boolean;
  noWaterShare: number | null; fairShare: number; scheduled: Water | null; outage: Water | null; criticalLitres: number;
};
/** One filling station's queue: its bookings per section and the order the fair queue served them. */
export type StationQueue = { station: string; trips: number; bookedTrips: number; bookings: Record<string, number>; served: { group: string; reason: string }[] };
export type PlanOverview = { facts: PlanFacts; sections: SectionRow[]; stations: StationQueue[]; heavyCutoff: number | null; heavyPercentile: number | null };

export type LivePlan = {
  id: string; day: string; status: string; approved: boolean; approvedBy: string | null; approvalReason: string | null;
  basis: { plan: string | null; entitlement: string | null; flags: string | null; weights: string | null };
  /** The need weights the plan was built with; null when the answer has none (never invented). */
  weights: (Weights & { isDefault: boolean }) | null;
  /** A readable name per group (ward name or section name); null where none is known. */
  names: Record<string, string | null>;
  /** planner_replay (the committed replay) or supplied_bookings; null when the answer does not say. */
  source: string | null;
  /** "section" for a plan by section (real month totals divided by days), else "ward". */
  unit: "section" | "ward";
  /** fleet or tight for a plan by section; null otherwise. */
  capacityScenario: string | null;
  /** Served and waiting bookings per group; for a plan by section also per ward (shared by building share). */
  groupTotals: Record<string, GroupTotals>;
  wardTotals: Record<string, GroupTotals> | null;
  wardUnplaced: GroupTotals | null;
  bookingsSupplied: number | null;
  trips: number | null; reserveTrips: number | null; outageTrips: number | null; served: number | null; waiting: number | null; stationsTotal: number | null;
  queue: QueueRow[]; flags: FlagRow[]; flagsTotal: number; checkedTotal: number; unchecked: string[];
  schedule: ScheduleRow[]; scheduledTotal: number | null; unroutedTotal: number | null;
  outage: OutageView; confidence: ConfidenceView;
  /** Set only for a plan by section; null when absent or malformed (the screen then shows less). */
  overview: PlanOverview | null;
};

/** One group that gains or loses booked trips under a plan's weights. */
export type CompareRow = { group: string; name: string | null; servedDefault: number; servedWeighted: number; change: number };
export type CompareView = { against: string; weights: Weights; defaultWeights: Weights; gainers: CompareRow[]; losers: CompareRow[] };

export type { FallbackReason };

type Row = Record<string, unknown>;

const isRow = (value: unknown): value is Row => typeof value === "object" && value !== null && !Array.isArray(value);
const num = (value: unknown): number | null => (typeof value === "number" && Number.isFinite(value) ? value : null);
const text = (value: unknown): string | null => (typeof value === "string" ? value : null);
const count = (value: unknown): number | null => (Array.isArray(value) ? value.length : null);
const rows = (value: unknown): Row[] => (Array.isArray(value) ? value.filter(isRow) : []);

function weightsOf(value: unknown): Weights | null {
  if (!isRow(value)) return null;
  const wad = num(value.wad);
  const cad = num(value.cad);
  const hardship = num(value.hardship);
  return wad === null || cad === null || hardship === null ? null : { wad, cad, hardship };
}

/** Sum of numbers; null as soon as one is unavailable. */
function sum(values: (number | null)[]): number | null {
  return values.reduce<number | null>((total, value) => (total === null || value === null ? null : total + value), 0);
}

export function adaptPlanList(raw: unknown): PlanList | null {
  if (!isRow(raw) || !Array.isArray(raw.items)) return null;
  const items = rows(raw.items);
  if (items.some((item) => typeof item.plan_id !== "string" || typeof item.day !== "string")) return null;
  return {
    total: num(raw.total) ?? items.length,
    defaultWeights: weightsOf(raw.default_weights),
    maxWeight: num(raw.max_weight),
    items: items
      .map((item) => ({
        id: item.plan_id as string,
        day: item.day as string,
        status: text(item.status) ?? "UNKNOWN",
        flagsTotal: num(item.flags_total),
        checkedTotal: num(item.checked_total),
        simulation: isRow(item.basis) && (text(item.basis.plan) ?? "").startsWith("SIMULATION"),
        weights: weightsOf(item.weights),
        source: text(item.source),
      }))
      .sort((a, b) => b.day.localeCompare(a.day)),
  };
}

function toConfidence(raw: unknown): { view: ConfidenceView; byGroup: Map<string, Row> } | null {
  if (!isRow(raw) || !Array.isArray(raw.groups)) return null;
  const groups = rows(raw.groups).filter((group) => typeof group.group === "string");
  const calibration = isRow(raw.calibration) ? raw.calibration : {};
  return {
    byGroup: new Map(groups.map((group) => [group.group as string, group])),
    view: {
      threshold: num(raw.threshold),
      thresholdBasis: text(raw.threshold_basis),
      calibrationStatus: text(calibration.status),
      groups: groups.length,
      belowThreshold: groups.filter((group) => group.needs_check === true).length,
    },
  };
}

function totalsOf(value: unknown): Record<string, GroupTotals> | null {
  if (!isRow(value)) return null;
  const out: Record<string, GroupTotals> = {};
  for (const [key, row] of Object.entries(value)) {
    const served = isRow(row) ? num(row.served) : null;
    const waiting = isRow(row) ? num(row.waiting) : null;
    if (served === null || waiting === null) return null;
    out[key] = { served, waiting };
  }
  return out;
}

export function adaptLivePlan(rawPlan: unknown, rawConfidence: unknown): LivePlan | null {
  const confidence = toConfidence(rawConfidence);
  if (!confidence || !isRow(rawPlan) || typeof rawPlan.plan_id !== "string" || typeof rawPlan.day !== "string") return null;
  if (!isRow(rawPlan.stations) || !isRow(rawPlan.flags) || !isRow(rawPlan.checked) || !isRow(rawPlan.scheduled) || !isRow(rawPlan.outage)) return null;
  const stations = Object.values(rawPlan.stations).filter(isRow);
  const checked = rawPlan.checked;
  const confidenceOf = (group: string, fallback: unknown) => {
    const scored = confidence.byGroup.get(group);
    return scored ? num(scored.confidence) : num(fallback);
  };

  const flags: FlagRow[] = Object.entries(rawPlan.flags)
    .map(([group, flag]) => {
      const row = isRow(flag) ? flag : {};
      return { group, confidence: confidenceOf(group, row.confidence), reason: text(row.reason), checked: group in checked, checkReason: text(checked[group]) };
    })
    .sort((a, b) => a.group.localeCompare(b.group));

  // Per-group served counts are only exact when every station sent its whole served list.
  const complete = stations.every((station) => count(station.served) !== null && count(station.served) === num(station.served_total));
  const servedBy = new Map<string, number>();
  for (const station of stations) for (const booking of rows(station.served)) {
    const group = text(booking.group);
    if (group) servedBy.set(group, (servedBy.get(group) ?? 0) + 1);
  }
  const queue: QueueRow[] = [...confidence.byGroup.entries()]
    .map(([group, row]) => ({ group, served: complete ? servedBy.get(group) ?? 0 : null, confidence: num(row.confidence), needsCheck: row.needs_check === true, checked: group in checked }))
    .sort((a, b) => (b.served ?? 0) - (a.served ?? 0) || a.group.localeCompare(b.group));

  const unrouted = new Map(rows(rawPlan.unrouted).flatMap((item) => (typeof item.place_id === "string" ? [[item.place_id, text(item.reason)] as const] : [])));
  const schedule: ScheduleRow[] = Object.entries(rawPlan.scheduled)
    .map(([wardId, share]) => {
      const row = isRow(share) ? share : {};
      return { wardId, litres: num(row.litres), floor: num(row.floor), status: text(row.status), unrouted: unrouted.get(wardId) ?? null };
    })
    .sort((a, b) => a.wardId.localeCompare(b.wardId));

  const outage = rawPlan.outage;
  const basis = isRow(rawPlan.basis) ? rawPlan.basis : {};
  const planWeights = weightsOf(rawPlan.weights);
  const names = isRow(rawPlan.group_names)
    ? Object.fromEntries(Object.entries(rawPlan.group_names).map(([group, name]) => [group, typeof name === "string" ? name : null]))
    : {};
  const status = text(rawPlan.status) ?? "UNKNOWN";
  return {
    id: rawPlan.plan_id,
    day: rawPlan.day,
    status,
    approved: status === "APPROVED",
    approvedBy: text(rawPlan.approved_by),
    approvalReason: text(rawPlan.approval_reason),
    basis: { plan: text(basis.plan), entitlement: text(basis.effective_entitlement), flags: text(basis.flags), weights: text(basis.weights) },
    weights: planWeights && isRow(rawPlan.weights) ? { ...planWeights, isDefault: rawPlan.weights.is_default === true } : null,
    names,
    source: text(rawPlan.source),
    unit: rawPlan.unit === "section" ? "section" : "ward",
    capacityScenario: text(rawPlan.capacity_scenario),
    groupTotals: totalsOf(rawPlan.group_totals) ?? {},
    wardTotals: totalsOf(rawPlan.ward_totals),
    wardUnplaced: isRow(rawPlan.ward_unplaced) && num(rawPlan.ward_unplaced.served) !== null && num(rawPlan.ward_unplaced.waiting) !== null ? { served: rawPlan.ward_unplaced.served as number, waiting: rawPlan.ward_unplaced.waiting as number } : null,
    bookingsSupplied: num(rawPlan.bookings_supplied),
    trips: stations.length ? sum(stations.map((station) => num(station.trips))) : null,
    reserveTrips: num(rawPlan.reserve_trips),
    outageTrips: num(rawPlan.outage_trips),
    served: stations.length ? sum(stations.map((station) => num(station.served_total))) : null,
    waiting: stations.length ? sum(stations.map((station) => num(station.waiting_total))) : null,
    stationsTotal: num(rawPlan.stations_total),
    queue,
    flags,
    flagsTotal: flags.length,
    checkedTotal: flags.filter((flag) => flag.checked).length,
    unchecked: flags.filter((flag) => !flag.checked).map((flag) => flag.group),
    schedule,
    scheduledTotal: num(rawPlan.scheduled_total),
    unroutedTotal: num(rawPlan.unrouted_total),
    outage: {
      critical: count(outage.critical),
      allocations: count(outage.allocations),
      unusedLitres: num(outage.unused_litres),
      countsTowardDebt: typeof outage.counts_toward_water_debt === "boolean" ? outage.counts_toward_water_debt : null,
      basis: isRow(outage.basis) ? Object.fromEntries(Object.entries(outage.basis).filter((entry): entry is [string, string] => typeof entry[1] === "string")) : {},
    },
    confidence: confidence.view,
    overview: overviewOf(rawPlan.overview, stations),
  };
}

const triple = (value: unknown): [number, number, number] | null => {
  if (!Array.isArray(value) || value.length !== 3) return null;
  const [a, b, c] = value.map(num);
  return a === null || b === null || c === null ? null : [a, b, c];
};
const CATEGORIES = new Set(["cut", "scheduled", "heavy", "normal", "unknown"]);

function waterOf(value: unknown): Water | null {
  if (!isRow(value)) return null;
  const litres = num(value.litres), people = num(value.people), loads = num(value.loads);
  if (litres === null || people === null || loads === null) return null;
  return { litres, people, loads, full: value.full === true, hoursCutOff: num(value.hours_cut_off) };
}

function overviewOf(raw: unknown, stations: Row[]): PlanOverview | null {
  if (!isRow(raw) || !isRow(raw.facts) || !Array.isArray(raw.sections) || !Array.isArray(raw.stations)) return null;
  const f = raw.facts;
  const tiers = triple(f.tiers), servedTiers = triple(f.served_tiers);
  const keys = ["bookings", "carried", "commercial", "served", "waiting", "trips", "fleet_tankers", "trips_per_tanker", "reserve_trips", "reserve_used_trips", "outage_trips", "booked_trips", "scheduled_sections", "cut_sections", "critical_stops", "stations", "load_litres", "litres_per_person"] as const;
  const v = Object.fromEntries(keys.map((k) => [k, num(f[k])]));
  if (!tiers || !servedTiers || keys.some((k) => v[k] === null)) return null;
  const facts: PlanFacts = {
    bookings: v.bookings!, carried: v.carried!, commercial: v.commercial!, tiers, servedTiers, served: v.served!, waiting: v.waiting!, trips: v.trips!,
    fleetTankers: v.fleet_tankers!, tripsPerTanker: v.trips_per_tanker!, reserveTrips: v.reserve_trips!, reserveUsedTrips: v.reserve_used_trips!, outageTrips: v.outage_trips!,
    bookedTrips: v.booked_trips!, scheduledSections: v.scheduled_sections!, cutSections: v.cut_sections!, criticalStops: v.critical_stops!, stations: v.stations!,
    loadLitres: v.load_litres!, litresPerPerson: v.litres_per_person!,
  };
  const sections: SectionRow[] = [];
  for (const r of rows(raw.sections)) {
    const t = triple(r.tiers), st = triple(r.served_tiers);
    const name = text(r.name), group = text(r.group);
    if (!t || !st || !name || !group) return null;
    sections.push({
      group, name, category: (CATEGORIES.has(String(r.category)) ? r.category : "unknown") as SectionCategory,
      bookings: num(r.bookings) ?? 0, carried: num(r.carried) ?? 0, tiers: t, servedTiers: st, served: num(r.served) ?? 0, waiting: num(r.waiting) ?? 0,
      bookingsPer1000: num(r.bookings_per_1000), peerBookingsPer1000: num(r.peer_bookings_per_1000), station: text(r.station), needEstimated: r.need_estimated === true,
      noWaterShare: num(r.no_water_share), fairShare: num(r.fair_share) ?? 0, scheduled: waterOf(r.scheduled), outage: waterOf(r.outage), criticalLitres: num(r.critical_litres) ?? 0,
    });
  }
  // The order each station served its bookings in (position order, as the fair queue decided).
  const servedAt = new Map<string, { group: string; reason: string }[]>();
  for (const station of stations) {
    const id = text(station.station);
    if (!id) continue;
    const list = rows(station.served).filter((b) => typeof b.group === "string").sort((a, b) => (num(a.position) ?? 0) - (num(b.position) ?? 0));
    servedAt.set(id, list.map((b) => ({ group: b.group as string, reason: text(b.reason) ?? "DRR" })));
  }
  const queues: StationQueue[] = rows(raw.stations).flatMap((s) => {
    const id = text(s.station_id);
    if (!id || !isRow(s.bookings)) return [];
    const bookings = Object.fromEntries(Object.entries(s.bookings).filter((e): e is [string, number] => typeof e[1] === "number"));
    return [{ station: id, trips: num(s.trips) ?? 0, bookedTrips: num(s.booked_trips) ?? 0, bookings, served: servedAt.get(id) ?? [] }];
  });
  const cats = isRow(raw.categories) ? raw.categories : {};
  return { facts, sections, stations: queues, heavyCutoff: num(cats.heavy_cutoff), heavyPercentile: num(cats.heavy_percentile) };
}

/** Why the sample plan is shown instead of live plans (same rules as the atlas screen). */
export function planReason(error: ApiError): FallbackReason {
  return reasonForError(error);
}

function compareRows(value: unknown): CompareRow[] | null {
  if (!Array.isArray(value)) return null;
  const out: CompareRow[] = [];
  for (const item of rows(value)) {
    const servedDefault = num(item.served_default);
    const servedWeighted = num(item.served_weighted);
    const change = num(item.change);
    if (typeof item.group !== "string" || servedDefault === null || servedWeighted === null || change === null) return null;
    out.push({ group: item.group, name: text(item.name), servedDefault, servedWeighted, change });
  }
  return out.length === value.length ? out : null;
}

/** GET /plans/{id}/compare: who gains and who loses booked trips under a plan's weights. */
export function adaptCompare(raw: unknown): CompareView | null {
  if (!isRow(raw) || typeof raw.against !== "string") return null;
  const weights = weightsOf(raw.weights);
  const defaultWeights = weightsOf(raw.default_weights);
  const gainers = compareRows(raw.gainers);
  const losers = compareRows(raw.losers);
  if (!weights || !defaultWeights || !gainers || !losers) return null;
  return { against: raw.against, weights, defaultWeights, gainers, losers };
}
