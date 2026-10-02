import uuid
from datetime import UTC, timedelta

from sqlalchemy import String, inspect
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.db import create_all, make_engine, make_session_factory
from app.models import IdTimestampMixin, new_id, utcnow


class ProbeBase(DeclarativeBase):
    """Separate base so this test does not add tables to the app metadata."""


class Probe(IdTimestampMixin, ProbeBase):
    __tablename__ = "probe"
    name: Mapped[str] = mapped_column(String(20))


def test_new_id_is_unique_uuid4() -> None:
    first, second = new_id(), new_id()
    assert first != second
    assert uuid.UUID(first).version == 4


def test_utcnow_is_timezone_aware_utc() -> None:
    assert utcnow().utcoffset() == timedelta(0)
    assert utcnow().tzinfo is UTC


def test_mixin_fills_id_and_created_at() -> None:
    engine = make_engine("sqlite:///:memory:")
    ProbeBase.metadata.create_all(engine)
    with make_session_factory(engine)() as session:
        row = Probe(name="a")
        session.add(row)
        session.commit()
        assert uuid.UUID(row.id).version == 4
        assert row.created_at is not None


def test_create_all_runs_on_empty_metadata() -> None:
    engine = make_engine("sqlite:///:memory:")
    create_all(engine)
    assert inspect(engine).get_table_names() == []
