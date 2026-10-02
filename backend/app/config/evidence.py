from dataclasses import dataclass


@dataclass(frozen=True)
class EvidenceConfig:
    # Source: docs/JALLEKHA_FINAL_SOLUTION.md D2 (GHMC ward polygons, 2016 numbering).
    # The ward count "150" in this label is not stated in the solution doc.
    geography_version: str = "GHMC_2016_150"
    # Source: docs/JALLEKHA_FINAL_SOLUTION.md F1 (mandal fallback "when under half the
    # wards pass").
    minimum_join_coverage: float = 0.5


EVIDENCE_CONFIG = EvidenceConfig()
