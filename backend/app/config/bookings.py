"""Settings for tanker bookings made through JalLekha (services/bookings.py). Every number says
where it comes from (REAL, DERIVED, ASSUMED, OPEN)."""

from dataclasses import dataclass


@dataclass(frozen=True)
class BookingConfig:
    # Who a booking is for. Hospitals and care homes are the critical facilities of F8 tier 0
    # (config/section_plan.py tier0_categories); schools are not tier 0 there. Basis: F8.
    categories: tuple[str, ...] = (
        "home",
        "apartment",
        "hospital",
        "care_home",
        "school",
        "commercial",
    )
    # A hospital, care-home or school booking is a claim until an officer verifies it once (anyone
    # could tick "hospital"). Until then it is planned like any other booking. Basis: ASSUMED.
    claim_categories: tuple[str, ...] = ("hospital", "care_home", "school")
    tier0_categories: tuple[str, ...] = ("hospital", "care_home")
    # A verified school is served in the second step, with homes that have no water on the
    # premises (children cannot carry water from elsewhere). Basis: ASSUMED, owner may change.
    tier1_categories: tuple[str, ...] = ("school",)
    # HMWSSB booking categories (ALLOCATION_CONFIG.booking_caps): an apartment booking is a
    # 5-24 flat building unless an officer records otherwise. Basis: REAL caps, ASSUMED mapping.
    queue_category: tuple[tuple[str, str], ...] = (
        ("home", "domestic"),
        ("apartment", "apartment_5_24"),
        ("hospital", "domestic"),
        ("care_home", "domestic"),
        ("school", "domestic"),
        ("commercial", "commercial"),
    )
    # One open booking per phone number at a time (HMWSSB allows a domestic customer one tanker in
    # two days; an open booking is one not yet delivered or expired). Basis: DERIVED from the
    # REAL rule, simplified.
    open_bookings_per_phone: int = 1
    # Phone numbers: E.164, as for delivery stops (config/stops.py).
    phone_pattern: str = r"\+[1-9]\d{7,14}"
    facility_name_max: int = 120
    claim_reason_max: int = 500


BOOKING_CONFIG = BookingConfig()
