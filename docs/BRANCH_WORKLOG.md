# Branch worklog

This file records what each task branch discovered and changed. It lets a teammate understand, review, reproduce, or correct the work without relying on chat history.

## Required workflow

Every task branch must add or update its entry here before opening a pull request. Keep the entry concise and evidence based. Update it again if review changes the implementation.

Use this template:

```markdown
## `<branch>` — `<task-id>`

- **Owner / date:**
- **Purpose:**
- **What we found:** Facts, constraints, data gaps, failed assumptions, and important evidence links.
- **What we changed:** Files and behavior changed on this branch.
- **Validation:** Commands, tests, datasets, results, and the task-specific `<owner>:<task-id>` CI workflow. Distinguish simulated results from real observations.
- **Known limitations:** Remaining uncertainty, unavailable data, deferred scope, or operational risk.
- **Handoff / next step:** Dependencies created, who needs the output, and what must happen after merge.
- **Pull request:** URL or `pending`.
```

The pull-request description must summarize the same information and link to this file. A task cannot move from `IN_REVIEW` to `DONE` until its entry reflects the merged result.

## `research/p1` — `R-P1`

- **Owner / date:** P1 (Yaseer), 2026-10-01.
- **Purpose:** Recheck the data and methods behind F1-F4 before implementation.
- **What we found:**
  - Census 2011 is still the only verified official ward-level source found for household water and phone access; no newer ward-level replacement was verified.
  - The available DataMeet/OSM file contains only 145 polygons from the historical 2016 150-ward scheme. Official sources describe a 300-ward arrangement in December 2025 and a three-corporation reorganisation in February 2026. A current machine-readable boundary/crosswalk was not verified.
  - Open Buildings Temporal is useful for detecting building change, but its documented jitter, temporal instability and uncalibrated confidence prevent treating its building ratio as an exact household-growth ratio.
  - No authoritative public HMWSSB section polygons or section-to-ward crosswalk were verified. Section totals are exact; ward attribution is approximate.
  - Agostini et al. supports modelling latent spatial under-reporting, but BYM2 is a separate spatial prior from Riebler et al. Low bookings alone cannot prove unmet need.
- **What we changed:** Added `docs/research/P1.md`; froze the demo to versioned historical geography `GHMC_2016_150`; required effective dates and source quality for geography; changed F2 to compare Open Buildings, WorldPop and GHS-POP sensitivity estimates; changed F4 to negative-binomial and peer-median baselines with optional evaluated BYM2; revised D1, E1, E3 and E5 acceptance criteria; added `docs/P1_TASKS.md`.
- **Validation:** `python scripts/ci/verify_p1_r_p1.py` parses all 46 tracker rows, checks every F1-F4 decision and evidence marker, confirms solution corrections and validates this worklog. GitHub Actions runs it as `P1:R-P1`; `git diff --check` also passes. This branch changes documentation and specifications, so no application test suite exists yet.
- **Known limitations:** The demo can make historically anchored comparisons but cannot claim current ward-level water need. Current official polygons, a current crosswalk, HMWSSB section boundaries and field truth for under-reporting remain unavailable.
- **Handoff / next step:** One teammate and the owner review PR #2. After merge, mark R-P1 `DONE`. P1 then waits for S1 and starts S2; D1/E1/E3/E5 must follow the revised acceptance criteria.
- **Pull request:** https://github.com/Tabsirshaikh/jallekha/pull/2
