# Exact section low-booking checks (F4)

`GET /underserved/section-checks?offset=0&limit=200`, officer bearer token only.
Returns `schema_version`, `basis`, `limitations`, `validation`, `flagged_count`,
and the usual `total`, `offset`, `limit`, `items` pagination.

Each item identifies `section_id` (`division:section`), section name, division and calendar
`period_year` (2025). `bookings` is the sum of published rows (REAL); `booking_months` makes
partial years explicit. `domestic_connections` is the mean monthly billing count (DERIVED),
using D, DS, DM, DP, M0, M1, M4, MB; `flats_connection_share` uses M0, M1, M4, MB.
`rate` is annual bookings per 1,000 domestic connections, not a monthly rate.
Missing/incomplete denominators or years produce null rates, never measured zero.

`reference_rate` is the median of at most five nearest complete sections in the same division,
excluding the target, by absolute log connection ratio plus twice the difference in flats share.
At least three peers are required. `peer_sections` lists them. `ratio_threshold` is the 2024
leave-target-out ratio's 20th percentile. Those choices are ASSUMED in `config/section_checks.py`.
`field_check_candidate` also requires `wad_context > wad_cohort_median`. The median uses distinct
wards, not section-weighted repeats. Census need and geocoded points are DERIVED_APPROXIMATE
context only; `ward_id`, `ward_name`, `lat`, `lng` can be null. No allocation changes result.
The screen hides basis labels; data and API retain them.

`validation` reports 2024-only predictions against complete 2025 observations on the same
section/division identities. Both peers and city-rate baseline use 2024 connection exposure.
It includes Spearman correlation, median symmetric multiplicative miss, fraction within 2x,
mean absolute error, paired sample count and zero pairs excluded from multiplicative measures.
This is prediction accuracy, not flag precision. There are no field outcomes yet.

Rebuild: `.venv/Scripts/python.exe scripts/evidence/build_section_checks.py`.
Verify: `.venv/Scripts/python.exe scripts/evidence/verify_section_checks.py`.
The verifier recomputes outputs, input digests, validation and the U5 section snapshot.

Legacy `/underserved/field-checks` ward outputs remain for compatibility/research. Their
point-assigned booking numbers are unsuitable evidence of ward under-booking and are no longer
displayed by U5's checks tab or ward panel. See F3/F4 limitations.
