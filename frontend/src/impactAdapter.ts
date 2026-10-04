/** Maps T10's `GET /impact` answer (A8 sandbox summary) into the impact page's view rows.
 * Missing measures stay null; every measure carries the answer's basis label. */

export type Metric = "served_share" | "need_weighted_unmet_share" | "mean_wait_days" | "gini_fill_rate" | "jain_fill_rate" | "worst_group_fill_rate" | "km_per_kl";
export const METRICS: Metric[] = ["served_share", "need_weighted_unmet_share", "mean_wait_days", "gini_fill_rate", "jain_fill_rate", "worst_group_fill_rate", "km_per_kl"];

export type ImpactMetric = { mean: number | null; min: number | null; max: number | null; basis: string };
export type ImpactRow = { replay: string; scenario: string; policy: string; seed_count: number | null; label: string; metrics: Record<Metric, ImpactMetric> };
export type RealBaselines = { label: string; booking_gini_sections: number | null; booking_gini_basis: string; delivered_share: Record<string, number | null>; source: string };

type ApiMeasure = { mean?: number | null; min?: number | null; max?: number | null; seeds?: number | null };

export type ApiImpact = {
  label: string;
  seeds: number | null;
  replay: string;
  scenario: string;
  scenario_basis?: string | null;
  policies: Record<string, string>;
  results: Record<string, Record<string, ApiMeasure>>;
  real_baselines: RealBaselines;
  duplicate_merge_share: { value: number | null; basis: string; reason: string };
};

export type ImpactView = {
  rows: ImpactRow[];
  policies: Record<string, string>;
  baselines: RealBaselines;
  unavailableReason: string;
  scenarioBasis: string | null;
};

export function impactFromApi(answer: ApiImpact): ImpactView {
  const basis = answer.label;
  const rows = Object.keys(answer.results)
    .sort()
    .map((policy) => {
      const measures = answer.results[policy];
      const metrics = Object.fromEntries(
        METRICS.map((metric) => {
          const m = measures[metric];
          return [metric, { mean: m?.mean ?? null, min: m?.min ?? null, max: m?.max ?? null, basis }];
        }),
      ) as Record<Metric, ImpactMetric>;
      const seeds = METRICS.map((metric) => measures[metric]?.seeds).find((n) => typeof n === "number") ?? answer.seeds ?? null;
      return { replay: answer.replay, scenario: answer.scenario, policy, seed_count: seeds, label: basis, metrics };
    });
  return {
    rows,
    policies: answer.policies,
    baselines: answer.real_baselines,
    unavailableReason: answer.duplicate_merge_share.reason,
    scenarioBasis: answer.scenario_basis ?? null,
  };
}

/** A policy's mean minus B1's; blank (null) when either is missing, never treated as zero. */
export function policyDifference(value: number | null, reference: number | null): number | null {
  return value === null || reference === null ? null : value - reference;
}
