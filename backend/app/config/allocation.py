from dataclasses import dataclass


@dataclass(frozen=True)
class AllocationConfig:
    minimum_litres_per_person_day: int = 15
    require_operator_approval: bool = True


ALLOCATION_CONFIG = AllocationConfig()
