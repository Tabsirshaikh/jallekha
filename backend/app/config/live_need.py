from dataclasses import dataclass


@dataclass(frozen=True)
class LiveNeedConfig:
    """Live need clues for the ward atlas (U5). Census need is the baseline (it changes only with
    a new survey); these clues, from data the system records every day, say where need may be
    rising now. Research: docs/REMAINING_WORK.md "Live need" (tanker demand and groundwater depth
    track piped-supply failure; supply hours are not published by HMWSSB). A ward is flagged
    when at least `min_bad_clues` clues are bad; each clue is shown, nothing is hidden in a score.
    Every threshold below is ASSUMED (policy, owner may change)."""

    # Bookings: the last `bookings_window_days` against the ward's usual month.
    bookings_window_days: int = 30
    # A ward's usual month = its 2022-24 bookings (data/derived/equity/wards.csv) / the months
    # observed (Jan 2022 - Feb 2024 without the missing Dec 2022 = 25; equity summary).
    history_months: int = 25
    bookings_jump_ratio: float = 1.5
    bookings_jump_min: int = 10  # fewer live bookings than this never count as a jump
    # "No water" complaints (F14 category no_water) in the last `complaint_window_days`.
    complaint_window_days: int = 7
    complaints_min: int = 3
    # Supply cuts: officer-entered supply notices (F15) overlapping the last `cut_window_days`.
    cut_window_days: int = 7
    # Groundwater (shown as background, never counted as a warning sign): median anomaly of
    # the ward's sections (metres deeper than the same month in
    # earlier years, data/derived/groundwater/section_anomaly.csv, latest month).
    groundwater_deeper_m: float = 1.0
    # Water owed: any water debt (F11) counts.
    owed_min_litres: float = 1.0
    min_bad_clues: int = 2
    # Concentration: share of bookings in the top `top_fraction` of sections (equity E4: 10%).
    top_fraction: float = 0.1


LIVE_NEED_CONFIG = LiveNeedConfig()
