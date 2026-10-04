"""Delivery-proof state in the database (F12): stops and T3 `DeliveryState`s across restarts.

T3's `services/delivery.py` keeps a delivery as an immutable `DeliveryState` and holds no
database. This store maps that state, and the stops deliveries start from, onto tables:

| state                                   | stored in                                          |
|-----------------------------------------|----------------------------------------------------|
| `Stop` (position, basis)                | `delivery_stop`                                    |
| its 2-3 representatives / its residents | `representative` / `resident`                      |
| delivery fields, `started_at`           | `delivery` (`created_at` is the start)             |
| `otp`                                   | `delivery.otp_*`: nonce and hash, never the code   |
| `representatives` copied at the start   | `delivery_roster`, kind `representative`           |
| `sampled_resident_ids`, in sample order | `delivery_roster`, kind `sample`                   |
| `responses`, in the order counted       | `resident_response.answer`, roster `reply_order`   |
| `outcome`                               | `delivery_outcome` (decided once)                  |

A saved state loads back equal to the one saved, through any store on the same database
(tests/services/test_delivery_store.py). A stop's representatives and residents load in id
order. Times are stored and returned in UTC. `resident_response.replied_at` is when the reply
was saved: the state itself carries no reply time.

Writes are last-writer-wins: two requests changing one delivery at the same moment can lose
one change (as with the in-memory holder this replaces; OPEN).
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal, cast

from sqlalchemy import delete, select
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import make_session_factory
from app.models import (
    Delivery,
    DeliveryOutcome,
    DeliveryRoster,
    DeliveryStop,
    Representative,
    Resident,
    ResidentResponse,
    utcnow,
)
from app.services import delivery as dl

REPRESENTATIVE = "representative"
SAMPLE = "sample"
Rule = Literal["majority", "no_majority_fallback"]


@dataclass(frozen=True)
class Stop:
    stop_id: str
    lat: float
    lon: float
    representatives: tuple[dl.Representative, ...]
    residents: tuple[dl.Resident, ...]
    basis: str = "SYNTHETIC"  # REAL | SYNTHETIC; never assumed REAL


class StopConflict(ValueError):
    """The stop id, or one of its representative ids, is already registered."""


def _utc(value: datetime) -> datetime:
    """SQLite returns naive datetimes; every stored time is UTC."""
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _utc_or_none(value: datetime | None) -> datetime | None:
    return None if value is None else _utc(value)


def _duplicates(ids: Iterable[str]) -> list[str]:
    return sorted(i for i, n in Counter(ids).items() if n > 1)


class DeliveryStore:
    def __init__(self, engine: Engine) -> None:
        self._sessions = make_session_factory(engine)

    # --- stops ---------------------------------------------------------------------------------

    def put_stop(self, stop: Stop) -> None:
        """Register a new stop with its people. Raises StopConflict if an id is already taken."""
        stray = [r.id for r in stop.representatives if r.stop_id != stop.stop_id]
        if stray:
            raise ValueError(f"Representatives {stray} do not belong to stop {stop.stop_id}")
        for people, ids in (
            ("representative", [r.id for r in stop.representatives]),
            ("resident", [r.id for r in stop.residents]),
        ):
            if twice := _duplicates(ids):
                raise ValueError(f"Duplicate {people} ids: {twice}")
        try:
            with self._sessions.begin() as session:
                self._check_free(session, stop)
                session.add(
                    DeliveryStop(stop_id=stop.stop_id, lat=stop.lat, lon=stop.lon, basis=stop.basis)
                )
                session.flush()  # the stop row first: residents refer to it
                session.add_all(
                    Representative(
                        id=r.id,
                        stop_id=stop.stop_id,
                        phone=r.phone,
                        language=r.language,
                        active=True,
                        basis=stop.basis,
                    )
                    for r in stop.representatives
                )
                session.add_all(
                    Resident(
                        stop_id=stop.stop_id,
                        resident_id=r.id,
                        phone=r.phone,
                        language=r.language,
                        basis=stop.basis,
                    )
                    for r in stop.residents
                )
        except IntegrityError as exc:  # registered by someone else in the meantime
            raise StopConflict(f"Stop {stop.stop_id} or a representative id is taken") from exc

    @staticmethod
    def _check_free(session: Session, stop: Stop) -> None:
        if session.scalar(select(DeliveryStop.id).where(DeliveryStop.stop_id == stop.stop_id)):
            raise StopConflict(f"Stop {stop.stop_id} already exists")
        ids = [r.id for r in stop.representatives]
        taken = sorted(session.scalars(select(Representative.id).where(Representative.id.in_(ids))))
        if taken:
            raise StopConflict(f"Representative ids already registered: {taken}")

    def get_stop(self, stop_id: str) -> Stop | None:
        with self._sessions() as session:
            row = session.scalar(select(DeliveryStop).where(DeliveryStop.stop_id == stop_id))
            return self._stops(session, [row])[0] if row else None

    def list_stops(self) -> list[Stop]:
        with self._sessions() as session:
            rows = session.scalars(select(DeliveryStop).order_by(DeliveryStop.stop_id)).all()
            return self._stops(session, rows)

    @staticmethod
    def _stops(session: Session, rows: Sequence[DeliveryStop]) -> list[Stop]:
        ids = [row.stop_id for row in rows]
        reps: dict[str, list[dl.Representative]] = defaultdict(list)
        for rep in session.scalars(
            select(Representative)
            .where(Representative.stop_id.in_(ids), Representative.active.is_(True))
            .order_by(Representative.id)
        ):
            reps[rep.stop_id].append(
                dl.Representative(rep.id, rep.stop_id, rep.phone, rep.language)
            )
        residents: dict[str, list[dl.Resident]] = defaultdict(list)
        for res in session.scalars(
            select(Resident).where(Resident.stop_id.in_(ids)).order_by(Resident.resident_id)
        ):
            residents[res.stop_id].append(dl.Resident(res.resident_id, res.phone, res.language))
        return [
            Stop(
                row.stop_id,
                row.lat,
                row.lon,
                tuple(reps[row.stop_id]),
                tuple(residents[row.stop_id]),
                row.basis,
            )
            for row in rows
        ]

    # --- deliveries ------------------------------------------------------------------------------

    def has_delivery(self, delivery_id: str) -> bool:
        with self._sessions() as session:
            return session.get(Delivery, delivery_id) is not None

    def get_delivery(self, delivery_id: str) -> dl.DeliveryState | None:
        with self._sessions() as session:
            row = session.get(Delivery, delivery_id)
            return self._states(session, [row])[0] if row else None

    def list_deliveries(
        self, driver_id: str | None = None, stop_id: str | None = None
    ) -> list[dl.DeliveryState]:
        """Deliveries in start order, optionally of one driver and / or one stop."""
        query = select(Delivery).order_by(Delivery.created_at, Delivery.id)
        if driver_id is not None:
            query = query.where(Delivery.driver_id == driver_id)
        if stop_id is not None:
            query = query.where(Delivery.stop_id == stop_id)
        with self._sessions() as session:
            return self._states(session, session.scalars(query).all())

    def put_delivery(self, state: dl.DeliveryState) -> None:
        """Insert or update one delivery so that it loads back equal to `state`."""
        with self._sessions.begin() as session:
            row = session.get(Delivery, state.delivery_id)
            stop = session.scalar(select(DeliveryStop).where(DeliveryStop.stop_id == state.stop_id))
            if stop is None:
                raise ValueError(f"Stop {state.stop_id} is not registered")
            self._check_representatives(session, state)  # before a new row can be autoflushed
            if row is None:
                row = Delivery(id=state.delivery_id, basis=stop.basis)
                session.add(row)
            row.created_at = _utc(state.started_at)
            row.stop_id, row.driver_id = state.stop_id, state.driver_id
            row.stop_lat, row.stop_lon = state.stop_lat, state.stop_lon
            row.geofence_radius_m = state.geofence_radius_m
            otp = state.otp  # nonce and hash only: the code itself is never stored
            row.otp_representative_id = otp.representative_id if otp else None
            row.otp_nonce = otp.nonce if otp else None
            row.otp_code_hash = otp.code_hash if otp else None
            row.otp_digits = otp.digits if otp else None
            row.otp_issued_at = _utc(otp.issued_at) if otp else None
            row.otp_expires_at = _utc(otp.expires_at) if otp else None
            row.otp_wrong_attempts = state.wrong_attempts
            row.outside_tries = state.outside_tries
            row.otp_verified = state.otp_verified
            row.residents_sampled_at = _utc_or_none(state.sampled_at)
            row.sample_seed = state.sample_seed
            session.flush()  # the delivery row first: the rows below refer to it
            self._write_roster(session, state)
            self._write_responses(session, state)
            self._write_outcome(session, state)

    @staticmethod
    def _check_representatives(session: Session, state: dl.DeliveryState) -> None:
        ids = [rep.id for rep in state.representatives]
        stored = {
            r.id: dl.Representative(r.id, r.stop_id, r.phone, r.language)
            for r in session.scalars(select(Representative).where(Representative.id.in_(ids)))
        }
        wrong = [rep.id for rep in state.representatives if stored.get(rep.id) != rep]
        if wrong:
            raise ValueError(f"Representatives {wrong} are not registered as given")

    @staticmethod
    def _write_roster(session: Session, state: dl.DeliveryState) -> None:
        session.execute(
            delete(DeliveryRoster).where(DeliveryRoster.delivery_id == state.delivery_id)
        )
        reply_order = {rid: i for i, (rid, _) in enumerate(state.responses)}
        if set(reply_order) - set(state.sampled_resident_ids):
            raise ValueError("Every counted reply must come from a sampled resident")
        session.add_all(
            DeliveryRoster(
                delivery_id=state.delivery_id, kind=REPRESENTATIVE, position=i, member_id=rep.id
            )
            for i, rep in enumerate(state.representatives)
        )
        session.add_all(
            DeliveryRoster(
                delivery_id=state.delivery_id,
                kind=SAMPLE,
                position=i,
                member_id=rid,
                reply_order=reply_order.get(rid),
            )
            for i, rid in enumerate(state.sampled_resident_ids)
        )

    @staticmethod
    def _write_responses(session: Session, state: dl.DeliveryState) -> None:
        """One row per sampled resident; `answer` stays empty for silence (counts for nothing)."""
        rows = {
            r.resident_id: r
            for r in session.scalars(
                select(ResidentResponse).where(ResidentResponse.delivery_id == state.delivery_id)
            )
        }
        for resident_id, row in rows.items():
            if resident_id not in state.sampled_resident_ids:
                session.delete(row)
        answers = dict(state.responses)
        now = utcnow()
        for resident_id in state.sampled_resident_ids:
            row = rows.get(resident_id)
            if row is None:
                row = ResidentResponse(delivery_id=state.delivery_id, resident_id=resident_id)
                if state.sampled_at is not None:
                    row.created_at = _utc(state.sampled_at)  # when they were asked
                session.add(row)
            answer = answers.get(resident_id)
            if row.answer != answer:
                row.answer, row.replied_at = answer, now if answer else None

    @staticmethod
    def _write_outcome(session: Session, state: dl.DeliveryState) -> None:
        row = session.scalar(
            select(DeliveryOutcome).where(DeliveryOutcome.delivery_id == state.delivery_id)
        )
        decision = state.outcome
        if decision is None:
            if row is not None:
                session.delete(row)
            return
        if row is None:
            row = DeliveryOutcome(delivery_id=state.delivery_id)  # created_at: decision time
            session.add(row)
        row.outcome, row.rule = decision.outcome, decision.rule
        row.otp_verified = decision.otp_verified
        row.yes_count, row.no_count, row.silent_count = decision.yes, decision.no, decision.silent
        row.counts_toward_debt = dl.counts_toward_debt(decision.outcome)
        row.outcome_basis = decision.basis

    @staticmethod
    def _states(session: Session, rows: Sequence[Delivery]) -> list[dl.DeliveryState]:
        ids = [row.id for row in rows]
        roster: dict[str, list[DeliveryRoster]] = defaultdict(list)
        for member in session.scalars(
            select(DeliveryRoster)
            .where(DeliveryRoster.delivery_id.in_(ids))
            .order_by(DeliveryRoster.position)
        ):
            roster[member.delivery_id].append(member)
        rep_ids = {m.member_id for ms in roster.values() for m in ms if m.kind == REPRESENTATIVE}
        reps = {
            r.id: dl.Representative(r.id, r.stop_id, r.phone, r.language)
            for r in session.scalars(select(Representative).where(Representative.id.in_(rep_ids)))
        }
        answers = {
            (r.delivery_id, r.resident_id): r.answer
            for r in session.scalars(
                select(ResidentResponse).where(ResidentResponse.delivery_id.in_(ids))
            )
        }
        outcomes = {
            o.delivery_id: o
            for o in session.scalars(
                select(DeliveryOutcome).where(DeliveryOutcome.delivery_id.in_(ids))
            )
        }
        return [_state(row, roster[row.id], reps, answers, outcomes.get(row.id)) for row in rows]


def _state(
    row: Delivery,
    roster: list[DeliveryRoster],
    reps: dict[str, dl.Representative],
    answers: dict[tuple[str, str], str | None],
    outcome: DeliveryOutcome | None,
) -> dl.DeliveryState:
    samples = [m for m in roster if m.kind == SAMPLE]
    replied = sorted(
        (m for m in samples if m.reply_order is not None), key=lambda m: cast(int, m.reply_order)
    )
    otp = None
    if row.otp_nonce is not None:
        otp = dl.OtpChallenge(
            representative_id=cast(str, row.otp_representative_id),
            nonce=row.otp_nonce,
            code_hash=cast(str, row.otp_code_hash),
            digits=cast(int, row.otp_digits),
            issued_at=_utc(cast(datetime, row.otp_issued_at)),
            expires_at=_utc(cast(datetime, row.otp_expires_at)),
        )
    decision = None
    if outcome is not None:
        decision = dl.OutcomeDecision(
            outcome=cast(dl.Outcome, outcome.outcome),
            rule=cast(Rule, outcome.rule),
            otp_verified=outcome.otp_verified,
            yes=outcome.yes_count,
            no=outcome.no_count,
            silent=outcome.silent_count,
            basis=outcome.outcome_basis,
        )
    return dl.DeliveryState(
        delivery_id=row.id,
        stop_id=row.stop_id,
        stop_lat=row.stop_lat,
        stop_lon=row.stop_lon,
        driver_id=row.driver_id,
        representatives=tuple(reps[m.member_id] for m in roster if m.kind == REPRESENTATIVE),
        started_at=_utc(row.created_at),
        geofence_radius_m=row.geofence_radius_m,
        otp=otp,
        wrong_attempts=row.otp_wrong_attempts,
        outside_tries=row.outside_tries,
        otp_verified=row.otp_verified,
        sampled_resident_ids=tuple(m.member_id for m in samples),
        sample_seed=row.sample_seed,
        sampled_at=_utc_or_none(row.residents_sampled_at),
        responses=tuple(
            (m.member_id, cast(dl.Answer, answers[(row.id, m.member_id)])) for m in replied
        ),
        outcome=decision,
    )
