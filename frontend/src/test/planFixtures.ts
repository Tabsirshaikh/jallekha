/** Small plan API responses in the real shapes (checked against a running API on 2026-10-04:
 * POST /plans {"day":"2025-05-01"}, GET /plans, GET /plans/{id}, /confidence, check, approve). */

const BASIS = {
  plan: "SIMULATION (A7 replay main_2025, tight, seed 0; daily arrivals SYNTHETIC, monthly totals REAL)",
  effective_entitlement: "DERIVED (A2 Census 2011 need; A3 fallback median where flagged)",
  flags: "DERIVED (T9 gate: min of available signals; threshold 0.50 PROVISIONAL)",
  weights: "ASSUMED policy weights (configured defaults): need weight = 1 + 2 x water-access deficit + 1 x no-phone share + 1 x hardship",
};

export const WEIGHTED_ID = "replay-2025-05-01-w5-0-0";
export const WEIGHTS = { wad: 5, cad: 0, hardship: 0 };
export const SUPPLIED_ID = "plan-2026-10-03-ab12cd34";
const NAMES: Record<string, string | null> = { "ward:relation/7848824": "Ward 105 Gachibowli", "ward:relation/7852805": "Ward 76 Serilingampally", "section:ADARSHNAGAR": "ADARSHNAGAR", "ward:relation/9999999": null };

const FLAG_BASIS = "DERIVED; min of available signals; threshold 0.50";

export const FLAGGED = ["section:ADARSHNAGAR", "ward:relation/7852805"] as const;

function served(group: string, count: number, start: number) {
  return Array.from({ length: count }, (_, i) => ({ booking_id: `2025-04-29:X:${String(start + i).padStart(5, "0")}`, group, position: start + i, reason: "DRR", lender: null }));
}

export function planBody(checked: Record<string, string> = {}, status: "DRAFT" | "APPROVED" = "DRAFT", approval: { by: string; reason: string } | null = null, weighted = false, supplied = 0) {
  return {
    plan_id: supplied ? SUPPLIED_ID : weighted ? WEIGHTED_ID : "replay-2025-05-01",
    source: supplied ? "supplied_bookings" : "planner_replay",
    bookings_supplied: supplied || null,
    weights: weighted ? { ...WEIGHTS, is_default: false } : { wad: 2, cad: 1, hardship: 1, is_default: true },
    group_names: NAMES,
    day: supplied ? "2026-10-03" : "2025-05-01",
    status,
    digest: "ef7b720b266de246534bd366618796bc81a17548900ecaff51bada0ca250a298",
    reserve_trips: 325,
    outage_trips: 0,
    special_tankers: [],
    approved_by: approval?.by ?? null,
    approval_reason: approval?.reason ?? null,
    stations: {
      ST01: { station: "ST01", trips: 406, booked_trips: 386, lent: 0, borrowed: 0, served: [...served("ward:relation/7848824", 3, 1), ...served("section:ADARSHNAGAR", 1, 4)], waiting: ["2025-04-29:X:00387"], served_total: 4, waiting_total: 1 },
      ST02: { station: "ST02", trips: 12, booked_trips: 10, lent: 0, borrowed: 2, served: served("ward:relation/7852805", 2, 1), waiting: [], served_total: 2, waiting_total: 0 },
    },
    stations_total: 2,
    transfers: [{ lender: "ST30", borrower: "ST02", trips: 2, round_trip_km: 2.574 }],
    transfers_total: 1,
    scheduled: {
      "relation/7848824": { ward_id: "relation/7848824", litres: 127542.41237198106, floor: 214399.92285, target: 214399.92285, status: "FLOOR_NOT_MET" },
      "relation/7848859": { ward_id: "relation/7848859", litres: null, floor: 130536.65898000001, target: 130536.65898000001, status: "FLOOR_NOT_MET" },
    },
    scheduled_total: 2,
    outage: {
      critical: [], allocations: [], ended: [], unused_litres: 9735000, counts_toward_water_debt: false,
      basis: { people: "DERIVED (Census 2011 population via E2) or officer count", lpcd: "ASSUMED (F10 10-15 lpcd)", priority: "ASSUMED deprivation weight exp(hours / tau)" },
    },
    effective_entitlement: { "section:ADARSHNAGAR": 13024.602141999998 },
    flags: {
      "section:ADARSHNAGAR": { confidence: 0.0, needs_check: true, reason: "weakest census_join_quality=0.0000 (section not placed on a ward: need is the A3 fallback); used: census_join_quality, section_location; unavailable: data_age, evidence_age, forecast_interval_width", basis: FLAG_BASIS },
      "ward:relation/7852805": { confidence: 0.25, needs_check: true, reason: "weakest section_location=0.2500 (NEAREST_500M); used: census_join_quality, section_location; unavailable: data_age, evidence_age, forecast_interval_width", basis: FLAG_BASIS },
    },
    flags_total: 2,
    checked,
    unrouted: [{ kind: "scheduled", place_id: "relation/7848824", litres: 127542.41237198106, reason: "NEEDS_SERVICE_POINT" }],
    unrouted_total: 1,
    special_stops: [],
    routing: null,
    basis: weighted ? { ...BASIS, weights: "ASSUMED policy weights chosen by an officer for this plan: need weight = 1 + 5 x water-access deficit + 0 x no-phone share + 0 x hardship" } : BASIS,
  };
}

const unavailableSignals = [
  { name: "data_age", available: false, score: null, basis: "Census 2011, 15 years old; excluded" },
  { name: "forecast_interval_width", available: false, score: null, basis: "T2 forecast not merged: no interval width" },
  { name: "evidence_age", available: false, score: null, basis: "no dated evidence in the repo" },
];

function group(name: string, confidence: number | null, needsCheck: boolean) {
  return {
    group: name, confidence, needs_check: needsCheck,
    reason: `weakest signal for ${name}`,
    used: ["census_join_quality", "section_location"],
    unavailable: ["data_age", "evidence_age", "forecast_interval_width"],
    signals: [{ name: "census_join_quality", available: true, score: confidence, basis: "min(census_coverage, dominant_source_share)" }, ...unavailableSignals],
  };
}

export const confidenceBody = {
  threshold: 0.5,
  threshold_basis: "PROVISIONAL",
  calibration: {
    row_type: "selection", threshold: 0.5, group_days: 17363, unflagged_group_days: 11500, matched_unflagged: 10887, match_share: 0.9467,
    match_share_basis: "not_separable: target 0.90 already met with nothing flagged, so the replay cannot tell thresholds apart; PROVISIONAL threshold kept (OPEN, owner to confirm)",
    groups: 152, flagged_groups: 60, flagged_share: 0.3947, flagged_share_basis: "DERIVED; groups with T9 confidence below the threshold, over replay groups",
    status: "not_separable", label: "SIMULATION",
  },
  groups: [group("section:ADARSHNAGAR", 0.0, true), group("ward:relation/7848824", 0.5, false), group("ward:relation/7852805", 0.25, true)],
};

export function listBody(checkedTotal = 0, status: "DRAFT" | "APPROVED" = "DRAFT", withWeighted = false, withSupplied = false) {
  const item = (id: string, weights: typeof WEIGHTS | null, source = "planner_replay", day = "2025-05-01") => ({ plan_id: id, day, status, basis: BASIS, flags_total: 2, checked_total: checkedTotal, created_at: "2026-10-04T15:17:45.312034+00:00", weights, source });
  const items = withWeighted ? [item("replay-2025-05-01", null), item(WEIGHTED_ID, WEIGHTS)] : [item("replay-2025-05-01", null)];
  if (withSupplied) items.push(item(SUPPLIED_ID, null, "supplied_bookings", "2026-10-03"));
  return { total: items.length, offset: 0, limit: 200, items, default_weights: { wad: 2, cad: 1, hardship: 1 }, max_weight: 5 };
}

export const compareBody = {
  against: "replay-2025-05-01", day: "2025-05-01", weights: WEIGHTS, default_weights: { wad: 2, cad: 1, hardship: 1 },
  gainers: [{ group: "ward:relation/7848824", name: "Ward 105 Gachibowli", served_default: 192, served_weighted: 200, change: 8 }, { group: "section:ADARSHNAGAR", name: "ADARSHNAGAR", served_default: 25, served_weighted: 26, change: 1 }],
  losers: [{ group: "ward:relation/7852805", name: null, served_default: 144, served_weighted: 136, change: -8 }],
  all_changes: [], basis: "SIMULATION (same replay day, same trips; only the need weights differ)",
};

export function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

export function apiError(status: number, code: string, message: string): Response {
  return json({ error: { code, message, details: null } }, status);
}

export type Call = { method: string; path: string; body: unknown };

/** A stateful stand-in for the plan routes: checks and approval change what later GETs return. */
export function planServer(options: { userId?: string | null; plans?: boolean; approve?: (body: unknown) => Response; compare?: Response } = {}) {
  const calls: Call[] = [];
  const checked: Record<string, string> = {};
  let approval: { by: string; reason: string } | null = null;
  let stored = options.plans ?? true;
  let weightedStored = false;
  let suppliedCount = 0;
  const fetchMock = (url: string, init?: RequestInit): Promise<Response> => {
    const parsed = new URL(url, "http://localhost");
    const path = decodeURIComponent(parsed.pathname);
    const method = init?.method ?? "GET";
    const body = typeof init?.body === "string" ? JSON.parse(init.body) : undefined;
    calls.push({ method, path: parsed.pathname, body });
    if (path === "/auth/me") return Promise.resolve(json({ role: "officer", user_id: options.userId === undefined ? "off-1" : options.userId }));
    if (path === "/plans" && method === "GET") return Promise.resolve(json(stored ? listBody(Object.keys(checked).length, approval ? "APPROVED" : "DRAFT", weightedStored, suppliedCount > 0) : { total: 0, offset: 0, limit: 200, items: [] }));
    if (path === "/plans" && method === "POST") {
      const day = (body as { day?: string }).day;
      const bookings = (body as { bookings?: { section: string }[] }).bookings;
      if (bookings) {
        if (bookings.some((b) => b.section === "BAD")) return Promise.resolve(apiError(422, "validation_error", "booking 1: section is not an HMWSSB section with a station and need data"));
        suppliedCount = bookings.length;
        return Promise.resolve(json(planBody(checked, "DRAFT", null, false, suppliedCount), 201));
      }
      const weights = (body as { weights?: typeof WEIGHTS }).weights;
      if (weights && (weights.wad !== 2 || weights.cad !== 1 || weights.hardship !== 1)) {
        const existedW = weightedStored;
        weightedStored = true;
        return Promise.resolve(json(planBody(checked, "DRAFT", null, true), existedW ? 200 : 201));
      }
      // Only 2025-05-01 has replay data in this stand-in; any other day answers like a day outside the window.
      if (day !== "2025-05-01") return Promise.resolve(apiError(404, "not_found", `No replay data for ${day}: the replay covers 2025-03-01 to 2025-07-31`));
      const existed = stored;
      stored = true;
      return Promise.resolve(json(planBody(checked), existed ? 200 : 201));
    }
    if (path === `/plans/${SUPPLIED_ID}` && suppliedCount) return Promise.resolve(json(planBody({ ...checked }, "DRAFT", null, false, suppliedCount)));
    if (path === `/plans/${SUPPLIED_ID}/confidence` && suppliedCount) return Promise.resolve(json(confidenceBody));
    if (path === `/plans/${WEIGHTED_ID}` && weightedStored) return Promise.resolve(json(planBody({ ...checked }, "DRAFT", null, true)));
    if (path === `/plans/${WEIGHTED_ID}/confidence` && weightedStored) return Promise.resolve(json(confidenceBody));
    if (path === `/plans/${WEIGHTED_ID}/compare` && weightedStored) return Promise.resolve(options.compare ?? json(compareBody));
    if (path === "/plans/replay-2025-05-01" && stored) return Promise.resolve(json(planBody({ ...checked }, approval ? "APPROVED" : "DRAFT", approval)));
    if (path === "/plans/replay-2025-05-01/confidence" && stored) return Promise.resolve(json(confidenceBody));
    const check = path.match(/^\/plans\/replay-2025-05-01\/groups\/(.+)\/check$/);
    if (check && method === "POST") {
      checked[check[1]] = (body as { reason: string }).reason;
      return Promise.resolve(json({ plan_id: "replay-2025-05-01", group: check[1], checked: true, unchecked_flags: FLAGGED.filter((g) => !(g in checked)), ledger_seq: 2, ledger_event: "ward_reviewed" }));
    }
    if (path === "/plans/replay-2025-05-01/approve" && method === "POST") {
      if (options.approve) return Promise.resolve(options.approve(body));
      const { officer_id, reason } = body as { officer_id: string; reason: string };
      approval = { by: officer_id, reason };
      return Promise.resolve(json(planBody(checked, "APPROVED", approval)));
    }
    return Promise.resolve(apiError(404, "not_found", "Not found"));
  };
  return { fetchMock, calls, checked };
}
