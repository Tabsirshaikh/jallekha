"""ASSUMED review policy for exact section rates; never changes entitlements."""

from dataclasses import dataclass


@dataclass(frozen=True)
class SectionCheckConfig:
    train_year: int = 2024
    period_year: int = 2025
    months_per_year: int = 12
    peer_count: int = 5
    minimum_peers: int = 3
    ratio_quantile: float = 0.20
    need_quantile: float = 0.50
    flats_distance_weight: float = 2.0
    basis: str = "ASSUMED"


SECTION_CHECK_CONFIG = SectionCheckConfig()
