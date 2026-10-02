import pytest
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError

from app.db import create_all, make_engine, make_session_factory
from app.models import Complaint, DuplicateLink


def _complaint(**overrides: object) -> Complaint:
    values = {
        "category": "no_water",
        "lat": 17.385,
        "lon": 78.4867,
        "channel": "app",
        "basis": "SYNTHETIC",
    }
    values.update(overrides)
    return Complaint(**values)


def test_tables_created_one_per_model() -> None:
    engine = make_engine("sqlite:///:memory:")
    create_all(engine)
    assert {"complaint", "duplicate_link"} <= set(inspect(engine).get_table_names())


def test_link_round_trip_and_one_link_per_child() -> None:
    engine = make_engine("sqlite:///:memory:")
    create_all(engine)
    with make_session_factory(engine)() as session:
        parent, child = _complaint(), _complaint()
        session.add_all([parent, child])
        session.flush()
        session.add(
            DuplicateLink(
                child_id=child.id,
                parent_id=parent.id,
                matched_id=parent.id,
                rule="location_time",
                distance_m=12.5,
                hours_apart=1.0,
            )
        )
        session.commit()
        stored = session.query(DuplicateLink).one()
        assert (stored.child_id, stored.parent_id, stored.basis) == (child.id, parent.id, "DERIVED")

        session.add(
            DuplicateLink(
                child_id=child.id,
                parent_id=parent.id,
                matched_id=parent.id,
                rule="household",
                distance_m=0.0,
                hours_apart=2.0,
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()
