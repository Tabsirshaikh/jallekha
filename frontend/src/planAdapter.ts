/** U7: turns the plan routes (GET /plans, GET /plans/{id}, GET /plans/{id}/confidence; docs/api_shapes.md
 * sections 8-9 and docs/api_additions/plans.md) into the allocation plan screen's view types.
 * Unavailable values stay null, never zero; a malformed answer gives null so the screen does not
 * show part of a plan. */
import type { ApiError } from "./api";
import { reasonForError, type FallbackReason } from "./evidenceAdapter";

/** Days `POST /plans` can build: P2's committed A8 replay window. */
export const REPLAY_FIRST_DAY = "2025-03-01";
export const REPLAY_LAST_DAY = "2025-07-31";

export type PlanSummary = { id: string; day: string; status: string; flagsTotal: number | null; checkedTotal: number | null; simulation: boolean };
export type PlanList = { total: number; items: PlanSummary[] };

export type FlagRow = { group: string; confidence: number | null; reason: string | null; checked: boolean; checkReason: string | null };
/** One booking group in the day's queue. `served` is null when the server cut a station's list short. */
export type QueueRow = { group: string; served: number | null; confidence: number | null; needsCheck: boolean; checked: boolean };
export type ScheduleRow = { wardId: string; litres: number | null; floor: number | null; status: string | null; unrouted: string | null };
export type OutageView = { critical: number | null; allocations: number | null; unusedLitres: number | null; countsTowardDebt: boolean | null; basis: Record<string, string> };
export type ConfidenceView = { threshold: number | null; thresholdBasis: string | null; calibrationStatus: string | null; groups: number; belowThreshold: number };

export type LivePlan = {
  id: string; day: string; status: string; approved: boolean; approvedBy: string | null; approvalReason: string | null;
  basis: { plan: string | null; entitlement: string | null; flags: string | null };
  trips: number | null; reserveTrips: number | null; outageTrips: number | null; served: number | null; waiting: number | null; stationsTotal: number | null;
  queue: QueueRow[]; flags: FlagRow[]; flagsTotal: number; checkedTotal: number; unchecked: string[];
  schedule: ScheduleRow[]; scheduledTotal: number | null; unroutedTotal: number | null;
  outage: OutageView; confidence: ConfidenceView;
};

export type { FallbackReason };

type Row = Record<string, unknown>;

const isRow = (value: unknown): value is Row => typeof value === "object" && value !== null && !Array.isArray(value);
const num = (value: unknown): number | null => (typeof value === "number" && Number.isFinite(value) ? value : null);
const text = (value: unknown): string | null => (typeof value === "string" ? value : null);
const count = (value: unknown): number | null => (Array.isArray(value) ? value.length : null);
const rows = (value: unknown): Row[] => (Array.isArray(value) ? value.filter(isRow) : []);

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
    items: items
      .map((item) => ({
        id: item.plan_id as string,
        day: item.day as string,
        status: text(item.status) ?? "UNKNOWN",
        flagsTotal: num(item.flags_total),
        checkedTotal: num(item.checked_total),
        simulation: isRow(item.basis) && (text(item.basis.plan) ?? "").startsWith("SIMULATION"),
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
  const status = text(rawPlan.status) ?? "UNKNOWN";
  return {
    id: rawPlan.plan_id,
    day: rawPlan.day,
    status,
    approved: status === "APPROVED",
    approvedBy: text(rawPlan.approved_by),
    approvalReason: text(rawPlan.approval_reason),
    basis: { plan: text(basis.plan), entitlement: text(basis.effective_entitlement), flags: text(basis.flags) },
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
  };
}

/** Why the sample plan is shown instead of live plans (same rules as the atlas screen). */
export function planReason(error: ApiError): FallbackReason {
  return reasonForError(error);
}
