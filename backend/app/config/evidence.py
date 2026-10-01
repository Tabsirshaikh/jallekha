from dataclasses import dataclass


@dataclass(frozen=True)
class EvidenceConfig:
    geography_version: str = "GHMC_2016_150"
    minimum_join_coverage: float = 0.5


EVIDENCE_CONFIG = EvidenceConfig()
