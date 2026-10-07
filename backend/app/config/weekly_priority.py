"""Weekly emergency tanker service policy; values are assumptions, not fitted coefficients."""

from dataclasses import dataclass


@dataclass(frozen=True)
class WeeklyPriorityConfig:
    window_days: int = 7  # ASSUMED rolling completed-day window.
    covered_factor: float = 0.25  # ASSUMED: keep a positive turn share to avoid starvation.
    shortage_factor: float = 4.0  # ASSUMED: maximum multiplier at complete service shortfall.
    deprivation_weight: float = 0.5  # ASSUMED extra boost for days below the daily minimum.
    maximum_note_chars: int = 2000  # ASSUMED input bound.


WEEKLY_PRIORITY_CONFIG = WeeklyPriorityConfig()
