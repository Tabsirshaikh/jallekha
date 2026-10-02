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


GROWTH_CONFIG = GrowthConfig()
