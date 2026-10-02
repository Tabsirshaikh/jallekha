# `fix/t1-followup` — `T1` follow-up

- **Owner / date:** P3, 2026-10-02.
- **Purpose:** Fix two problems in P3's own T1 code that the S3 review found, and record T1 as DONE after PR #19 merged.
- **What we found:** `TrustConfig.dedup_window_hours` used `MappingProxyType`, so `dataclasses.asdict`, `copy.deepcopy` and `pickle` of `TRUST_CONFIG` raised `TypeError: cannot pickle 'mappingproxy' object`, and `hash(TRUST_CONFIG)` failed. Nothing called them yet, so the bug was latent. `services/dedup.py` also had its own copy of `haversine_m` with the same Earth radius as `services/geo.py` (added by S3).
- **What we changed:** `backend/app/config/trust.py`: the windows are now a tuple of `(category, hours)` pairs (immutable, hashable, copyable); values and sources unchanged. `backend/app/services/dedup.py`: `DedupRule.from_config` reads `dict(...)` of that tuple; the module imports `EARTH_RADIUS_M` and `haversine_m` from `services/geo.py` instead of defining its own, and still re-exports both, so existing imports work. New test `backend/tests/test_trust_config.py` (asdict, deepcopy, pickle round trip, hash, read-only windows). `docs/features.csv` T1 row and `docs/P3_FEATURES.md` set to DONE (PR #19 merged); nothing else in `features.csv` changed.
- **Validation:** The new tests failed on the old code (`cannot pickle 'mappingproxy'`) and pass after the fix. `dedup.haversine_m is geo.haversine_m` is `True`. `python tasks.py test` exit 0: 162 backend tests, 1 frontend test, all P1 verifiers. `python tasks.py lint` exit 0. `verify_main_integration.py` and `verify_p1_r_p1.py` pass.
- **Known limitations:** `services/geo.haversine_m` turns NaN coordinates into a large distance instead of an error (S3 review D9, P2's file); dedup inherits that behaviour, as it did with its own copy.
- **Handoff / next step:** None for other areas. T1's Chicago calibration still waits for P1's registered D13 pull.
- **Pull request:** pending.
