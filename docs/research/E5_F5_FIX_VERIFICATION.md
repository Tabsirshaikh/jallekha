# Booking and forecast fix verification, 2026-10-07

Verified against fetched `origin/main` = `6b6bff1` in an isolated worktree. The five fix
commits (`f392396`, `c89aa24`, `27d4268`, `80d6989`, `085945b`) are ancestors of main.
This review reports implementation and measured results separately; passing software tests
does not establish model accuracy or prove hidden water demand. No forecast/model/UI code
or existing data is modified by this verification.
Performance figures below are DERIVED evaluations from saved artifacts; published booking
observations are REAL source counts. Section geography, transferred counts and capacities
retain their documented approximate or ASSUMED bases.

## Low bookings and the NB model

**Original problem:** section booking totals were assigned to one ward using one geocoded
point. The model treated those approximate allocations as ward observations. All six old
flags had only one or two sections pinned; low ward counts could be placement artifacts.
The ward NB diagnostic had rank correlation 0.30 and median miss 5.2x, weaker in ranking
than the household baseline (0.48). Changing the model alone cannot fix that observation error.

**Implemented:** operational screening now uses exact 2025 section/division bookings per
1,000 domestic connections. Similar-section reference excludes the target and uses division,
connection count and flats share. High approximate ward water need is context only. There
are 197 section identities and 12 visit candidates. Selected map dots expose actual bookings,
rates, peer rates and visit status; the old ward NB expected-count bars are removed from the
operational screen. Ward need scores were not removed. Archived ward model outputs remain
available for research, not allocation or the current visit list.

On **121 section pairs, 2024 inputs predicting 2025**, peers versus connections/city-rate baseline:

| Method | Rank correlation | Median miss | Within 2x |
|---|---:|---:|---:|
| Section peer reference | 0.3718 | 2.4824x | 38.02% |
| Connections x city rate | 0.1504 | 3.3103x | 28.10% |

This is an improvement against that baseline but still weak. It is a different cohort and
protocol from the old ward diagnostic, so the old/new numbers are not a direct accuracy comparison.
Flag precision remains unmeasured; low bookings are an investigation prompt, not proof that
people could not book.

**New under-reporting model:** tested a seeded, nonspatial NB/Binomial framework using need
and access inputs. Its three assumed-prior MAP fits were rejected: median misses 3.79-4.53x,
versus 3.61x for the city-rate baseline on 107 section pairs. Same-section 2024 persistence
performed much better (1.36x miss; 91.59% within 2x), but cannot detect persistent booking
barriers. MAP optimizer agreement is not posterior convergence. No validated true demand or
booking probability was produced, and this model is not used operationally.

**Ground loop:** officer/field-worker date, yes/no/unclear and note recording exists with
ledger digests and replay protection. Repo evidence records zero real ground outcomes.
Precision needs 30 distinct decisive outcomes; twelve current flags alone cannot reach it.

**Status:** the misleading operational ward comparison is corrected. Hidden demand and the
accuracy of flags are **not solved**. This is a defensible current approach, not a proven best
model. Better evidence is the next priority: observed booking barriers and official section GIS.
[Stoner et al.](https://arxiv.org/html/1809.00544v1) explain why identifying under-reporting
requires informative reporting information or fully observed counts; our assumed priors do not supply it.

## Ward booking estimates

One-point transfer was replaced with building-count-weighted approximate Voronoi/division cells.
Existing 2023 Open Buildings 32 m fractional-count rasters were used, **not individual vector
footprints**. 91.82% of 2025 bookings were allocated; 117,564 remained unplaced before the
separate location review. Ward counts retain DERIVED_APPROXIMATE labels; official service
boundaries are unavailable. The new review file has not yet been fed into that map.

The 107-ward sensitivity audit reduced median magnitude errors but worsened rankings for
NB, peers and the household baseline. It does not demonstrate geographic accuracy improvement.
**Status: approximate transfer implemented; exact ward estimation remains unsolved.**

## Forecast and shortage warnings

**Original problem:** January 2026 training cutoff, mostly past forecast months, no city
range, unreadable mixed chart, and a large summer underforecast across changed section names.

**Implemented:** city totals include all cached portal months through August 2026, independent
of the section re-cut. Twelve city months cover September 2026-August 2027. City residual
ranges, history/future distinction, capacity line, monthly retrospective forecast-versus-actual
view and four-language strings exist. One refresh command rebuilds forecast/shortage outputs.
Reservoir and groundwater data supply context. Geography uses conservative old/new matches:
63 approximate and 210 unmatched current sections; missing histories are not invented as zero.

**Measured results:** twelve candidates including baseline were evaluated on 31 common rolling
origins. No alternative passed the required improvement rule; seasonal naive was retained.
Its city mean absolute percentage error is **31.16%**, matched-section weighted error **46.57%**.
Some candidates improve one measure, so this does not mean every alternative is worse on
every metric. The original frozen February-August holdout still shows GBM 31.10% versus
naive 31.77%, confirming a near tie rather than an accuracy breakthrough.

Nominal 80% / 90% city ranges covered only **54.5% / 81.8%** of 22 held-back months.
The lower range substantially undercovers; one-step calibration does not establish coverage
for all twelve horizons. Most current sections lack reliable matched forecasts or capacities.

**New integration issue found during this verification:** subsequent station-assignment changes
left 42 saved shortage rows with stale capacity figures/reasons. Example: Ahmed Nagar,
September 2026, saved capacity 112.1 trips versus rebuilt 97.7. The forecast table retains the
old section capacity too. All individual risk categories and aggregate counts remain unchanged
(six high, 28 medium, 143 low, 642 unknown), but the saved artifacts no longer reproduce.
These capacity-dependent forecast/shortage outputs and snapshots need rebuilding together.
The data-only review intentionally preserves existing files.

**Status:** forecast refresh, city range and UI are implemented. Accurate summer forecasts,
well-calibrated ranges, complete section correspondence and consistent capacity artifacts
remain **partly or wholly unsolved**. Seasonal naive is the current choice under the owner's
selection rule, not a universally best forecast. Temporal validation against simple baselines
is sound practice; see [Forecasting: Principles and Practice](https://otexts.com/fpp3/accuracy.html).

## Validation and practical conclusion

- Full lint passes; all 200 frontend tests and translation checks pass.
- All task data verifiers pass, including exact section checks, approximate transfer and saved
  under-reporting results. Legacy ward-model verification remains archival only.
- Full backend in current-main-plus-location-review worktree: **1,025 passed, one failed**,
  `test_committed_risk_list_reproduces`, from the stale shortage artifact above.
- Four new location artifact tests failed first and then passed; all existing tracked data
  is preserved. The original separate booking and forecast branches previously had full green
  runs, but those results do not establish that later merged capacity inputs remain consistent.

The work improves the integrity of the comparison and the visibility of forecast errors.
It does not justify claiming accurate hidden-demand estimates, validated field flags or
reliable summer shortage predictions. The next useful work is ground evidence, official
section geography, consistent capacity rebuilding and interval/forecast evaluation on new months.
