"""Settings for plans by section (services/section_plan.py). Every number says where it comes from.

Basis labels: REAL (published), DERIVED (computed from real data), ASSUMED (a policy or modelling
choice that the owner may change), ESTIMATED (a stand-in for a figure HMWSSB does not publish).
"""

from dataclasses import dataclass

from app.config.sandbox import SANDBOX_CONFIG


@dataclass(frozen=True)
class SectionPlanConfig:
    # Carry-over between days: a booking that waits is planned again on the next days until it
    # expires after `booking_expiry_days` (A8, ASSUMED). A plan for a day replays the days before
    # it from this many days back (expiry + 1), which is enough for the waiting list and for the
    # fair queue's turn credits to settle. Basis: DERIVED from the A8 expiry.
    carry_days: int = SANDBOX_CONFIG.booking_expiry_days + 1

    # Share of tanker trips that went to commercial customers between 1 March and 15 July 2022:
    # 190,145 of 589,189 trips (domestic and apartments 399,044), HMWSSB answer to an RTI query as
    # reported by The News Minute (2022-07). Used only to label bookings domestic or commercial,
    # in proportion to each section's commercial connections. Basis: REAL for 2022, applied to 2025
    # as ASSUMED. https://www.thenewsminute.com/telangana/impending-crisis-hyderabad-used-589-lakh-tankers-water-board-summer-108592
    commercial_trip_share: float = 190_145 / (190_145 + 399_044)

    # Priority classes (F8). HMWSSB publishes no booking types, so for a plan by section:
    # - tier 0 (critical facilities): each mapped hospital or care home (OSM, incomplete) is taken
    #   to be one of its section's bookers every day, capped by the section's bookings. Basis:
    #   ASSUMED. Schools and clinics are not tier 0. (Water-agency practice puts hospitals first
    #   when supply fails.)
    tier0_categories: tuple[str, ...] = ("hospitals", "care_homes")
    tier0_bookings_per_facility: float = 1.0
    # - tier 1 (no water on premises): the section's Census-2011 share of homes fetching water
    #   from outside the premises (WAD, carried onto the section by building share) is the share
    #   of its other bookings put in tier 1. Basis: ESTIMATED (the A8 simulation draws tiers from
    #   Census shares the same way).
    # Facilities served first in an outage (F10); an officer can add others. Basis: ASSUMED.
    outage_critical_categories: tuple[str, ...] = ("hospitals", "care_homes", "uphcs", "clinics")
    critical_stop_litres: float = 5000.0  # one tanker load a day per critical facility. ASSUMED.

    # People in a section: domestic connections x household size. One connection can serve many
    # flats, so this understates apartment areas. Household size: median of the 2016 wards
    # (Census 2011, data/derived/population/ward_population_2025.csv). Basis: ESTIMATED.
    household_size_fallback: float = 4.3

    # Scheduled supply (F9) in a plan by section: the sections the under-served field-check screen
    # (F4) flags are the candidates ("they did not book but should have"); an officer may confirm
    # none of them. Stops are the section's estimated centre until an officer registers real ones.
    # Basis: ASSUMED.
    scheduled_modes: tuple[str, ...] = ("f4", "none")

    # An outage notice (F15) names wards. A section is treated as cut when at least this share of
    # its buildings is in those wards; its people affected are scaled by that share. ASSUMED.
    outage_min_building_share: float = 0.5

    # Tanker routes (services/route_schedule.py). One booking is one tanker load: a trip is
    # station -> section -> station, so a tanker's day is a list of round trips. Basis below.
    # - Tankers on the road per station follow the station's trips of the day (capacity / trips a
    #   tanker makes: 9, DERIVED from 11,000 trips a day by 1,233 tankers, SANDBOX_CONFIG).
    # - Working day: two shifts, 06:00 to 22:00 (HMWSSB runs two shifts at busy stations, Siasat
    #   2026-04-23). Basis: ASSUMED.
    # - Time of a trip: fill + drive there + unload + drive back; fill 20 and unload 30 minutes
    #   (ALLOCATION_CONFIG, ASSUMED); driving from OSRM free-flow car legs where cached (DERIVED,
    #   optimistic: no traffic, no truck limits), else the straight line x 1.35 at 25 km/h
    #   (ESTIMATE).
    route_day_start_minute: int = 6 * 60
    route_day_end_minute: int = 22 * 60


SECTION_PLAN_CONFIG = SectionPlanConfig()
