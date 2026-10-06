/** U5: turns the T10 evidence routes into the water-access screen's view types (same shape as the
 * committed snapshot built by scripts/frontend/build_u5_snapshot.py). Unavailable values stay null. */
import type { ApiError } from "./api";

export type FieldReason = { code: string; model?: string; value: number | null; threshold: number | null; basis: string };
export type Ward = {
  id: string; name: string; censusYear: number | null; reviewRequired: boolean;
  population2011: number | null; households2011: number | null; waterAccessDeficitShare: number | null;
  constrainedAccessShare?: number | null; hardshipShare?: number | null;
  /** Fair-queue need score (1 + weighted WAD, CAD, hardship; backend service_models.need_weight). */
  needWeight?: number | null;
  /** Field check (E5): bookings seen, and what similar wards and the statistical model expected. */
  observedBookings?: number | null; peerExpected?: number | null; modelExpected?: number | null;
  /** OSM hospitals, clinics, UPHCs, schools and care homes placed in the ward (D9); null if not served. */
  criticalFacilities: number | null;
  growthRatio: number | null; growthQuality: string | null; bookings: number | null; bookingsPer1000: number | null;
  bookingStatus: string | null; fieldStatus: string; fieldCandidate: boolean | null;
  fieldReasons: FieldReason[];
};
export type EquitySummary = {
  bookings: number; delivered: number; gini: number; top_section_count: number; top_booking_share: number;
  bottom_section_count: number; bottom_booking_share: number; section_count: number; missing_source_months: string[];
  interpretation: string;
};
export type EvidenceDataset = {
  /** Date the saved snapshot was built; null when the API served the data just now. */
  snapshotDate: string | null; geographyVersion: string; wards: Ward[];
  summary: {
    wardCount: number; censusMappedCount: number; censusReviewCount: number;
    fieldCheckCount: number | null; eligibleCount: number | null; dataReviewCount: number | null;
    equity: EquitySummary;
  };
};
export type Feature = { geometry: { type: "Polygon" | "MultiPolygon"; coordinates: unknown }; properties: { ward_id: string; ward_name: string } };
export type LiveEvidence = { dataset: EvidenceDataset; features: Feature[] };

/** Raw answers of /atlas/wards, /equity/wards, /equity/summary, /underserved/field-checks and
 * /coverage/layers/water_access_evidence (docs/api_shapes.md sections 2-5). */
export type LiveEvidenceInput = { atlas: unknown; equityWards: unknown; equitySummary: unknown; fieldChecks: unknown; layer: unknown };

export type FallbackReason = "signIn" | "forbidden" | "unreachable" | "serverError" | "incomplete";

type Row = Record<string, unknown>;

const isRow = (value: unknown): value is Row => typeof value === "object" && value !== null && !Array.isArray(value);
const num = (value: unknown): number | null => (typeof value === "number" && Number.isFinite(value) ? value : null);
const text = (value: unknown): string | null => (typeof value === "string" ? value : null);

/** All rows of a complete first page ({total, items}); null when the page is missing or short. */
function allItems(page: unknown, key = "items", totalKey = "total"): Row[] | null {
  if (!isRow(page) || !Array.isArray(page[key])) return null;
  const items = (page[key] as unknown[]).filter(isRow);
  const total = num(page[totalKey]);
  if (total === null || items.length !== total) return null;
  return items;
}

function byWard(rows: Row[]): Map<string, Row> {
  return new Map(rows.flatMap((row) => (typeof row.ward_id === "string" ? [[row.ward_id, row] as const] : [])));
}

function toReason(raw: Row): FieldReason {
  const model = text(raw.model);
  return { code: text(raw.code) ?? "UNKNOWN", ...(model ? { model } : {}), value: num(raw.value), threshold: num(raw.threshold), basis: text(raw.basis) ?? "UNAVAILABLE" };
}

export function toWard(evidence: Row, equity: Row | undefined, field: Row | undefined): Ward {
  const candidate = field?.field_check_candidate;
  return {
    id: String(evidence.ward_id),
    name: text(evidence.ward_name) ?? String(evidence.ward_id),
    censusYear: num(evidence.census_year),
    reviewRequired: evidence.review_required === true,
    population2011: num(evidence.population),
    households2011: num(evidence.households),
    waterAccessDeficitShare: num(evidence.wad),
    constrainedAccessShare: num(evidence.cad),
    hardshipShare: num(evidence.hardship),
    observedBookings: num(field?.observed_bookings),
    peerExpected: isRow(field?.model_scores) && isRow(field.model_scores.PEER_MEDIAN) ? num(field.model_scores.PEER_MEDIAN.expected) : null,
    modelExpected: isRow(field?.model_scores) && isRow(field.model_scores.NB) ? num(field.model_scores.NB.expected) : null,
    criticalFacilities: num(evidence.critical_facilities),
    growthRatio: num(field?.growth_ratio_context_only),
    growthQuality: text(field?.growth_quality),
    bookings: num(equity?.bookings),
    bookingsPer1000: num(equity?.bookings_per_1000),
    bookingStatus: text(equity?.mapping_status),
    fieldStatus: text(field?.status) ?? "UNAVAILABLE",
    fieldCandidate: typeof candidate === "boolean" ? candidate : null,
    fieldReasons: Array.isArray(field?.reasons) ? (field.reasons as unknown[]).filter(isRow).map(toReason) : [],
  };
}

function toEquity(raw: unknown): EquitySummary | null {
  if (!isRow(raw)) return null;
  const numbers = ["bookings", "delivered", "gini", "top_section_count", "top_booking_share", "bottom_section_count", "bottom_booking_share", "section_count"] as const;
  if (numbers.some((key) => num(raw[key]) === null)) return null;
  const months = Array.isArray(raw.missing_source_months) ? raw.missing_source_months.filter((m): m is string => typeof m === "string") : [];
  return { ...(Object.fromEntries(numbers.map((key) => [key, raw[key]])) as Record<(typeof numbers)[number], number>), missing_source_months: months, interpretation: text(raw.interpretation) ?? "" };
}

function toFeatures(layer: unknown): Feature[] | null {
  if (!isRow(layer) || !Array.isArray(layer.features)) return null;
  return layer.features.filter((feature): feature is Feature =>
    isRow(feature) && isRow(feature.geometry) && (feature.geometry.type === "Polygon" || feature.geometry.type === "MultiPolygon")
    && isRow(feature.properties) && typeof feature.properties.ward_id === "string");
}

/** The screen's data from the live API, or null when any answer is missing, short or malformed. */
export function adaptLiveEvidence(input: LiveEvidenceInput): LiveEvidence | null {
  const atlas = allItems(input.atlas);
  const equityRows = allItems(input.equityWards);
  const fieldRows = isRow(input.fieldChecks) ? allItems(input.fieldChecks, "rows", "rows_total") : null;
  const equity = toEquity(input.equitySummary);
  const features = toFeatures(input.layer);
  if (!atlas || !equityRows || !fieldRows || !equity || !features || !isRow(input.fieldChecks)) return null;
  const equityById = byWard(equityRows);
  const fieldById = byWard(fieldRows);
  const wards = atlas.filter((row) => typeof row.ward_id === "string").map((row) => toWard(row, equityById.get(row.ward_id as string), fieldById.get(row.ward_id as string)));
  const summary = isRow(input.fieldChecks.summary) ? input.fieldChecks.summary : {};
  const geographyVersion = (isRow(input.layer) ? text(input.layer.geography_version) : null) ?? text(atlas[0]?.geo_version) ?? "—";
  return {
    features,
    dataset: {
      snapshotDate: null,
      geographyVersion,
      wards,
      summary: {
        wardCount: wards.length,
        censusMappedCount: wards.filter((ward) => ward.population2011 !== null).length,
        censusReviewCount: wards.filter((ward) => ward.reviewRequired).length,
        fieldCheckCount: num(summary.field_check_count),
        eligibleCount: num(summary.eligible_count),
        dataReviewCount: num(summary.data_review_count),
        equity,
      },
    },
  };
}

/** Why the saved snapshot is shown instead of live data. */
export function reasonForError(error: ApiError): FallbackReason {
  if (error.status === 401) return "signIn";
  if (error.status === 403) return "forbidden";
  if (error.status === 0) return "unreachable";
  return "serverError";
}

/** U5 live need (GET /atlas/live): five clues per ward and booking concentration. */
export type Clue = { code: "owed" | "bookings" | "complaints" | "cuts" | "groundwater"; bad: boolean; known: boolean; counts: boolean; value: number | null; reference: number };
export type LiveWard = { id: string; needWeight: number | null; clues: Clue[]; badCount: number; knownCount: number; rising: boolean; bookingsWindow: number; usualMonth: number | null };
export type Concentration = { source: "live" | "history"; liveBookings: number; gini: number | null; topShare: number | null; topSections: number; sections: number; bookings: number; top: { section: string; bookings: number; share: number }[] };
export type LiveNeed = { windowDays: number; minBad: number; wards: Map<string, LiveWard>; concentration: Concentration };

export function adaptLiveNeed(raw: unknown): LiveNeed | null {
  if (!isRow(raw) || !Array.isArray(raw.wards) || !isRow(raw.concentration)) return null;
  const c = raw.concentration;
  const wards = new Map<string, LiveWard>();
  for (const w of raw.wards.filter(isRow)) {
    if (typeof w.ward_id !== "string" || !Array.isArray(w.clues)) return null;
    wards.set(w.ward_id, {
      id: w.ward_id,
      needWeight: isRow(w.need) ? num(w.need.need_weight) : null,
      clues: w.clues.filter(isRow).map((k) => ({ code: k.code as Clue["code"], bad: k.bad === true, known: k.known !== false, counts: k.counts !== false, value: num(k.value), reference: num(k.reference) ?? 0 })),
      badCount: num(w.bad_count) ?? 0, knownCount: num(w.known_count) ?? 4, rising: w.rising === true, bookingsWindow: num(w.bookings_window) ?? 0, usualMonth: num(w.usual_month_bookings),
    });
  }
  return {
    windowDays: num(raw.window_days) ?? 30, minBad: num(raw.min_bad_clues) ?? 2, wards,
    concentration: {
      source: c.source === "live" ? "live" : "history", liveBookings: num(c.live_bookings) ?? 0, gini: num(c.gini), topShare: num(c.top_share),
      topSections: num(c.top_sections) ?? 0, sections: num(c.sections) ?? 0, bookings: num(c.bookings) ?? 0,
      top: Array.isArray(c.top) ? c.top.filter(isRow).map((t) => ({ section: String(t.section), bookings: num(t.bookings) ?? 0, share: num(t.share) ?? 0 })) : [],
    },
  };
}

export type SectionCheck = {
  section_id: string; section: string; division: string; period_year: number;
  bookings: number; rate: number | null; reference_rate: number | null;
  field_check_candidate: boolean; ward_id: string | null; lat: number | null; lng: number | null;
  latest_outcome?: { could_not_book: string; checked_on: string } | null;
};

export function adaptSectionChecks(raw: unknown): SectionCheck[] | null {
  const items = allItems(raw);
  if (!items || items.some((r) => typeof r.section_id !== "string" || typeof r.section !== "string"
    || typeof r.field_check_candidate !== "boolean" || num(r.bookings) === null
    || num(r.period_year) === null)) return null;
  return items.map((r) => ({ section_id: String(r.section_id), section: String(r.section),
    division: String(r.division), period_year: Number(r.period_year), bookings: Number(r.bookings),
    rate: num(r.rate), reference_rate: num(r.reference_rate), field_check_candidate: r.field_check_candidate === true,
    ward_id: text(r.ward_id), lat: num(r.lat), lng: num(r.lng),
    latest_outcome: isRow(r.latest_outcome) ? { could_not_book: String(r.latest_outcome.could_not_book), checked_on: String(r.latest_outcome.checked_on) } : null }));
}
