"""T9 confidence gate (F17): per-signal rules, combination, threshold and calibration.

Every value has a source or is marked ASSUMED / OPEN, owner to confirm. No LLM is used.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ConfidenceConfig:
    # --- inputs (P1's committed files; counts are read from the files, never hard-coded) ---
    evidence_path: str = "data/derived/evidence/ward_evidence.csv"  # E2 (P1)
    sections_path: str = "data/derived/crosswalk/section_to_ward_2016.csv"  # E1 / SEC-FIX (P1)
    section_summary_path: str = "data/derived/crosswalk/section_to_ward_summary.json"  # P1
    replay_groups_path: str = "data/derived/planner_replay/groups.csv"  # A7 replay (P2)
    calibration_path: str = "data/derived/confidence_calibration.csv"
    # Ward neighbours (shared border) for the degraded scenario: E5's adjacency graph (P1).
    adjacency_path: str = "data/derived/underserved/ward_adjacency.json"

    # --- signal 1: Census join quality (E2 columns) ---
    # Rule: a ward that is not allocation_eligible, or whose join_status is not the areal
    # crosswalk, scores 0 (its need is the A3 fallback, not Census). Otherwise
    # min(census_coverage, dominant_source_share): the weaker of how much of the ward Census
    # covers and how much of it comes from one 2009 source ward. Section groups (not placed on
    # a ward) score 0: their need is the A3 fallback. Basis: E2 column meanings
    # (docs/P1 evidence notes); the min rule is ASSUMED, OPEN, owner to confirm.
    census_ok_join_status: tuple[str, ...] = ("AREAL_2009_CROSSWALK",)
    # A ward P1 marked review_required is capped at this score. ASSUMED, OPEN, owner to confirm.
    census_review_cap: float = 0.5

    # --- signal 2: section-location uncertainty (section_to_ward_2016.csv) ---
    # Score per ward_method of a MAPPED section. A ward group takes the weakest of its sections;
    # an unplaced section group scores 0. ASSUMED, OPEN, owner to confirm: INSIDE (point inside
    # the ward polygon) is certain; NEAREST_500M (nearest ward within 500 m) close; WARD_NAME
    # (matched by name) and OSM_NEAR_DIVISION (OSM point near the HMWSSB division) weaker.
    location_method_scores: tuple[tuple[str, float], ...] = (
        ("INSIDE", 1.0),
        ("NEAREST_500M", 0.75),
        ("WARD_NAME", 0.5),
        ("OSM_NEAR_DIVISION", 0.5),
    )
    # Source: P1's section_to_ward_summary.json checks.outlier_km (6.0 km): a placed section
    # farther than this from its HMWSSB division office caps the ward's location score.
    location_outlier_km: float = 6.0
    # Score cap for such a section. ASSUMED, OPEN, owner to confirm.
    location_outlier_cap: float = 0.5

    # --- signal 3: data age ---
    # Census 2011 is the only need source and has the same year for every ward, so data age
    # does not separate wards. The signal is computed and reported but excluded from the
    # combination. OPEN, owner to confirm: any per-group data-age rule.
    data_age_include: bool = False
    # Age (years) at which the score reaches 0, linear from 1 at age 0. ASSUMED, OPEN.
    data_age_zero_at_years: float = 20.0

    # --- signal 4: forecast interval width (T2) ---
    # Decision (b), OPEN, owner to confirm: behind an interface; unavailable until T2 merges.
    # Rule when available: 1 - relative width / interval_width_zero_at, clipped to 0-1, where
    # relative width = (upper - lower) / forecast of the 80% interval. ASSUMED, OPEN.
    interval_width_zero_at: float = 2.0

    # --- signal 5: evidence age ---
    # No dated evidence exists in the repo (E5 field checks carry no dates), so unavailable.

    # --- combination and gate ---
    # Decision, OPEN, owner to confirm: the minimum of the available signals; a missing signal
    # is excluded and listed, never scored 0. No available signal -> confidence 0 (a check).
    combination: str = "min_of_available"
    # Decision, OPEN, owner to confirm: 90% of unflagged group-days must match the
    # full-information plan (docs/P3_BUILD_PLAN.md T9 step 4, "e.g. 90%").
    target_match_share: float = 0.90
    # PROVISIONAL threshold used when the calibration cannot choose one. ASSUMED, OPEN.
    provisional_threshold: float = 0.5
    # The gate's threshold. DERIVED (item 18): the lowest candidate meeting target_match_share
    # in all 5 error draws of the degraded-signal replay (SIMULATION, 2026-10-06; lowest draw
    # 0.9086 against 0.8897 with nothing flagged). It flags the 45 of 152 replay groups with
    # confidence 0 (no usable Census join or no ward placement) and catches about 41% of the
    # damaged groups; catching 90% would need 0.70 and send 117 groups to officers
    # (data/derived/confidence_calibration.csv). Holds only under the ASSUMED error rates
    # below; the rule itself is OPEN, owner to confirm.
    threshold: float = 0.05
    threshold_basis: str = "DERIVED"
    # Candidate thresholds 0.00-1.00 in steps of 0.05. ASSUMED.
    candidate_thresholds: tuple[float, ...] = field(
        default_factory=lambda: tuple(round(i * 0.05, 2) for i in range(21))
    )
    # --- degraded-signal scenario (item 18) ---
    # The replay above cannot tell thresholds apart, so the threshold is chosen on a scenario
    # where the data the system has is wrong in known places, more often where its own quality
    # signals say it is weak. Every rate is ASSUMED, OPEN, owner to confirm; the chosen
    # threshold holds only if real errors follow the same pattern (docs/LIMITATIONS.md F17).
    # Chance that a placed section really lies in a neighbouring ward, by placement method.
    degraded_move_probability: tuple[tuple[str, float], ...] = (
        ("INSIDE", 0.02),
        ("NEAREST_500M", 0.25),
        ("WARD_NAME", 0.5),
        ("OSM_NEAR_DIVISION", 0.5),
    )
    # A placed section farther than location_outlier_km from its division office.
    degraded_outlier_move_probability: float = 0.5
    # True need = recorded need x exp(N(0, sd)), sd = max(floor, need_error_sd x (1 - Census
    # join score)): a ward whose Census join scores 1 is off by about 5%, one scoring 0 (the
    # median fallback) by a factor of about e (+170% / -63%) one time in three.
    degraded_need_error_sd: float = 1.0
    degraded_need_error_sd_floor: float = 0.05
    # A group counts as damaged (for the "caught" share) when a section was moved out of it or
    # its true need is off by at least this share.
    degraded_error_need_share: float = 0.25
    # Error draws; a threshold must meet target_match_share in every one.
    degraded_seeds: int = 5

    # Rounding of written values, and the tolerance Windows / Linux runs must agree within.
    confidence_decimals: int = 4
    threshold_decimals: int = 2
    reproduce_tolerance: float = 1e-4


CONFIDENCE_CONFIG = ConfidenceConfig()
