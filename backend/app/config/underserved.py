"""E5 engineering defaults; thresholds are review policy, not entitlements."""

from dataclasses import dataclass


@dataclass(frozen=True)
class UnderservedConfig:
    minimum_areas: int = 20
    peer_count: int = 5
    ratio_quantile: float = 0.20
    wad_quantile: float = 0.75
    max_reference_age_years: int = 2
    credible_mass: float = 0.95
    chains: int = 2
    draws: int = 1000
    tune: int = 1000
    seed: int = 20261002
    max_rhat: float = 1.01
    minimum_bulk_ess: float = 100
    max_model_areas: int = 250
    geography_version: str = "GHMC_2016_150"


UNDERSERVED_CONFIG = UnderservedConfig()
