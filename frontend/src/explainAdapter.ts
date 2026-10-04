/** Maps T10 explain and contest answers (docs/api_shapes.md sections 10 and 11) into the explanation
 * screen's view types. Missing values stay null; a ward without Census data shows no number. */
import type { ApiError } from "./api";

type Debt = { available: boolean; account_id: string | null; debt_litres: number | null; cap_litres: number | null; in_debt_since: string | null };

export type ApiWardResponse = {
  explanation: {
    ward_id: string;
    ward_name: string;
    status: string;
    service_class: string;
    class_basis: string;
    join_status: string;
    allocation_eligible: boolean;
    review_required: boolean;
    quality_flags: string[];
    check_reasons: string[];
    census_label: string;
    need_weight: number | null;
    need_basis: string | null;
    wad: number | null;
    wad_basis: string | null;
    cad: number | null;
    cad_basis: string | null;
    hardship: number | null;
    hardship_basis: string | null;
    households: number | null;
    households_basis: string | null;
    entitlement: number | null;
    critical_facilities: number | null;
    critical_facilities_basis: string | null;
    debt: Debt;
  };
};

export type ApiChange = { input: string; amount: number; step: number; from_value: number | string; to_value: number | string; after_place: number };
export type ApiCounterfactual = { booking_id: string; status: string; before_place: number; changes: ApiChange[]; not_inputs: [string, string][] };

export type ApiBookingResponse = {
  explanation: {
    booking_id: string;
    status: string;
    group: string;
    tier: number;
    arrived_at: string;
    place: number | null;
    position: number | null;
    reason: string | null;
    arrival_rank: number | null;
    entitlement: number | null;
    quantum: number | null;
    deficit_before: number | null;
    capacity: number | null;
    cap_reason: string | null;
    waiting_hours: number | null;
    debt: Debt;
  };
  counterfactual?: ApiCounterfactual | null;
};

export type ApiContest = {
  contest_id: string;
  created_at: string;
  filed_by: string;
  role: string;
  target_type: string;
  target_id: string;
  reason_code: string;
  reason_text: string;
  status: string;
};
export type ApiReply = { reply_id: string; created_at: string; officer_id: string; outcome_code: string; reason_text: string };
export type ApiContestDetail = ApiContest & { reply: ApiReply | null };
export type ApiContestPage = { total: number; offset: number; limit: number; items: ApiContest[] };
/** POST /contests and POST /contests/{id}/reply. */
export type ApiContestResult = { status: string; contest_id: string | null; reply_id: string | null; ledger_seq: number | null; error: string | null };

export type Num = { value: number | null; basis: string | null };

export type WardView = {
  id: string;
  name: string;
  hasCensus: boolean;
  serviceClass: string;
  classBasis: string;
  joinStatus: string;
  reviewRequired: boolean;
  qualityFlags: string[];
  checkReasons: string[];
  censusLabel: string;
  needWeight: Num;
  wad: Num;
  cad: Num;
  hardship: Num;
  households: Num;
  entitlement: Num;
  criticalFacilities: Num;
  debtAvailable: boolean;
};

export type BookingView = {
  id: string;
  status: string; // served | waiting | rejected
  group: string;
  tier: number;
  arrivedAt: string;
  place: number | null;
  position: number | null;
  reason: string | null;
  arrivalRank: number | null;
  entitlement: number | null;
  quantum: number | null;
  deficitBefore: number | null;
  capacity: number | null;
  capReason: string | null;
  waitingHours: number | null;
  debtAvailable: boolean;
};

/** One "what would have to change" step; the screen words it. */
export type CounterfactualStep =
  | { kind: "tier"; from: number | null; to: number | null; after: number }
  | { kind: "arrival"; minutes: number; after: number }
  | { kind: "entitlement"; percent: number; after: number }
  | { kind: "deficit"; amount: number; after: number }
  | { kind: "other"; input: string; after: number };

export type CounterfactualView = { status: "found" | "already_first" | "none"; before: number | null; steps: CounterfactualStep[]; notInputs: string[] };

export type ReplyView = { id: string; createdAt: string; officerId: string; outcome: string; text: string };
export type ContestView = {
  id: string;
  createdAt: string;
  targetType: string;
  targetId: string;
  reasonCode: string;
  text: string;
  status: string; // open | replied
  /** undefined: not loaded yet (list rows carry no reply); null: no reply. */
  reply?: ReplyView | null;
};

const num = (value: number | null | undefined, basis: string | null | undefined, show: boolean): Num => ({ value: show ? (value ?? null) : null, basis: basis ?? null });

export function wardFromApi(response: ApiWardResponse): WardView {
  const e = response.explanation;
  const hasCensus = e.status === "census";
  return {
    id: e.ward_id,
    name: e.ward_name,
    hasCensus,
    serviceClass: e.service_class,
    classBasis: e.class_basis,
    joinStatus: e.join_status,
    reviewRequired: e.review_required,
    qualityFlags: e.quality_flags ?? [],
    checkReasons: e.check_reasons ?? [],
    censusLabel: e.census_label,
    needWeight: num(e.need_weight, e.need_basis, hasCensus),
    wad: num(e.wad, e.wad_basis, hasCensus),
    cad: num(e.cad, e.cad_basis, hasCensus),
    hardship: num(e.hardship, e.hardship_basis, hasCensus),
    households: num(e.households, e.households_basis, hasCensus),
    entitlement: num(e.entitlement, hasCensus ? "DERIVED" : null, hasCensus),
    criticalFacilities: num(e.critical_facilities, e.critical_facilities_basis, true),
    debtAvailable: e.debt?.available ?? false,
  };
}

function step(change: ApiChange): CounterfactualStep {
  const after = change.after_place;
  if (change.input === "tier") return { kind: "tier", from: typeof change.from_value === "number" ? change.from_value : null, to: typeof change.to_value === "number" ? change.to_value : null, after };
  if (change.input === "arrival") return { kind: "arrival", minutes: change.amount, after };
  if (change.input === "group_entitlement") return { kind: "entitlement", percent: Math.round(change.amount * 100), after };
  if (change.input === "group_deficit") return { kind: "deficit", amount: change.amount, after };
  return { kind: "other", input: change.input, after };
}

export function counterfactualFromApi(cf: ApiCounterfactual | null | undefined): CounterfactualView | null {
  if (!cf) return null;
  const status = cf.status === "found" ? "found" : cf.status === "already_first" ? "already_first" : "none";
  return { status, before: cf.before_place ?? null, steps: (cf.changes ?? []).map(step), notInputs: (cf.not_inputs ?? []).map(([code]) => code) };
}

export function bookingFromApi(response: ApiBookingResponse): { booking: BookingView; counterfactual: CounterfactualView | null } {
  const e = response.explanation;
  return {
    booking: {
      id: e.booking_id,
      status: e.status,
      group: e.group,
      tier: e.tier,
      arrivedAt: e.arrived_at,
      place: e.place ?? null,
      position: e.position ?? null,
      reason: e.reason ?? null,
      arrivalRank: e.arrival_rank ?? null,
      entitlement: e.entitlement ?? null,
      quantum: e.quantum ?? null,
      deficitBefore: e.deficit_before ?? null,
      capacity: e.capacity ?? null,
      capReason: e.cap_reason ?? null,
      waitingHours: e.waiting_hours ?? null,
      debtAvailable: e.debt?.available ?? false,
    },
    counterfactual: counterfactualFromApi(response.counterfactual),
  };
}

export function contestFromApi(item: ApiContest): ContestView {
  return {
    id: item.contest_id,
    createdAt: item.created_at,
    targetType: item.target_type,
    targetId: item.target_id,
    reasonCode: item.reason_code,
    text: item.reason_text,
    status: item.status,
  };
}

export function contestDetailFromApi(detail: ApiContestDetail): ContestView {
  const reply = detail.reply;
  return {
    ...contestFromApi(detail),
    reply: reply ? { id: reply.reply_id, createdAt: reply.created_at, officerId: reply.officer_id, outcome: reply.outcome_code, text: reply.reason_text } : null,
  };
}

export function contestsFromApi(page: ApiContestPage): { items: ContestView[]; total: number } {
  return { items: (page.items ?? []).map(contestFromApi), total: page.total ?? 0 };
}

export type ErrorKind = "unreachable" | "rejected" | "forbidden" | "notFound" | "conflict" | "invalid" | "error";

/** The server's answer in plain terms; the screen words each one. */
export function errorKind(error: ApiError): ErrorKind {
  switch (error.status) {
    case 0: return "unreachable";
    case 401: return "rejected";
    case 403: return "forbidden";
    case 404: return "notFound";
    case 409: return "conflict";
    case 422: return "invalid";
    default: return "error";
  }
}
