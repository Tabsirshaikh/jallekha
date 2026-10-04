/** U5: turns the T10 evidence routes into the water-access screen's view types (same shape as the
 * committed snapshot built by scripts/frontend/build_u5_snapshot.py). Unavailable values stay null. */
import type { ApiError } from "./api";

export type FieldReason = { code: string; model?: string; value: number | null; threshold: number | null; basis: string };
export type Ward = {
  id: string; name: string; censusYear: number | null; reviewRequired: boolean;
  population2011: number | null; households2011: number | null; waterAccessDeficitShare: number | null;
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
