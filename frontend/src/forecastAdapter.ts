/** Maps T10 forecast / backtest / shortage rows (docs/api_shapes.md sections 6 and 7) into the
 * forecast screen's view types. Missing numbers stay null; every number keeps its basis. */

export type BasisTag = "REAL" | "DERIVED" | "SIMULATION" | "ASSUMED" | "UNAVAILABLE";
export type Risk = "high" | "medium" | "low" | "unknown";

export type ApiPage<T> = { items: T[]; total: number; basis?: string; reason?: string };

export type ApiForecastRow = {
  level: string;
  section: string | null;
  month: string;
  model: string;
  point: number | null;
  point_basis: string | null;
  lower_80: number | null;
  upper_80: number | null;
  lower_80_basis: string | null;
  upper_80_basis: string | null;
  lower_90: number | null;
  upper_90: number | null;
  lower_90_basis: string | null;
  upper_90_basis: string | null;
  capacity_trips?: number | null;
  capacity_trips_basis?: string | null;
  updated_through?: string;
  match_status?: string;
};

export type ApiHistoryRow = {month: string; level: string; section: string | null; actual: number | null; actual_basis: string; updated_through?: string};
export type ApiAccuracyRow = ApiHistoryRow & {point: number | null; error_pct: number | null; capacity_trips?: number | null};

export type ApiBacktestRow = {
  run: string;
  row_type: string;
  model: string | null;
  origin: string | number | null;
  months: number | null;
  section_months: number | null;
  city_mape: number | null;
  city_mape_basis: string | null;
  section_wape: number | null;
  section_wape_basis: string | null;
  note: string | null;
};

export type ApiShortageRow = {
  section: string;
  month: string;
  months_ahead: number | null;
  forecast_bookings: number | null;
  forecast_bookings_basis: string | null;
  upper_80: number | null;
  upper_80_basis: string | null;
  capacity_trips: number | null;
  capacity_trips_basis: string | null;
  capacity_ratio: number | null;
  capacity_ratio_basis: string | null;
  risk: string | null;
  reason: string | null;
  groundwater_status: string | null;
};

/** One forecast month as the outlook chart and detail panel draw it. */
export type OutlookMonth = {
  month: string;
  median: number | null;
  low80: number | null;
  high80: number | null;
  low90: number | null;
  high90: number | null;
  capacity: number | null;
  basis: BasisTag;
  rangeBasis: BasisTag;
  capacityBasis: BasisTag;
  /** The API's own words when the interval is unavailable. */
  rangeNote: string | null;
};

export type FixtureMonth = { month: string; low80: number; high80: number; low90: number; high90: number; median: number; capacity: number; basis: string };

export type ShortageRow = {
  key: string;
  section: string;
  month: string;
  monthsAhead: number | null;
  forecast: number | null;
  forecastBasis: BasisTag;
  upper80: number | null;
  upper80Basis: BasisTag;
  capacity: number | null;
  capacityBasis: BasisTag;
  ratio: number | null;
  ratioBasis: BasisTag;
  risk: Risk;
  reason: string;
  groundwaterUnavailable: boolean;
};

export type BacktestComparison = { run: string; model: string; origin: string | null; months: number | null; cityMape: number | null; sectionWape: number | null; basis: BasisTag };
export type BacktestSummary = {
  comparisons: BacktestComparison[];
  selected: { model: string; note: string } | null;
  notRun: { model: string; note: string }[];
};

const TAGS: BasisTag[] = ["REAL", "DERIVED", "SIMULATION", "ASSUMED", "UNAVAILABLE"];

/** "DERIVED: sum of ..." -> "DERIVED". Anything without a known leading word is UNAVAILABLE. */
export function basisTag(text: string | null | undefined): BasisTag {
  const word = (text ?? "").trim().split(/[\s:]/, 1)[0].toUpperCase();
  return (TAGS as string[]).includes(word) ? (word as BasisTag) : "UNAVAILABLE";
}

function detail(text: string | null | undefined): string | null {
  if (!text) return null;
  const at = text.indexOf(":");
  return at < 0 ? null : text.slice(at + 1).trim() || null;
}

export function outlookFromFixture(rows: FixtureMonth[]): OutlookMonth[] {
  return rows.map((row) => ({
    month: row.month,
    median: row.median,
    low80: row.low80,
    high80: row.high80,
    low90: row.low90,
    high90: row.high90,
    capacity: row.capacity,
    basis: "SIMULATION",
    rangeBasis: "SIMULATION",
    capacityBasis: "SIMULATION",
    rangeNote: null,
  }));
}

/** `shortage` supplies the ASSUMED capacity for a section's months (T8); city rows have none. */
export function outlookFromApi(rows: ApiForecastRow[], shortage: ShortageRow[]): OutlookMonth[] {
  return [...rows]
    .sort((a, b) => a.month.localeCompare(b.month))
    .map((row) => {
      const capacityRow = row.section === null ? undefined : shortage.find((s) => s.section === row.section && s.month === row.month);
      const capacity = row.capacity_trips ?? capacityRow?.capacity ?? null;
      const rangeBasis = basisTag(row.lower_80_basis);
      return {
        month: row.month,
        median: row.point,
        low80: row.lower_80,
        high80: row.upper_80,
        low90: row.lower_90,
        high90: row.upper_90,
        capacity,
        basis: basisTag(row.point_basis),
        rangeBasis,
        capacityBasis: capacity === null ? "UNAVAILABLE" : row.capacity_trips != null ? basisTag(row.capacity_trips_basis) : (capacityRow?.capacityBasis ?? "UNAVAILABLE"),
        rangeNote: rangeBasis === "UNAVAILABLE" ? detail(row.lower_80_basis) : null,
      };
    });
}

function risk(word: string | null): Risk {
  return word === "high" || word === "medium" || word === "low" ? word : "unknown";
}

export function shortageFromApi(rows: ApiShortageRow[]): ShortageRow[] {
  return rows.map((row) => ({
    key: `${row.section}|${row.month}`,
    section: row.section,
    month: row.month,
    monthsAhead: row.months_ahead,
    forecast: row.forecast_bookings,
    forecastBasis: basisTag(row.forecast_bookings_basis),
    upper80: row.upper_80,
    upper80Basis: basisTag(row.upper_80_basis),
    capacity: row.capacity_trips,
    capacityBasis: basisTag(row.capacity_trips_basis),
    ratio: row.capacity_ratio,
    ratioBasis: basisTag(row.capacity_ratio_basis),
    risk: risk(row.risk),
    reason: row.reason ?? "",
    groundwaterUnavailable: (row.groundwater_status ?? "UNAVAILABLE") === "UNAVAILABLE",
  }));
}

/** Unknown sits above low: a missing capacity can hide a real risk. */
export const RISK_ORDER: Risk[] = ["high", "medium", "unknown", "low"];

export function sortByRisk(rows: ShortageRow[]): ShortageRow[] {
  return [...rows].sort(
    (a, b) =>
      RISK_ORDER.indexOf(a.risk) - RISK_ORDER.indexOf(b.risk) ||
      (b.ratio ?? -Infinity) - (a.ratio ?? -Infinity) ||
      a.month.localeCompare(b.month) ||
      a.section.localeCompare(b.section),
  );
}

/** Models compared on the origins every model shares (a fair comparison), plus T2's selection note. */
export function summarizeBacktest(rows: ApiBacktestRow[]): BacktestSummary {
  const comparisons = rows
    .filter((row) => row.row_type === "summary_common_origins" && row.model)
    .map((row) => ({
      run: row.run,
      model: row.model ?? "",
      origin: row.origin === null ? null : String(row.origin),
      months: row.months,
      cityMape: row.city_mape,
      sectionWape: row.section_wape,
      basis: basisTag(row.city_mape_basis),
    }))
    .sort((a, b) => a.run.localeCompare(b.run) || (a.model === "seasonal_naive" ? -1 : b.model === "seasonal_naive" ? 1 : a.model.localeCompare(b.model)));
  const selectedRow = rows.find((row) => row.row_type === "selected");
  const notRun = new Map<string, string>();
  rows.filter((row) => row.row_type === "not_run" && row.model).forEach((row) => notRun.set(row.model ?? "", row.note ?? ""));
  return {
    comparisons,
    selected: selectedRow?.model ? { model: selectedRow.model, note: selectedRow.note ?? "" } : null,
    notRun: [...notRun].map(([model, note]) => ({ model, note })),
  };
}

export function sectionsFromForecast(rows: ApiForecastRow[]): string[] {
  return [...new Set(rows.map((row) => row.section).filter((s): s is string => Boolean(s)))].sort((a, b) => a.localeCompare(b));
}
