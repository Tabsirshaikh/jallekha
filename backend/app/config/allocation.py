from dataclasses import dataclass


@dataclass(frozen=True)
class AllocationConfig:
    # Source: docs/JALLEKHA_FINAL_SOLUTION.md section 3 (Sphere 2018: at least 15 l/person/day)
    # and F9 ("15 lpcd floor, officer may raise"). Basis: ASSUMED policy norm.
    minimum_litres_per_person_day: int = 15
    # Source: docs/JALLEKHA_FINAL_SOLUTION.md section 6 ("officer approval (F16)") and
    # docs/features.csv A7 done-when ("approval needs a reason").
    require_operator_approval: bool = True


ALLOCATION_CONFIG = AllocationConfig()
