from dataclasses import dataclass


@dataclass(frozen=True)
class GrowthConfig:
    # Google Open Buildings Temporal V1: annual inference years 2016–2023.
    # https://developers.google.com/earth-engine/datasets/catalog/GOOGLE_Research_open-buildings-temporal_v1
    years: tuple[int, ...] = tuple(range(2016, 2024))
    # Engineering choice for bounded public COG extraction, not native/effective resolution.
    # Google publishes 0.5 m rasters with ~4 m effective resolution. Test 16/32/64 m sensitivity.
    grid_metres: int = 32
    # Conservative engineering review gate: incomplete raster coverage is not extrapolated.
    minimum_coverage: float = 0.99
    # Engineering network bound; retries reuse archived successful tile extractions.
    network_workers: int = 4
    network_timeout_seconds: int = 30
    # A ward's building trend is "stable" when, after removing the city-wide year shocks, its
    # slope is at least this many standard errors above zero (usual 2-sigma convention).
    # Basis: ASSUMED statistical threshold; replaces the CV-of-annual-change heuristic, which
    # flagged every ward because the city-wide shocks dominate small annual changes.
    minimum_trend_t: float = 2.0


GROWTH_CONFIG = GrowthConfig()
