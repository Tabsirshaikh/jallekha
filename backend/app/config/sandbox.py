from dataclasses import dataclass


@dataclass(frozen=True)
class SandboxConfig:
    """Policy sandbox (A8, F19). Every output is labelled SIMULATION."""

    # Source: F19 "30+ seeds"; every policy runs on the same seeds (common random numbers,
    # docs/research/P2.md). Basis: spec.
    seeds: int = 30
    # A booking still unserved this many days after it arrived counts as unmet (the household
    # gives up and buys from a private tanker, about Rs 2,000 per 5,000 l). Before the 2026 fleet
    # increase HMWSSB took "about 3 days" (Deccan Chronicle, 2026-02-24). Basis: ASSUMED.
    booking_expiry_days: int = 3
    # "90 tanker filling stations and 150 filling points" (Telangana Today, 2025-12-21).
    # Basis: REAL count; positions are ASSUMED stand-ins (no public list with coordinates).
    station_count: int = 90
    # Fleet scenario: 1,150 tankers (Telangana Today, 2025-12-21) x 9 trips per tanker per day
    # (1,233 tankers making more than 11,000 trips a day, docs/research/P2.md [S]: 8.9).
    # Basis: REAL (news) for the fleet, DERIVED for trips.
    fleet_tankers: int = 1150
    trips_per_tanker_day: float = 9.0
    # Tight scenario: capacity cut until B1 delivers this share of bookings, the REAL HMWSSB
    # delivered share in Jun-Aug 2026 (92.1% / 89.2% / 92.4%, Telangana portal). Basis: REAL.
    tight_delivered_share: float = 0.90
    # JL only: share of each station's daily trips set aside for scheduled supply (F9) to
    # wards where people fetch water off premises. Basis: ASSUMED; JL_F8 (queue only, no
    # reserve) is reported next to JL so the cost of the reserve to booked service is visible.
    jl_scheduled_reserve_share: float = 0.05
    # Groups (wards) with fewer bookings than this over the replay are left out of Gini, Jain
    # and worst fill rate, which would otherwise be driven by a handful of bookings.
    # Basis: ASSUMED.
    fairness_min_group_bookings: int = 100
    # One-way km from a section's point to the household it serves: mean distance from the
    # centre of a disc to a uniform point (2/3 R) for the mean GHMC ward area (549.3 km^2 over
    # 145 wards, datameet ward polygons = 3.79 km^2, R = 1.10 km). Sections are about ward-sized.
    # Basis: DERIVED from REAL ward areas; the uniform disc is ASSUMED. Same for every policy.
    section_access_km: float = 0.732
    # B4 (minimum cost) may serve a booking from any of its this-many nearest stations.
    # Basis: ASSUMED; keeps the greedy assignment fast.
    b4_candidate_stations: int = 5


SANDBOX_CONFIG = SandboxConfig()
