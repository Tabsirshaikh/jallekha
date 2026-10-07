"""Tanker bookings made through JalLekha: the start of the chain booking -> plan -> tanker ->
delivery code -> water debt.

* **Where:** the booking's location decides its section (the approximate section areas,
  `section_plan.section_of_point`) and its ward; a point outside every section is refused.
* **Who for:** home, apartment, hospital, care home, school or commercial. A hospital, care home
  or school is a *claim* until an officer verifies it; until then it is planned like a home.
* **Priority (F8):** verified hospital or care home -> tier 0; verified school, or a home with no
  water on the premises (self-declared, like F8's tier 1) -> tier 1; everyone else tier 2.
* **One open booking per phone number** (a booking is open until it is delivered, cancelled or
  expired).
* **Ledger:** creation, claim checks and tanker assignment are logged without the phone number
  (only the booking id, section, category and tier).

The store keeps rows in the `booking` table; a plan by section reads the waiting bookings of its
day (`waiting_for`) and an approved plan assigns tankers to them (`assign`).
"""

from __future__ import annotations

import hashlib
import re
import secrets
import threading
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.engine import Engine

from app.config.access import ACCESS_CONFIG
from app.config.bookings import BOOKING_CONFIG as CFG
from app.config.sandbox import SANDBOX_CONFIG
from app.db import make_session_factory
from app.models import Booking
from app.models.base import utcnow
from app.services import section_plan, ward_locate
from app.services.ledger_port import LedgerPort

IST = section_plan.IST
OPEN = ("WAITING", "ASSIGNED")


class BookingRefused(ValueError):
    """The booking cannot be made or changed (the message says why, without personal data)."""


class BookingConflict(BookingRefused):
    """The phone number already has an open booking, or the booking is in another state."""


@dataclass(frozen=True)
class Place:
    section: str  # group id, "section:NAME"
    name: str  # the section's name
    ward_id: str | None
    ward_name: str | None


def consumer_key(phone: str) -> str:
    """A stable key per phone number (last 10 digits), so the queue can apply per-consumer rules
    without keeping the number in the plan."""
    digits = re.sub(r"\D", "", phone)[-10:]
    return hashlib.sha256(f"jallekha-booking:{digits}".encode()).hexdigest()[:24]


def tier_of(category: str, claim_status: str, water_at_home: str) -> int:
    if claim_status == "VERIFIED" and category in CFG.tier0_categories:
        return 0
    if claim_status == "VERIFIED" and category in CFG.tier1_categories:
        return 1
    return 1 if water_at_home == "no" else 2


def queue_category(category: str) -> str:
    return dict(CFG.queue_category)[category]


def local_day(moment: datetime) -> date:
    return moment.astimezone(IST).date()


def day_end(day: date) -> datetime:
    """Midnight at the end of `day`, Hyderabad time."""
    return datetime.combine(day + timedelta(days=1), time(0, 0), tzinfo=IST)


class BookingStore:
    def __init__(
        self,
        engine: Engine,
        ledger: LedgerPort | None = None,
        root: Path | None = None,
        clock: Callable[[], datetime] = utcnow,
    ) -> None:
        from app.config.env import REPO_ROOT

        Booking.__table__.create(engine, checkfirst=True)
        self._sessions = make_session_factory(engine)
        self._ledger = ledger
        self._root = root or REPO_ROOT
        self._clock = clock
        self._lock = threading.RLock()

    # -- where ------------------------------------------------------------------------------

    def locate(self, lat: float, lon: float) -> Place | None:
        group = section_plan.section_of_point(self._root, lat, lon)
        if group is None or group.removeprefix(section_plan.SECTION_PREFIX) not in (
            section_plan.static_sections(self._root)
        ):
            return None
        ward = ward_locate.locate(lat, lon)
        return Place(
            group,
            group.removeprefix(section_plan.SECTION_PREFIX),
            ward,
            ward_locate.ward_name(ward),
        )

    # -- create -----------------------------------------------------------------------------

    def create(
        self,
        *,
        lat: float,
        lon: float,
        category: str,
        water_at_home: str,
        phone: str,
        language: str,
        channel: str = "app",
        facility_name: str | None = None,
        basis: str = "REAL",
        actor: str = "resident",
    ) -> Booking:
        if category not in CFG.categories:
            raise BookingRefused(f"category must be one of {list(CFG.categories)}")
        if water_at_home not in ("yes", "no", "unknown"):
            raise BookingRefused("water_at_home must be yes, no or unknown")
        if not re.fullmatch(CFG.phone_pattern, phone):
            raise BookingRefused("phone must be an E.164 number: + then 8-15 digits")
        if language not in ACCESS_CONFIG.supported_languages:
            raise BookingRefused(
                f"language must be one of {list(ACCESS_CONFIG.supported_languages)}"
            )
        if channel not in ("app", "field_worker"):
            raise BookingRefused("channel must be app or field_worker")
        if basis not in ("REAL", "SYNTHETIC"):
            raise BookingRefused("basis must be REAL or SYNTHETIC")
        if category in CFG.claim_categories and not (facility_name or "").strip():
            raise BookingRefused("A hospital, care home or school booking needs its name")
        place = self.locate(lat, lon)
        if place is None:
            raise BookingRefused(
                "This place is outside every HMWSSB section we know; move the pin inside the city"
            )
        now = self._clock()
        key = consumer_key(phone)
        with self._lock, self._sessions() as session, session.begin():
            open_rows = [
                r
                for r in session.scalars(
                    select(Booking).where(Booking.consumer_key == key, Booking.status.in_(OPEN))
                )
                if not self._finished(r, now)
            ]
            if len(open_rows) >= CFG.open_bookings_per_phone:
                raise BookingConflict(
                    f"This phone number already has an open booking ({open_rows[0].booking_id})"
                )
            row = Booking(
                booking_id=f"BK-{local_day(now).strftime('%Y%m%d')}-{secrets.token_hex(3).upper()}",
                arrived_at=now,
                lat=lat,
                lon=lon,
                section=place.section,
                ward_id=place.ward_id,
                category=category,
                water_at_home=water_at_home,
                facility_name=(facility_name or "").strip()[: CFG.facility_name_max] or None,
                claim_status="CLAIMED" if category in CFG.claim_categories else "NONE",
                phone=phone,
                consumer_key=key,
                language=language,
                channel=channel,
                basis=basis,
                status="WAITING",
            )
            session.add(row)
            session.flush()
            session.expunge(row)
        self._log("booking_created", row, actor, now)
        return row

    # -- read -------------------------------------------------------------------------------

    def get(self, booking_id: str) -> Booking | None:
        with self._sessions() as session:
            row = session.scalar(select(Booking).where(Booking.booking_id == booking_id))
            if row is not None:
                session.expunge(row)
            return row

    def list(
        self,
        day: date | None = None,
        status: str | None = None,
        section: str | None = None,
        claim: str | None = None,
    ) -> list[Booking]:
        with self._sessions() as session:
            query = select(Booking).order_by(Booking.arrived_at, Booking.booking_id)
            if status:
                query = query.where(Booking.status == status)
            if section:
                query = query.where(Booking.section == section)
            if claim:
                query = query.where(Booking.claim_status == claim)
            rows = list(session.scalars(query))
            for r in rows:
                session.expunge(r)
        if day is not None:
            rows = [r for r in rows if local_day(_aware(r.arrived_at)) == day]
        return rows

    def waiting_for(self, day: date) -> list[Booking]:
        """Bookings a plan for `day` takes: still waiting, made before the day ended, and not
        older than the booking expiry (A8: 3 days)."""
        end = day_end(day)
        expiry = SANDBOX_CONFIG.booking_expiry_days
        return [
            r
            for r in self.list(status="WAITING")
            if _aware(r.arrived_at) < end and (day - local_day(_aware(r.arrived_at))).days < expiry
        ]

    def _finished(self, row: Booking, now: datetime) -> bool:
        """A waiting booking older than the expiry is no longer open."""
        days = (local_day(now) - local_day(_aware(row.arrived_at))).days
        return row.status == "WAITING" and days >= SANDBOX_CONFIG.booking_expiry_days

    def expired(self, row: Booking) -> bool:
        return self._finished(row, self._clock())

    # -- change -----------------------------------------------------------------------------

    def check_claim(self, booking_id: str, decision: str, officer_id: str, reason: str) -> Booking:
        if decision not in ("VERIFIED", "REJECTED"):
            raise BookingRefused("decision must be VERIFIED or REJECTED")
        if not officer_id.strip() or not reason.strip():
            raise BookingRefused("An officer id and a reason are required")
        if len(reason) > CFG.claim_reason_max:
            raise BookingRefused("The reason is too long")
        with self._lock, self._sessions() as session, session.begin():
            row = session.scalar(select(Booking).where(Booking.booking_id == booking_id))
            if row is None:
                raise KeyError(booking_id)
            if row.claim_status == "NONE":
                raise BookingConflict("This booking is for a home: there is no claim to check")
            row.claim_status = decision
            row.claim_checked_by = officer_id.strip()
            session.flush()
            session.expunge(row)
        self._log(
            "booking_claim_checked",
            row,
            officer_id,
            self._clock(),
            decision=decision,
            reason_sha256=hashlib.sha256(reason.encode()).hexdigest(),
        )
        return row

    def assign(self, booking_id: str, plan_id: str, trip: dict[str, Any], stop_id: str) -> bool:
        """Give a waiting booking its tanker from an approved plan (once; False if it already
        has one or is no longer waiting)."""
        with self._lock, self._sessions() as session, session.begin():
            row = session.scalar(select(Booking).where(Booking.booking_id == booking_id))
            if row is None or row.status != "WAITING":
                return False
            row.status = "ASSIGNED"
            row.plan_id = plan_id
            row.tanker_id = trip["tanker_id"]
            row.station_id = trip["station_id"]
            row.trip_n = int(trip["n"])
            row.depart = trip["depart"]
            row.arrive = trip["arrive"]
            row.stop_id = stop_id
            session.flush()
            session.expunge(row)
        self._log(
            "booking_assigned",
            row,
            "system",
            self._clock(),
            plan_id=plan_id,
            tanker_id=row.tanker_id,
            trip=row.trip_n,
        )
        return True

    def assigned_to(self, tanker_id: str, plan_id: str) -> list[Booking]:
        with self._sessions() as session:
            rows = list(
                session.scalars(
                    select(Booking)
                    .where(Booking.tanker_id == tanker_id, Booking.plan_id == plan_id)
                    .order_by(Booking.trip_n)
                )
            )
            for r in rows:
                session.expunge(r)
            return rows

    def _log(self, entry: str, row: Booking, actor: str, now: datetime, **extra: Any) -> None:
        if self._ledger is None:
            return
        self._ledger.append(
            entry,
            {
                "entity_type": "booking",
                "entity_id": row.booking_id,
                "section": row.section,
                "category": row.category,
                "claim_status": row.claim_status,
                "tier": tier_of(row.category, row.claim_status, row.water_at_home),
                "channel": row.channel,
                "basis": row.basis,
                "at": now.isoformat(),
                **extra,
            },
            actor,
        )


def _aware(moment: datetime) -> datetime:
    """SQLite returns naive datetimes; they were written as UTC."""
    return moment if moment.tzinfo else moment.replace(tzinfo=UTC)


def as_plan_booking(row: Booking, priority: bool = True) -> dict[str, Any]:
    """A waiting booking as stored in a plan's recipe (no phone number)."""
    return {
        "booking_id": row.booking_id,
        "section": row.section.removeprefix(section_plan.SECTION_PREFIX),
        "arrived_at": _aware(row.arrived_at).isoformat(),
        "tier": tier_of(row.category, row.claim_status, row.water_at_home) if priority else 2,
        "category": queue_category(row.category),
        "consumer_id": row.consumer_key,
        "lat": row.lat,
        "lon": row.lon,
    }
