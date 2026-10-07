"""From an approved plan by section to the drivers: each served booking made through JalLekha gets
its tanker, trip and times (route_schedule), and a delivery stop at the booking's location.

At a booked home there are no registered neighbours, so the booker is both the person who gets
the delivery code (the F12 representative) and the one asked "Did you get water? 1 yes / 2 no"
(the resident check). Code read out at the door + inside the 150 m geofence + "1 yes" gives a
Confirmed delivery, which pays the section's water debt when the day is closed (F11). Estimated
bookings (from monthly totals) have no person behind them: their trips stay on the route sheet
without a delivery code.
"""

from __future__ import annotations

from typing import Any

from app.services import delivery as dl
from app.services.bookings import BookingStore
from app.services.delivery_store import DeliveryStore, Stop

BOOKER = "booker"  # the resident id of the booker at a booking's stop


PREFIX = "bk-"


def stop_id_for(booking_id: str) -> str:
    return f"{PREFIX}{booking_id}"


def is_booking_stop(stop_id: str) -> bool:
    """A stop made for one booking: its only representative is the booker."""
    return stop_id.startswith(PREFIX)


def is_real(booking_id: str | None) -> bool:
    """Estimated bookings are named "SECTION|day|k"; bookings made through JalLekha are not."""
    return bool(booking_id) and "|" not in str(booking_id)


def assign_from_routes(
    plan_id: str, routes: dict[str, Any], bookings: BookingStore, deliveries: DeliveryStore
) -> int:
    """Give every served real booking of the plan its tanker; returns how many were assigned
    (a booking that already has a tanker, or no longer waits, is left as it is)."""
    assigned = 0
    for tanker in routes["tankers"]:
        for trip in tanker["trips"]:
            booking_id = trip.get("booking_id")
            if not is_real(booking_id):
                continue
            row = bookings.get(booking_id)
            if row is None or row.status != "WAITING":
                continue
            stop_id = stop_id_for(booking_id)
            if deliveries.get_stop(stop_id) is None:
                deliveries.put_stop(
                    Stop(
                        stop_id,
                        row.lat,
                        row.lon,
                        (dl.Representative(f"{stop_id}-rep", stop_id, row.phone, row.language),),
                        (dl.Resident(BOOKER, row.phone, row.language),),
                        row.basis,
                        row.ward_id,
                        "DERIVED" if row.ward_id else "UNPLACED",
                    )
                )
            trip_info = {
                **trip,
                "tanker_id": tanker["tanker_id"],
                "station_id": tanker["station_id"],
            }
            assigned += bookings.assign(booking_id, plan_id, trip_info, stop_id)
    return assigned
