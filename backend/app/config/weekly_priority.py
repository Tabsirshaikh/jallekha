"""Weekly emergency tanker service policy; values are assumptions, not fitted coefficients."""

from dataclasses import dataclass


@dataclass(frozen=True)
class WeeklyPriorityConfig:
    window_days: int = 7  # ASSUMED rolling completed-day window.
    # A section whose verified need is covered keeps its Census baseline (factor 1): confirmed
    # water removes the temporary shortage boost, never part of the structural need. ASSUMED
    # (the plan approved by the owner: "their Census baseline remains unchanged").
    covered_factor: float = 1.0
    shortage_factor: float = 4.0  # ASSUMED: maximum multiplier at complete service shortfall.
    deprivation_weight: float = 0.5  # ASSUMED extra boost for days below the daily minimum.
    maximum_note_chars: int = 2000  # ASSUMED input bound.


WEEKLY_PRIORITY_CONFIG = WeeklyPriorityConfig()
