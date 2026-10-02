# E1-FIX — historical location-validation repair

Branch: codex/e1-location-validation. Base: feat/e2-evidence, PR #8.

## Findings
This is BOTH a data gap and implementation error. D1 district/mandal sources are
Point centroids, not polygon boundaries. E1 did not check geometry, yet assigned
high confidence and reviewer_status=verified to ward-number candidates. Its README
zone parser expected headings, but the actual file is a Markdown table; zone lookup
was empty. Ward 37 has two distinct named polygons and cannot be resolved by number.
Five targets have multiple Census source assignments. Historic numeric equality
does not demonstrate equivalent boundaries, even when a target is inside a mandal.

## Repair
Remove false verified/high-confidence labels from candidate joins. Add location_status
and full state/district/subdistrict/town/ward identifiers. Correct table parser without
treating zone names as validation. Explicitly report candidate versus validated coverage.
Add a conservative validation path accepting reviewed official Census 2011 ward polygons;
require unique identifiers, unique source/target assignment and equal valid polygon geometry.
Points, current-vintage, ambiguous, unreviewed and different-footprint sources fail closed.
Different geometry requires a separately researched population-transfer crosswalk;
area overlap alone is not assumed to allocate population or amenities.
E2 receives precise location failure codes; no allocation block is removed by this repair.
Deterministic E1 artifacts and LF-normalized derived-text hashes make Linux/Windows CI reliable.
Raw source files remain unchanged. P1:E1-FIX CI and focused regression tests are added.

## Sources and limitations
Official Census lists ward 104 under Shaikpet in a compound administrative key:
https://censusindia.gov.in/nada/index.php/catalog/9834/study-description
Historical geography documentation:
https://censusindia.gov.in/nada/index.php/catalog/120
Official map portal returned HTTP 403 during verification:
https://www.ghmc.gov.in/PSWiseMaps.aspx
Polygon equality/intersection implementation documentation:
https://shapely.readthedocs.io/en/stable/reference/shapely.intersection.html
No authoritative machine-readable Census 2011 ward polygons or reviewed transfer table
were verified in this repair. No synthetic test geometry is installed as real data.

## Handoff
Place reviewed source polygons in data/verification/location/census2011_wards.geojson,
FeatureCollection EPSG:4326, with properties matching source_* codes, census_year=2011,
source_url to official gov.in/nic.in, reviewer_status=approved, reviewed_by and reviewed_at.
The input is hashed and its geometry is checked, not trusted based on a ward number.
Exact geometry validation proves only historical correspondence; it does not make
2011 demand current or automatically authorize public-service allocation.
The accurate demo remains a historical/provisional review view; use explicitly simulated
service zones for allocation until authoritative geography AND current demand are validated.


Expanded audit found another real defect: Hyderabad PCA mirror uses district 22 and
local mandal codes 01–16, whereas official HH-14 uses district 536 and mandal codes
04496–04511. Normalization now joins mandal name (five explicit spelling aliases),
town code and ward number to official HH-14, retaining original mirror codes.
Ward 37 first-match selection is removed: both target polygons remain unmatched.
Coverage distinguishes source candidate rows, unique target polygons and validated locations.
The unused heuristic mandal-to-zone dictionary is removed. Cross-district summaries are sorted.


Original-geography fallback: census_mandal_context.csv contains historical urban
subdistrict amenities (including 16 Hyderabad mandals). No ward mapping is implied;
Rangareddy urban-subdistrict scope may extend beyond GHMC. Verified transfer weights
are zero for all unvalidated candidates. Empty/malformed CRS inputs and duplicate
polygon identifiers fail closed. Hyderabad PCA sum agrees with 3,943,323 district
population, and all source administrative keys are unique after normalization.
Remaining requirements: authoritative historical polygons OR reviewed population-transfer
table; current household/demand observations; explicit policy for non-tap weights.
Mandal context supplies no population distribution across new ward boundaries.


## Final gap disposition
| Gap | Disposition |
| --- | --- |
| False high confidence / verified status | Fixed; only reviewed exact historical geometry may pass |
| Numeric-only crosswalk mistaken for validation | Fixed; candidate and validated coverage separate |
| Local mirror versus Census code systems | Fixed; original codes retained, HH-14 compound-key resolution |
| Ward 37 arbitrary first-polygon selection | Fixed; no first match or duplicated population |
| Multiple source rows / cross-district candidates | Detected and blocked; no speculative aggregation |
| README parser returned no zones | Fixed; table parsed, community context not authoritative proof |
| Silent missing/fractional/negative PCA counts | Fixed; malformed source counts fail instead of becoming zero |
| Reproducibility and line endings | Fixed; deterministic reports and canonical derived-text hashes |
| Weak verifier accepted changed summaries | Fixed; recomputes crosswalk, metrics, metadata and mandal table |
| Mandal fallback promised but not computed | Added original Census urban mandal context, not ward transfer |
| Wrong year, points, invalid geometry, duplicate IDs, CRS mismatch | Tested and rejected |
| Official Census 2011 ward footprints / transfer weights | DATA BLOCKER: no usable authoritative source verified |
| Target layer described as definitely 2016 | Explicit unverified historical 150-ward vintage; contract ID retained |
| Modern need inferred from old Census | Blocked; historical context never authorizes current allocation |

No claim of perfection or validated field geography is made. Code checks do not remove data blockers.

Final local tasks.py check PASS: 34 backend tests, 1 frontend test; all raw/D1/E1/E2 verifiers, Ruff formatting/lint, ESLint and TypeScript. Raw data unchanged.
PR: https://github.com/Tabsirshaikh/jallekha/pull/9; stacked base feat/e2-evidence. Code repair IN_REVIEW; E1 geographic completion remains pending authoritative data.
