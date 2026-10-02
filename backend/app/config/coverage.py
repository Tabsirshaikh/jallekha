"""E6 coverage-map contract; map layers expose evidence without upgrading it."""

from dataclasses import dataclass


@dataclass(frozen=True)
class CoverageConfig:
    schema_version: str = "E6-1"
    geography_version: str = "GHMC_2016_150"
    expected_feature_count: int = 145
    census_reference_year: int = 2011


COVERAGE_CONFIG = CoverageConfig()
