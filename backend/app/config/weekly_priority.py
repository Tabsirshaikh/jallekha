"""Weekly emergency tanker service policy; values are assumptions, not fitted coefficients."""

from dataclasses import dataclass


@dataclass(frozen=True)
class WeeklyPriorityConfig:
    window_days: int = 7  # ASSUMED rolling completed-day window.
    # A section that got all the water it needed in the last 7 days drops to this share of its
    # Census weight, so sections that got nothing move ahead of it; it keeps a positive share so
    # it is never starved. Owner decision 2026-10-07 ("if an area got a tanker daily its need
    # should get less so other areas can be higher"). ASSUMED value.
    covered_factor: float = 0.25
    shortage_factor: float = 4.0  # ASSUMED: maximum multiplier at complete service shortfall.
    deprivation_weight: float = 0.5  # ASSUMED extra boost for days below the daily minimum.
    maximum_note_chars: int = 2000  # ASSUMED input bound.
    # Without an officer's supply check, a section's own JalLekha bookings of the last 7 days
    # decide: delivered (Confirmed) against not delivered (Failed, Disputed, or expired after
    # waiting 3 days). Bookings still on the way, or delivered without proof (Unconfirmed), are
    # unknown and count for neither side. Fewer known results than this leaves the section
    # unknown (Census baseline). ASSUMED.
    min_known_bookings: int = 3


WEEKLY_PRIORITY_CONFIG = WeeklyPriorityConfig()
