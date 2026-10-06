"""ASSUMED priors for a seeded, non-spatial under-reporting research experiment."""

from dataclasses import dataclass


@dataclass(frozen=True)
class UnderreportingConfig:
    reporting_prior_means: tuple[float, ...] = (0.25, 0.5, 0.75)
    reporting_prior_strength: float = 50.0
    minimum_need_share: float = 0.01
    non_tap_weight: float = 0.5
    intercept_sd: float = 2.0
    access_coefficient_sd: float = 1.0
    map_starts: int = 3
    map_max_evaluations: int = 2000
    minimum_successful_starts: int = 2
    maximum_prediction_relative_spread: float = 0.05
    initial_jitter_sd: float = 0.2
    division_shrinkage_connections: float = 5000.0
    seed: int = 20261006
    max_rhat: float = 1.01
    minimum_bulk_ess: float = 100
    stand_in_stations: int = 90
    basis: str = "ASSUMED"


UNDERREPORTING_CONFIG = UnderreportingConfig()
