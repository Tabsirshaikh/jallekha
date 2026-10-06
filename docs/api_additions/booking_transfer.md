# Approximate ward booking transfer (F3)

`GET /equity/wards` retains its shape. `bookings` now carries fractional expected placements
from building-count shares; it is DERIVED_APPROXIMATE, not an observed integer.
`mapping_status` identifies the complete method, and `bookings_per_1000` is null: the authoritative
transfer/population requirement is unmet. API consumers must accept a decimal count.

`GET /equity/summary` adds `ward_unplaced_bookings` and `ward_bookings_basis`.
Exact section concentration and historical source period (2022-Jan to 2024-Feb) are unchanged.
The 2025 audit in `data/derived/underserved/booking_transfer_audit.json` is separate.
Coverage booking layers and ward report cards use the same approximate counts; no entitlement changes.

Rebuild: `scripts/evidence/build_booking_transfer.py`, `build_equity.py`, `build_coverage.py`,
`scripts/frontend/build_u5_snapshot.py`, `scripts/api/refresh_equity_examples.py`.
Verifier `scripts/evidence/verify_booking_transfer.py` recomputes cells, weights and input hashes.
Vector footprints are absent: this implementation uses cached Open Buildings 2023 32m
fractional building-count mass. Voronoi cells and a 1km buffered division hull are ASSUMED.
No point or area fallback for cells without usable building mass. Missing sections stay unplaced.
Legacy E5 model artifacts use their original observations only; U5 flags come from exact sections.
