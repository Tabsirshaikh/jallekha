from dataclasses import dataclass, field

from app.config.env import env_str

# Values marked "ported from v1" come from the v1 prototype's config
# (github.com/abhay-hanchate/jallekha, backend/app/config.py). They are planning
# assumptions, not measurements, and are revisited in A4 (scheduled supply + routing).


@dataclass(frozen=True)
class AllocationConfig:
    # Source: docs/JALLEKHA_FINAL_SOLUTION.md section 3 (Sphere 2018: at least 15 l/person/day)
    # and F9 ("15 lpcd floor, officer may raise"). Basis: ASSUMED policy norm.
    minimum_litres_per_person_day: int = 15
    # Source: docs/JALLEKHA_FINAL_SOLUTION.md section 6 ("officer approval (F16)") and
    # docs/features.csv A7 done-when ("approval needs a reason").
    require_operator_approval: bool = True

    # Litres in one planned stop. HMWSSB domestic tanker = 5,000 l for Rs 500 (Deccan Chronicle,
    # 2026-02-24; HMWSSB tanker booking guidelines). v1 used 6,000. Basis: REAL (published price).
    tanker_load_litres: int = 5000
    # Loads per tanker per shift (first load + reloads). Ported from v1. Basis: ASSUMED.
    max_trips_per_tanker: int = 4
    # Minutes to refill at a filling station. Ported from v1. Basis: ASSUMED.
    fill_minutes: int = 20
    # Minutes to unload at a stop. Ported from v1. Basis: ASSUMED.
    service_minutes: int = 30
    # Planning horizon in minutes (v1: 06:00-18:00). HMWSSB now runs two shifts at busy stations
    # (Siasat, 2026-04-23). Ported from v1. Basis: ASSUMED.
    shift_minutes: int = 720
    # Default OR-Tools time budget per plan, seconds. Ported from v1. Basis: ASSUMED.
    solver_seconds: float = 10.0

    # Solver weights (ported from v1). Route cost is km x arc_cost_per_km; a dropped optional stop
    # costs (priority/100)^2 x penalty_scale x extra_stop_decay^k for the k-th extra stop of the
    # same demand, so using capacity always beats idling and one place cannot take the fleet.
    arc_cost_per_km: int = 100
    penalty_scale: int = 1_000_000
    extra_stop_decay: float = 0.25
    # Mandatory stops carry a penalty larger than any possible route cost (v1 note: OR-Tools'
    # first-solution heuristics cannot seed hard mandatory nodes next to optional reload nodes).
    mandatory_penalty: int = 10_000_000_000

    # Road distance when no OSRM leg is available: straight line x road_factor at avg_speed_kmph.
    # Ported from v1. Basis: ASSUMED; replaced by OSRM legs when OSRM_URL is set.
    road_factor: float = 1.35
    avg_speed_kmph: float = 25.0
    # Environment: OSRM_URL (see .env.example), e.g. http://localhost:5000. Unset = no network.
    osrm_url: str | None = field(default_factory=lambda: env_str("OSRM_URL"))
    # Seconds before an OSRM request falls back to the estimate. Ported from v1. Basis: ASSUMED.
    osrm_timeout_seconds: float = 3.0

    # Booking replay windows (A1, F19). Source: docs/research/P2.md: summer 2025 is the latest
    # complete summer on the pre-Feb-2026 section map (977,933 bookings); 2023 kept for
    # continuity with the solution document. Month totals REAL; daily split SYNTHETIC.
    replay_months_main: tuple[tuple[int, int], ...] = (
        (2025, 3),
        (2025, 4),
        (2025, 5),
        (2025, 6),
        (2025, 7),
    )
    replay_months_secondary: tuple[tuple[int, int], ...] = (
        (2023, 3),
        (2023, 4),
        (2023, 5),
        (2023, 6),
        (2023, 7),
    )


ALLOCATION_CONFIG = AllocationConfig()
