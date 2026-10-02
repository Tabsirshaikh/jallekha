# P1 integration into main — 2 October 2026

Branch: `codex/p1-main-integration`, based on current `origin/main`.

## What we found

PRs #3 (S1), #4 (S2), #9 (E1 repair), and #10 (E4) were still open. Several other PRs had been merged into their parent feature branches rather than main; merges happened in different order, so no one parent contained the entire latest chain. Conflicts were in the shared solution specification and feature tracker.

The E1 repair CI failed because it ran all backend tests after E3 was added without installing rasterio. The same broad test invocation would affect E4 and the S1 full-suite job after integration. The research verifier also assumed the original 46-row tracker and pre-implementation wording; the implemented tracker adds E1-FIX and documents stricter data gates.

## What we changed

- Preserved main's P1/P3/P4 research and merged the complete E6, S2, E1 repair, and E5 branch histories. E4 and S1 head commits are already ancestors of these branches.
- Kept implemented F2/F3/F4 safeguards while retaining other contributors' updated forecasting, speech, ledger, geography, and source notes.
- Scoped E1 repair and E4 CI to their task tests; S1 remains the full-repository check and now installs the geo/model extras it needs.
- Updated research verification for the 47-row tracker and implemented evidence gates. Independent WorldPop/GHS-POP sensitivity remains explicitly deferred rather than falsely claimed complete.
- Added LF handling for generated GeoJSON so clean Windows checkouts retain reproducible bytes.
- Updated completed task records, retaining their original PR links and unresolved data limitations.
- Added `P1:integration` to verify all four open PR heads remain ancestors and source files contain no conflict markers.

## Validation and handoff

Run `python tasks.py check`, `python scripts/ci/verify_p1_r_p1.py`, and `python scripts/ci/verify_main_integration.py`. The integration PR targets main and must have passing checks before merge. Original stacked PRs become redundant after their exact heads are contained in main; close them only after verifying that ancestry.

This merge completes the implemented task scope. Census location validation, current ward geography, booking-to-ward transfer, missing private/legacy data, and operational field validation remain unavailable as documented in individual task worklogs.
