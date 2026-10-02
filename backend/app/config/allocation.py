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

    # Service models (A2, F7). A ward is "no_connection" by the Census rule only when most
    # households do not use tap water. Basis: ASSUMED threshold. Ward-level Census 2011 in GHMC
    # never reaches it (max ~29%), so no_connection normally comes from officer input.
    no_connection_non_tap_share: float = 0.5
    # Share of households fetching water outside their premises (WAD) at which a piped ward is
    # flagged for an officer to check for scheduled supply (F9 "wards F1/F4 flag").
    # Basis: ASSUMED; about the 90th percentile of E2 wards (16.5%).
    scheduled_candidate_wad: float = 0.15
    # Need weight = 1 + wad*WAD + cad*CAD + hardship*hardship (F8 entitlement = households x
    # need weight). Water access counts double phone access and hardship: the solution document
    # puts water need first and booking access second. Basis: ASSUMED policy weights; the
    # officer sliders (U7) change them, and every change is a ledger entry.
    need_weight_wad: float = 2.0
    need_weight_cad: float = 1.0
    need_weight_hardship: float = 1.0

    # HMWSSB tanker booking caps per consumer category (A3, F8). Source: HMWSSB tanker booking
    # guidelines (hyderabadwater.gov.in, checked 2026-10-02; docs/research/P2.md): domestic
    # "1 in two days (or) maximum 8 in a month"; multi-storied 5-24 flats "2 in one day (or)
    # maximum 30 in month"; 25-200 flats "3 in one day (or) maximum 60 in month"; commercial
    # "1 in one day (or) maximum 30 in month". Basis: REAL (published rule).
    booking_caps: dict[str, dict[str, int]] = field(
        default_factory=lambda: {
            "domestic": {"min_days_between": 2, "per_month": 8},
            "apartment_5_24": {"per_day": 2, "per_month": 30},
            "apartment_25_200": {"per_day": 3, "per_month": 60},
            "commercial": {"per_day": 1, "per_month": 30},
        }
    )

    # Outage response (A5, F10): "Tier 0 first, then everyone to 10-15 lpcd; priority rises
    # with hours cut off (deprivation cost)". Floor and target are the F10 range; basis ASSUMED.
    outage_floor_lpcd: float = 10.0
    outage_target_lpcd: float = 15.0
    # Deprivation weight = exp(hours / tau): rises faster the longer water is cut off
    # (Holguin-Veras et al. 2013: deprivation cost is non-linear in time). tau is ASSUMED.
    deprivation_tau_hours: float = 24.0
    # A ward becomes an outage candidate for officer confirmation when it has this many
    # distinct "no water" reports (after T1 duplicate linking) within the window. ASSUMED.
    outage_min_distinct_reports: int = 5
    outage_detection_window_hours: float = 6.0

    # Water debt (A6, F11): D' = max(0, D + entitled - confirmed delivered), capped at this many
    # days of the account's daily entitlement, so one long-missed group cannot claim the whole
    # fleet the next day; the cut is logged. Basis: ASSUMED.
    water_debt_cap_days: int = 7
    # Debt outstanding this many days in a row raises an alert (once per debt run). HMWSSB's
    # domestic rule is one tanker in two days (booking_caps above), so a third day in debt means
    # a missed cycle. Basis: DERIVED from the REAL booking rule; the margin is ASSUMED.
    water_debt_alert_days: int = 3

    # Station trip sharing (A8 follow-up, A7): a filling station lends the trips it has left
    # after its own queue to short stations within this straight-line radius (km). HMWSSB ties
    # each token to one station; in July 2026 only 8 of 95 stations had pending bookings
    # (NewsMeter, 2026-07-14). A few neighbour links give most of the gain of full pooling
    # (Jordan & Graves 1995). Chosen on the A8 sandbox sweep (Kneedle knee of bookings served vs
    # km; at 3 km a station has a median of 4 neighbours). Basis: DERIVED (simulation).
    station_sharing_radius_km: float = 3.0

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
