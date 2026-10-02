from datetime import UTC, datetime

import pytest
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError

from app.db import create_all, make_engine, make_session_factory
from app.models import Delivery, DeliveryOutcome, Representative, ResidentResponse

T0 = datetime(2026, 10, 2, 9, 0, tzinfo=UTC)


def _session():  # type: ignore[no-untyped-def]
    engine = make_engine("sqlite:///:memory:")
    create_all(engine)
    return engine, make_session_factory(engine)()


def test_delivery_tables_created_one_per_model() -> None:
    engine, _ = _session()
    tables = {"representative", "delivery", "resident_response", "delivery_outcome"}
    assert tables <= set(inspect(engine).get_table_names())


def test_delivery_round_trip_with_outcome_and_one_reply_per_resident() -> None:
    _, session = _session()
    with session:
        rep = Representative(
            stop_id="stop-1", phone="+910000000001", language="te", basis="SYNTHETIC"
        )
        session.add(rep)
        session.flush()
        delivery = Delivery(
            stop_id="stop-1",
            driver_id="drv-1",
            stop_lat=17.385,
            stop_lon=78.4867,
            otp_representative_id=rep.id,
            otp_digits=6,
            otp_expires_at=T0,
            basis="SYNTHETIC",
        )
        session.add(delivery)
        session.flush()
        session.add(ResidentResponse(delivery_id=delivery.id, resident_id="res-1", answer="yes"))
        session.add(
            DeliveryOutcome(
                delivery_id=delivery.id,
                outcome="Confirmed",
                rule="majority",
                otp_verified=True,
                yes_count=1,
                no_count=0,
                silent_count=2,
                counts_toward_debt=True,
                outcome_basis="DERIVED: F12 table",
            )
        )
        session.commit()
        stored = session.query(Delivery).one()
        assert (stored.otp_wrong_attempts, stored.otp_verified) == (0, False)
        assert session.query(DeliveryOutcome).one().counts_toward_debt

        session.add(ResidentResponse(delivery_id=delivery.id, resident_id="res-1", answer="no"))
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()
        session.add(
            DeliveryOutcome(
                delivery_id=delivery.id,
                outcome="Failed",
                rule="majority",
                otp_verified=False,
                yes_count=0,
                no_count=1,
                silent_count=0,
                counts_toward_debt=False,
                outcome_basis="DERIVED: F12 table",
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()
