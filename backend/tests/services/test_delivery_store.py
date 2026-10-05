"""Delivery-proof state in the database: stops, representatives, residents and deliveries.

Every check reloads through a new `DeliveryStore` on the same database file, the way a restarted
server would. All data here is SYNTHETIC.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable, Iterator
from datetime import UTC, date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.config.trust import TRUST_CONFIG
from app.db import create_all, make_engine
from app.services import delivery as dl
from app.services.delivery_store import DeliveryStore, Stop, StopConflict
from app.services.geo import offset_point
from app.services.ledger_port import InMemoryLedger
from app.services.sms import FakeSmsSender

OTP_KEY = "test-otp-key"
T0 = datetime(2026, 10, 2, 9, 0, tzinfo=UTC)
LAT, LON = 17.385, 78.4867
REPS = (
    dl.Representative("rep-1", "stop-1", "+910000000001", "te"),
    dl.Representative("rep-2", "stop-1", "+910000000002", "ur"),
)
RESIDENTS = tuple(
    dl.Resident(f"res-{i}", f"+91000000010{i}", lang)
    for i, lang in enumerate(["te", "ur", "hi", "en", "te", "te", "hi"], start=1)
)
STOP = Stop("stop-1", LAT, LON, REPS, RESIDENTS, "SYNTHETIC")
WINDOW = timedelta(minutes=TRUST_CONFIG.delivery_reply_window_minutes)

StoreFactory = Callable[[], DeliveryStore]


@pytest.fixture
def new_store(tmp_path: Path) -> Iterator[StoreFactory]:
    """Each call is a fresh store (and engine) on the same file: nothing survives in memory."""
    url = f"sqlite:///{(tmp_path / 'delivery.db').as_posix()}"
    engines = []

    def make() -> DeliveryStore:
        engine = make_engine(url)
        create_all(engine)
        engines.append(engine)
        return DeliveryStore(engine)

    yield make
    for engine in engines:
        engine.dispose()


@pytest.fixture
def chain() -> InMemoryLedger:
    return InMemoryLedger(key="test-ledger-key", clock=lambda: T0)


def _saved(new_store: StoreFactory, state: dl.DeliveryState) -> dl.DeliveryState:
    """Write through one store, read back through another, and check nothing changed."""
    new_store().put_delivery(state)
    loaded = new_store().get_delivery(state.delivery_id)
    assert loaded == state
    return loaded


def _at(metres: float) -> tuple[float, float]:
    return offset_point(LAT, LON, metres, 45.0)


def _started(new_store: StoreFactory, chain: InMemoryLedger) -> dl.DeliveryState:
    new_store().put_stop(STOP)
    stop = new_store().get_stop("stop-1")
    assert stop is not None
    state = dl.start_delivery(
        "del-1", stop.stop_id, stop.lat, stop.lon, "drv-1", stop.representatives, chain, T0
    )
    return _saved(new_store, state)


# --- stops ---------------------------------------------------------------------------------


def test_stop_round_trip_and_listing(new_store: StoreFactory) -> None:
    new_store().put_stop(STOP)
    other = Stop("stop-0", 17.4, 78.5, (), (), "REAL")
    new_store().put_stop(other)
    assert new_store().get_stop("stop-1") == STOP
    assert new_store().get_stop("missing") is None
    assert [s.stop_id for s in new_store().list_stops()] == ["stop-0", "stop-1"]


def test_stop_ids_and_representative_ids_cannot_be_reused(new_store: StoreFactory) -> None:
    new_store().put_stop(STOP)
    with pytest.raises(StopConflict):
        new_store().put_stop(STOP)
    taken = dl.Representative("rep-1", "stop-2", "+910000000009", "te")
    with pytest.raises(StopConflict):
        new_store().put_stop(Stop("stop-2", LAT, LON, (taken,), (), "SYNTHETIC"))
    assert new_store().get_stop("stop-2") is None


def test_a_representative_must_belong_to_its_stop(new_store: StoreFactory) -> None:
    with pytest.raises(ValueError, match="stop-9"):
        new_store().put_stop(Stop("stop-9", LAT, LON, REPS, (), "SYNTHETIC"))


# --- deliveries: exact reconstitution -------------------------------------------------------


def test_full_flow_reloads_equal_at_every_step(
    new_store: StoreFactory, chain: InMemoryLedger
) -> None:
    sms = FakeSmsSender()
    state = _started(new_store, chain)
    assert new_store().has_delivery("del-1") and not new_store().has_delivery("del-2")

    state = _saved(new_store, dl.request_otp(state, "rep-2", OTP_KEY, sms, chain, T0))
    code = sms.sent[-1].params["code"]
    state, result = dl.verify_otp(state, code, *_at(900), OTP_KEY, chain, T0)
    assert result == "outside_geofence"
    state = _saved(new_store, state)
    wrong = "0" * len(code) if code != "0" * len(code) else "1" * len(code)
    state, result = dl.verify_otp(state, wrong, *_at(20), OTP_KEY, chain, T0)
    assert result == "wrong_code"
    state = _saved(new_store, state)
    assert (state.outside_tries, state.wrong_attempts) == (1, 1)
    state, result = dl.verify_otp(state, code, *_at(20), OTP_KEY, chain, T0)
    assert result == "verified"
    state = _saved(new_store, state)

    state = dl.send_resident_check(state, RESIDENTS, "del-1", sms, chain, T0)
    state = _saved(new_store, state)
    later = T0 + timedelta(minutes=5)
    for i, resident_id in enumerate(state.sampled_resident_ids):
        state, counted = dl.record_response(
            state, resident_id, "2" if i == 0 else "1", chain, later
        )
        assert counted
        state = _saved(new_store, state)
    closed = dl.close_delivery(state, chain, later)
    assert closed.outcome is not None and closed.outcome.outcome == "Confirmed"
    reloaded = _saved(new_store, closed)
    assert dl.close_delivery(reloaded, chain, later) == closed  # decided once


def test_several_replies_saved_at_once_keep_their_order(
    new_store: StoreFactory, chain: InMemoryLedger
) -> None:
    state = _started(new_store, chain)
    state = dl.send_resident_check(state, RESIDENTS, "seed-x", FakeSmsSender(), chain, T0)
    for resident_id in reversed(state.sampled_resident_ids):  # replies out of sample order
        state, _ = dl.record_response(state, resident_id, "1", chain, T0)
    _saved(new_store, state)


def test_non_utc_times_are_stored_as_the_same_instant(
    new_store: StoreFactory, chain: InMemoryLedger
) -> None:
    new_store().put_stop(STOP)
    ist = T0.astimezone(timezone(timedelta(hours=5, minutes=30)))
    state = dl.start_delivery("del-1", "stop-1", LAT, LON, "drv-1", REPS, chain, ist)
    new_store().put_delivery(state)
    loaded = new_store().get_delivery("del-1")
    assert loaded == state and loaded is not None and loaded.started_at.tzinfo == UTC


def test_a_delivery_needs_a_registered_stop(new_store: StoreFactory, chain: InMemoryLedger) -> None:
    state = dl.start_delivery("del-1", "stop-1", LAT, LON, "drv-1", REPS, chain, T0)
    with pytest.raises(ValueError, match="stop-1"):
        new_store().put_delivery(state)


def _decided_after_reload(
    new_store: StoreFactory,
    chain: InMemoryLedger,
    verify: bool,
    answers: list[str],
    when: datetime,
) -> tuple[dl.DeliveryState, dl.DeliveryState]:
    """Run to the replies, save, reload in a new store, and close both copies."""
    sms = FakeSmsSender()
    state = dl.request_otp(_started(new_store, chain), "rep-1", OTP_KEY, sms, chain, T0)
    if verify:
        state, result = dl.verify_otp(
            state, sms.sent[-1].params["code"], *_at(10), OTP_KEY, chain, T0
        )
        assert result == "verified"
    state = dl.send_resident_check(state, RESIDENTS, "seed-1", sms, chain, T0)
    for resident_id, text in zip(state.sampled_resident_ids, answers, strict=False):
        state, counted = dl.record_response(state, resident_id, text, chain, T0)
        assert counted
    reloaded = _saved(new_store, state)
    return dl.close_delivery(state, chain, when), dl.close_delivery(reloaded, chain, when)


@pytest.mark.parametrize(
    ("verify", "answers", "outcome"),
    [
        (True, ["1", "1", "2"], "Confirmed"),
        (True, ["2", "2", "1"], "Disputed"),
        (False, ["1", "1", "2"], "Unconfirmed"),
        (False, ["2", "2", "1"], "Failed"),
    ],
)
def test_four_outcomes_decide_the_same_after_a_reload(
    new_store: StoreFactory, chain: InMemoryLedger, verify: bool, answers: list[str], outcome: str
) -> None:
    direct, reloaded = _decided_after_reload(new_store, chain, verify, answers, T0 + WINDOW * 2)
    assert reloaded.outcome is not None and reloaded.outcome.outcome == outcome
    assert reloaded == direct
    assert _saved(new_store, reloaded).outcome == direct.outcome


def test_silence_counts_for_nothing_after_a_reload(
    new_store: StoreFactory, chain: InMemoryLedger
) -> None:
    # One yes and everyone else silent: the single reply decides, the silent are only counted.
    direct, reloaded = _decided_after_reload(new_store, chain, True, ["1"], T0 + WINDOW * 2)
    assert reloaded == direct and reloaded.outcome is not None
    assert (reloaded.outcome.outcome, reloaded.outcome.yes, reloaded.outcome.no) == (
        "Confirmed",
        1,
        0,
    )
    assert reloaded.outcome.silent == len(reloaded.sampled_resident_ids) - 1
    # Nobody replied at all: still pending inside the window, OTP-only fallback after it.
    assert _silent_delivery(new_store, chain, "del-quiet-1", T0).outcome is None
    late = _silent_delivery(new_store, chain, "del-quiet-2", T0 + WINDOW * 2).outcome
    assert late is not None
    assert (late.outcome, late.rule, late.yes, late.no) == (
        "Unconfirmed",
        "no_majority_fallback",
        0,
        0,
    )


def _silent_delivery(
    new_store: StoreFactory, chain: InMemoryLedger, delivery_id: str, when: datetime
) -> dl.DeliveryState:
    """Another verified delivery at the same stop, nobody replies; reloaded, closed at `when`."""
    sms = FakeSmsSender()
    state = dl.start_delivery(delivery_id, "stop-1", LAT, LON, "drv-2", REPS, chain, T0)
    state = dl.request_otp(state, "rep-1", OTP_KEY, sms, chain, T0)
    state, _ = dl.verify_otp(state, sms.sent[-1].params["code"], *_at(10), OTP_KEY, chain, T0)
    state = dl.send_resident_check(state, RESIDENTS, "seed-2", sms, chain, T0)
    return dl.close_delivery(_saved(new_store, state), chain, when)


def test_list_deliveries_filters_by_driver_and_stop(
    new_store: StoreFactory, chain: InMemoryLedger
) -> None:
    _started(new_store, chain)
    store = new_store()
    reps2 = (
        dl.Representative("rep-3", "stop-3", "+910000000003", "te"),
        dl.Representative("rep-4", "stop-3", "+910000000004", "te"),
    )
    store.put_stop(Stop("stop-3", LAT, LON, reps2, (), "SYNTHETIC"))
    later = T0 + timedelta(minutes=1)
    store.put_delivery(dl.start_delivery("del-2", "stop-3", LAT, LON, "drv-2", reps2, chain, later))
    assert [s.delivery_id for s in new_store().list_deliveries()] == ["del-1", "del-2"]
    assert [s.delivery_id for s in new_store().list_deliveries(driver_id="drv-2")] == ["del-2"]
    assert [s.delivery_id for s in new_store().list_deliveries(stop_id="stop-1")] == ["del-1"]
    assert new_store().list_deliveries(driver_id="drv-1", stop_id="stop-3") == []


# --- what the database may hold -------------------------------------------------------------


def _cells(path: Path) -> list[tuple[str, str, str]]:
    """Every non-empty text cell of the database file as (table, column, value)."""
    out = []
    with sqlite3.connect(path) as db:
        tables = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        for table in tables:
            cursor = db.execute(f'SELECT * FROM "{table}"')  # names come from sqlite_master
            columns = [d[0] for d in cursor.description]
            for row in cursor:
                out.extend((table, c, str(v)) for c, v in zip(columns, row, strict=True) if v)
    return out


def test_otp_and_phones_stay_in_their_own_columns(
    new_store: StoreFactory, chain: InMemoryLedger, tmp_path: Path
) -> None:
    sms = FakeSmsSender()
    state = dl.request_otp(_started(new_store, chain), "rep-1", OTP_KEY, sms, chain, T0)
    code = sms.sent[-1].params["code"]
    state, _ = dl.verify_otp(state, code, *_at(10), OTP_KEY, chain, T0)
    state = dl.send_resident_check(state, RESIDENTS, "seed-1", sms, chain, T0)
    new_store().put_delivery(state)
    assert state.otp is not None
    cells = _cells(tmp_path / "delivery.db")
    phones = {p.phone for p in REPS} | {r.phone for r in RESIDENTS}

    def where(fragment: str) -> set[tuple[str, str]]:
        return {(t, c) for t, c, v in cells if fragment in v}

    assert where(code) == set()  # the plain OTP is never stored
    assert where(state.otp.nonce) == {("delivery", "otp_nonce")}
    assert where(state.otp.code_hash) == {("delivery", "otp_code_hash")}
    for phone in phones:
        assert where(phone) <= {("representative", "phone"), ("resident", "phone")}


def test_a_stop_keeps_its_ward_and_where_the_ward_came_from(new_store: StoreFactory) -> None:
    placed = Stop("stop-w", LAT, LON, (), (), "SYNTHETIC", "relation/7848824", "OFFICER")
    new_store().put_stop(placed)
    loaded = new_store().get_stop("stop-w")
    assert loaded == placed
    assert loaded is not None and loaded.ward_id == "relation/7848824"
    assert loaded.ward_basis == "OFFICER"
    assert new_store().get_stop("stop-w") in new_store().list_stops()


def test_a_stop_without_a_ward_is_unplaced(new_store: StoreFactory) -> None:
    new_store().put_stop(STOP)
    loaded = new_store().get_stop("stop-1")
    assert loaded is not None and loaded.ward_id is None and loaded.ward_basis == "UNPLACED"


def test_stops_and_deliveries_can_be_listed_by_ward_and_start_time(
    new_store: StoreFactory, chain: InMemoryLedger
) -> None:
    store = new_store()
    reps = tuple(dl.Representative(f"rep-a{i}", "stop-a", f"+9100000002{i}", "te") for i in (1, 2))
    store.put_stop(Stop("stop-a", LAT, LON, reps, (), "SYNTHETIC", "relation/1", "DERIVED"))
    store.put_stop(Stop("stop-b", LAT, LON, (), (), "SYNTHETIC", "relation/2", "DERIVED"))
    assert [s.stop_id for s in new_store().list_stops(ward_id="relation/1")] == ["stop-a"]
    for i, start in enumerate([T0, T0 + timedelta(days=1)]):
        state = dl.start_delivery(f"del-w{i}", "stop-a", LAT, LON, "drv-1", reps, chain, start)
        new_store().put_delivery(state)
    found = new_store().list_deliveries(stop_ids=["stop-a"], started_from=T0 + timedelta(hours=1))
    assert [d.delivery_id for d in found] == ["del-w1"]
    until = new_store().list_deliveries(stop_ids=["stop-a"], started_before=T0 + timedelta(hours=1))
    assert [d.delivery_id for d in until] == ["del-w0"]
    assert new_store().list_deliveries(stop_ids=[]) == []


def test_deliveries_are_found_by_hyderabad_day_bounds(
    new_store: StoreFactory, chain: InMemoryLedger
) -> None:
    from app.services.day_close import day_bounds

    store = new_store()
    reps = tuple(dl.Representative(f"rep-b{i}", "stop-b", f"+9100000003{i}", "te") for i in (1, 2))
    store.put_stop(Stop("stop-b", LAT, LON, reps, (), "SYNTHETIC", "relation/1", "DERIVED"))
    starts = {
        "late": datetime(2026, 10, 3, 18, 20, tzinfo=UTC),  # 23:50 IST on 10-03
        "early": datetime(2026, 10, 2, 18, 40, tzinfo=UTC),  # 00:10 IST on 10-03
        "next": datetime(2026, 10, 3, 18, 40, tzinfo=UTC),  # 00:10 IST on 10-04
        "before": datetime(2026, 10, 2, 18, 20, tzinfo=UTC),  # 23:50 IST on 10-02
    }
    for name, at in starts.items():
        new_store().put_delivery(dl.start_delivery(name, "stop-b", LAT, LON, "d", reps, chain, at))
    start, end = day_bounds(date(2026, 10, 3))
    found = new_store().list_deliveries(stop_ids=["stop-b"], started_from=start, started_before=end)
    assert sorted(d.delivery_id for d in found) == ["early", "late"]
