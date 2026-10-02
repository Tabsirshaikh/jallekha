# Person 1 (P1): Data and Evidence Tasks

**Owner:** P1 (Yaseer)
**Area:** Real-data pipeline and evidence layer (F1-F4)
**Current status:** `R-P1` is complete and in review; implementation tasks remain `TODO` pending S1 and review.

## Required order

| Order | ID | Task | Start after | Done when |
|---:|---|---|---|---|
| 1 | R-P1 | Re-research newer ward population/water-access data, ward crosswalks, building/population rasters, section boundaries, and spatial under-reporting methods. | Immediately | `docs/research/P1.md` is merged with checked links and keep/change/add decisions. Time-box: 2 days. |
| 2 | S2 | Port only verified research data into `data/raw/` and verification records into `data/verification/`. | S1 repository skeleton | Raw files remain unchanged; `SOURCES.md` and checksums are recorded; no hand-typed v1 tables. |
| 3 | D1 | Fetch OSM district/mandal boundaries, DataMeet zone table, OSM HMWSSB points, Open Buildings Temporal data, and National Water Data Portal groundwater levels. | R-P1 and S2 | Every file has URL, retrieval date, licence, coverage and a `REAL` basis record. |
| 4 | E1 | Build the 2009 Census-to-2016 ward polygon crosswalk using number, name and location checks, with mandal fallback. | D1 | Match coverage is reported; known missing wards are never falsely matched; header and join tests pass. |
| 5 | E2 | Produce the ward evidence table: population, Water Access Deficit (WAD), Channel Access Deficit (CAD), hardship, facilities and data-quality flags. | E1 | Failed joins remain empty; every derived field has a `_basis`; tests pass. **Merge this early because P2, P3 and P4 depend on it.** |
| 6 | E3 | Calculate ward growth adjustment from Open Buildings 2016-2023. | D1 and E2 | Growth ratio is produced per ward, labelled `DERIVED`, and checked against section booking growth. |
| 7 | E4 | Build booking-equity outputs: Gini coefficient, Lorenz curve, top-10% share, bookings per 1,000 people and seasonality. | E2 | Reproduces section Gini `0.78` and top 21 sections `67.7%`; ward estimates carry approximation labels. |
| 8 | E5 | Build the under-served detector using a negative-binomial/BYM2 spatial model with peer-median fallback. | E2 and E3 | Flags are stable across model variants; reasons use real values; output says “field check required,” never “proven neglect.” |
| 9 | E6 | Export coverage-map GeoJSON from E2, E4 and E5. | E4 and E5 | Three layers work: water-access need, bookings per 1,000 and coverage gap; no unsupported 500 m public-tap layer. |

## Branches

`research/p1` → `feat/s2-data` → `feat/d1-fetch` → `feat/e1-crosswalk` → `feat/e2-evidence` → `feat/e3-growth` → `feat/e4-equity` → `feat/e5-underserved` → `feat/e6-coverage`

## P1 rules for every task

- Wait for S1 before code/data PRs; research can begin immediately.
- One task per branch and pull request; never push directly to `main`.
- Do not edit raw source data or invent missing values.
- Record source URL, date, licence, geography, granularity and checksum.
- Label each value `REAL`, `DERIVED`, `ASSUMED`, `SYNTHETIC` or `TO FETCH`.
- Add `_basis` and quality fields to derived outputs.
- Add meaningful tests and run `python tasks.py test` and `python tasks.py lint` before review.
- Use only numbers re-verified in `data/verification/V-VERIFY_REVIEW.md` for slides.

## Critical handoffs

- **E2 → P2:** service models and ward need weights.
- **E2 → P3:** explanations and confidence gate.
- **D1 → P3:** forecast/shortage groundwater inputs.
- **E2/E4/E5 → P4:** Atlas, Booking Equity and Under-served screens.

## Immediate next action

Review and merge `research/p1`. Then wait for P3 to merge S1 and begin S2. Do not start feature code before the R-P1 research note is reviewed and merged.
