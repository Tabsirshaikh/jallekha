"""T3 delivery proof (F12): OTP + geofence + resident check -> four outcomes."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from app.config.trust import TRUST_CONFIG
from app.services import delivery as dl
from app.services import ledger, otp
from app.services.geo import offset_point
from app.services.ledger_port import InMemoryLedger
from app.services.sms import FakeSmsSender

OTP_KEY = "test-otp-key"
LEDGER_KEY = "test-ledger-key"
STOP = (17.385, 78.4867)
T0 = datetime(2026, 10, 2, 9, 0, tzinfo=UTC)
REPS = (
    dl.Representative(id="rep-1", stop_id="stop-1", phone="+910000000001", language="te"),
    dl.Representative(id="rep-2", stop_id="stop-1", phone="+910000000002", language="ur"),
)
RESIDENTS = tuple(
    dl.Resident(id=f"res-{i}", phone=f"+91000000010{i}", language=lang)
    for i, lang in enumerate(["te", "ur", "hi", "en", "te", "te", "hi"], start=1)
)
WINDOW = timedelta(minutes=TRUST_CONFIG.delivery_reply_window_minutes)
VALID = timedelta(minutes=TRUST_CONFIG.otp_valid_minutes)


@pytest.fixture
def chain() -> InMemoryLedger:
    return InMemoryLedger(key=LEDGER_KEY, clock=lambda: T0)


@pytest.fixture
def sms() -> FakeSmsSender:
    return FakeSmsSender()


def _start(chain: InMemoryLedger) -> dl.DeliveryState:
    return dl.start_delivery("del-1", "stop-1", *STOP, "drv-1", REPS, chain, T0)


def _at(metres: float, bearing: float = 45.0) -> tuple[float, float]:
    return offset_point(*STOP, metres, bearing)


def _verified(chain: InMemoryLedger, sms: FakeSmsSender) -> dl.DeliveryState:
    state = dl.request_otp(_start(chain), "rep-1", OTP_KEY, sms, chain, T0)
    state, result = dl.verify_otp(state, sms.sent[-1].params["code"], *_at(20), OTP_KEY, chain, T0)
    assert result == "verified"
    return state


def _with_replies(
    state: dl.DeliveryState, chain: InMemoryLedger, sms: FakeSmsSender, answers: list[str]
) -> dl.DeliveryState:
    state = dl.send_resident_check(state, RESIDENTS, "seed-1", sms, chain, T0)
    for resident_id, text in zip(state.sampled_resident_ids, answers, strict=False):
        state, accepted = dl.record_response(state, resident_id, text, chain, T0)
        assert accepted
    return state


# --- outcome table (F12) ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("otp_verified", "yes", "no", "outcome"),
    [
        (True, 3, 1, "Confirmed"),
        (True, 1, 3, "Disputed"),
        (False, 3, 1, "Unconfirmed"),
        (False, 1, 3, "Failed"),
    ],
)
def test_outcome_table(otp_verified: bool, yes: int, no: int, outcome: str) -> None:
    decision = dl.compute_outcome(otp_verified, yes, no, window_closed=False, all_replied=True)
    assert decision is not None
    assert decision.outcome == outcome
    assert decision.rule == "majority"
    assert decision.basis.startswith("DERIVED: F12")


def test_four_outcomes_end_to_end(sms: FakeSmsSender) -> None:
    def run(verify: bool, answers: list[str]) -> str:
        chain = InMemoryLedger(key=LEDGER_KEY, clock=lambda: T0)
        state = _verified(chain, sms) if verify else _start(chain)
        state = _with_replies(state, chain, sms, answers)
        state = dl.close_delivery(state, chain, T0 + WINDOW + timedelta(seconds=1))
        assert state.outcome is not None
        return state.outcome.outcome

    assert run(True, ["1", "1", "2"]) == "Confirmed"
    assert run(True, ["2", "2", "1"]) == "Disputed"
    assert run(False, ["1", "1", "2"]) == "Unconfirmed"
    assert run(False, ["2", "2", "1"]) == "Failed"


def test_only_confirmed_counts_toward_water_debt() -> None:
    assert dl.counts_toward_debt("Confirmed")
    for outcome in ("Disputed", "Unconfirmed", "Failed"):
        assert not dl.counts_toward_debt(outcome)


# --- ties, zero replies, silence (decision b, OPEN) -------------------------------------


@pytest.mark.parametrize(("otp_verified", "fallback"), [(True, "Unconfirmed"), (False, "Failed")])
def test_tie_waits_then_falls_back_to_otp(otp_verified: bool, fallback: str) -> None:
    assert dl.compute_outcome(otp_verified, 2, 2, window_closed=False, all_replied=False) is None
    decision = dl.compute_outcome(otp_verified, 2, 2, window_closed=True, all_replied=False)
    assert decision is not None
    assert (decision.outcome, decision.rule) == (fallback, "no_majority_fallback")


@pytest.mark.parametrize(("otp_verified", "fallback"), [(True, "Unconfirmed"), (False, "Failed")])
def test_zero_replies_waits_then_falls_back_to_otp(otp_verified: bool, fallback: str) -> None:
    assert dl.compute_outcome(otp_verified, 0, 0, window_closed=False, all_replied=False) is None
    decision = dl.compute_outcome(otp_verified, 0, 0, window_closed=True, all_replied=False)
    assert decision is not None
    assert (decision.outcome, decision.rule) == (fallback, "no_majority_fallback")


def test_silence_counts_for_nothing(chain: InMemoryLedger, sms: FakeSmsSender) -> None:
    # One yes and four silent residents: the yes decides; silence is not counted as no.
    state = _with_replies(_verified(chain, sms), chain, sms, ["1"])
    assert len(state.sampled_resident_ids) >= TRUST_CONFIG.delivery_residents_min
    still_open = dl.close_delivery(state, chain, T0 + WINDOW - timedelta(seconds=1))
    assert still_open.outcome is None
    closed = dl.close_delivery(state, chain, T0 + WINDOW + timedelta(seconds=1))
    assert closed.outcome is not None
    assert (closed.outcome.outcome, closed.outcome.yes, closed.outcome.no) == ("Confirmed", 1, 0)
    assert closed.outcome.silent == len(state.sampled_resident_ids) - 1


def test_invalid_late_and_unsampled_replies_are_ignored(
    chain: InMemoryLedger, sms: FakeSmsSender
) -> None:
    state = dl.send_resident_check(_start(chain), RESIDENTS, "seed-1", sms, chain, T0)
    first = state.sampled_resident_ids[0]
    outsider = next(r.id for r in RESIDENTS if r.id not in state.sampled_resident_ids)
    assert dl.record_response(state, first, "maybe", chain, T0)[1] is False
    assert dl.record_response(state, outsider, "1", chain, T0)[1] is False
    assert dl.record_response(state, first, "1", chain, T0 + WINDOW + timedelta(seconds=1))[1] is (
        False
    )
    state, accepted = dl.record_response(state, first, "2", chain, T0)
    assert accepted
    assert dl.record_response(state, first, "1", chain, T0)[1] is False  # first reply stands
    assert state.responses == ((first, "no"),)


@pytest.mark.parametrize(
    ("text", "answer"),
    [("1", "yes"), (" 2 ", "no"), ("౧", "yes"), ("२", "no"), ("١", "yes"), ("3", None), ("", None)],
)
def test_reply_parsing_accepts_digits_in_any_script(text: str, answer: str | None) -> None:
    assert dl.parse_reply(text) == answer


def test_no_residents_to_ask_still_waits_for_the_window(
    chain: InMemoryLedger, sms: FakeSmsSender
) -> None:
    state = dl.send_resident_check(_verified(chain, sms), (), "seed-1", sms, chain, T0)
    assert state.sampled_resident_ids == ()
    assert dl.close_delivery(state, chain, T0).outcome is None
    closed = dl.close_delivery(state, chain, T0 + WINDOW + timedelta(seconds=1))
    assert closed.outcome is not None
    assert (closed.outcome.outcome, closed.outcome.rule) == ("Unconfirmed", "no_majority_fallback")


def test_outcome_waits_for_all_replies_or_window(chain: InMemoryLedger, sms: FakeSmsSender) -> None:
    state = _with_replies(_verified(chain, sms), chain, sms, ["1", "1"])
    assert dl.close_delivery(state, chain, T0).outcome is None
    n = len(state.sampled_resident_ids)
    full = _with_replies(_verified(chain, sms), chain, sms, ["1"] * n)
    assert dl.close_delivery(full, chain, T0).outcome is not None


# --- resident sample ---------------------------------------------------------------------


def test_sample_is_seeded_sized_and_excludes_representatives() -> None:
    ids = [r.id for r in RESIDENTS] + ["rep-1"]
    first = dl.sample_residents(ids, "seed-1", exclude={"rep-1"})
    assert first == dl.sample_residents(list(reversed(ids)), "seed-1", exclude={"rep-1"})
    assert TRUST_CONFIG.delivery_residents_min <= len(first) <= TRUST_CONFIG.delivery_residents_max
    assert "rep-1" not in first and len(set(first)) == len(first)
    sizes = {len(dl.sample_residents(ids, f"seed-{i}")) for i in range(50)}
    assert sizes == set(
        range(TRUST_CONFIG.delivery_residents_min, TRUST_CONFIG.delivery_residents_max + 1)
    )


def test_sample_takes_everyone_when_fewer_than_minimum() -> None:
    assert sorted(dl.sample_residents(["a", "b"], "seed-1")) == ["a", "b"]


def test_resident_check_sms_uses_template_key_and_language(
    chain: InMemoryLedger, sms: FakeSmsSender
) -> None:
    state = dl.send_resident_check(_start(chain), RESIDENTS, "seed-1", sms, chain, T0)
    by_id = {r.id: r for r in RESIDENTS}
    assert len(sms.sent) == len(state.sampled_resident_ids)
    for message, resident_id in zip(sms.sent, state.sampled_resident_ids, strict=True):
        assert message.template_key == "delivery.resident_check"
        assert message.to == by_id[resident_id].phone
        assert message.language == by_id[resident_id].language


# --- geofence (150 m, server side) -------------------------------------------------------


def test_geofence_149_inside_151_outside(chain: InMemoryLedger) -> None:
    state = _start(chain)
    for bearing in (0, 90, 180, 270, 45):
        _, inside = dl.check_geofence(state, *_at(149, bearing), chain, T0)
        _, outside = dl.check_geofence(state, *_at(151, bearing), chain, T0)
        assert inside.inside and not outside.inside
    assert inside.radius_m == TRUST_CONFIG.geofence_radius_metres == 150


def test_geofence_exactly_150_is_inside(chain: InMemoryLedger) -> None:
    state = _start(chain)
    for bearing in range(360):
        assert dl.check_geofence(state, *_at(150, bearing), chain, T0)[1].inside


def test_otp_outside_geofence_is_not_verified_and_not_counted(
    chain: InMemoryLedger, sms: FakeSmsSender
) -> None:
    state = dl.request_otp(_start(chain), "rep-1", OTP_KEY, sms, chain, T0)
    code = sms.sent[-1].params["code"]
    state, result = dl.verify_otp(state, code, *_at(151), OTP_KEY, chain, T0)
    assert result == "outside_geofence"
    assert not state.otp_verified and state.wrong_attempts == 0
    state, result = dl.verify_otp(state, code, *_at(149), OTP_KEY, chain, T0)
    assert result == "verified" and state.otp_verified


def test_wrong_and_correct_code_outside_get_the_same_reply(
    chain: InMemoryLedger, sms: FakeSmsSender
) -> None:
    state = dl.request_otp(_start(chain), "rep-1", OTP_KEY, sms, chain, T0)
    code = sms.sent[-1].params["code"]
    digits = TRUST_CONFIG.otp_digits
    wrong = f"{(int(code) + 1) % 10**digits:0{digits}d}"
    after_wrong, wrong_reply = dl.verify_otp(state, wrong, *_at(151), OTP_KEY, chain, T0)
    after_right, right_reply = dl.verify_otp(state, code, *_at(151), OTP_KEY, chain, T0)
    assert wrong_reply == right_reply == "outside_geofence"
    for after in (after_wrong, after_right):
        assert after.wrong_attempts == 0 and not after.otp_verified
    # The logged attempt reveals nothing about the code either.
    outside_entries = [e.payload for e in chain.entries if e.event_type == "otp_attempted"]
    assert [p["result"] for p in outside_entries] == ["outside_geofence"] * 2
    assert outside_entries[0]["wrong_attempts"] == outside_entries[1]["wrong_attempts"] == 0


def test_geofence_is_checked_before_the_code(
    chain: InMemoryLedger, sms: FakeSmsSender, monkeypatch: pytest.MonkeyPatch
) -> None:
    state = dl.request_otp(_start(chain), "rep-1", OTP_KEY, sms, chain, T0)
    code = sms.sent[-1].params["code"]

    def code_must_not_be_checked(*args: object) -> bool:
        raise AssertionError("OTP code checked before the geofence")

    monkeypatch.setattr(dl.otp, "check", code_must_not_be_checked)
    for lat_lon in (_at(151), (None, None)):
        _, reply = dl.verify_otp(state, code, *lat_lon, OTP_KEY, chain, T0)
        assert reply == "outside_geofence"


def test_outside_tries_are_capped_with_one_final_ledger_entry(
    chain: InMemoryLedger, sms: FakeSmsSender
) -> None:
    cap = TRUST_CONFIG.outside_tries_max
    state = dl.request_otp(_start(chain), "rep-1", OTP_KEY, sms, chain, T0)
    code = sms.sent[-1].params["code"]
    for attempt in range(1, cap + 1):
        before = len(chain.entries)
        state, reply = dl.verify_otp(state, code, *_at(151), OTP_KEY, chain, T0)
        assert reply == "outside_geofence" and state.outside_tries == attempt
        assert [e.event_type for e in chain.entries[before:]] == [
            "geofence_checked",
            "otp_attempted",
        ]
    before = len(chain.entries)
    for _ in range(5):  # tries cap+1 .. cap+5
        state, reply = dl.verify_otp(state, code, *_at(151), OTP_KEY, chain, T0)
        assert reply == "outside_geofence"
    added = chain.entries[before:]
    assert [e.event_type for e in added] == ["outside_tries_exceeded"]
    assert added[0].payload["outside_tries"] == cap + 1
    assert added[0].payload["outside_tries_max"] == cap
    assert state.outside_tries == cap + 5
    assert state.wrong_attempts == 0 and not state.otp_verified
    assert ledger.verify_entries(list(chain.entries), LEDGER_KEY)["valid"]
    # The cap only limits logging: the code still works once the driver is at the stop.
    state, reply = dl.verify_otp(state, code, *_at(20), OTP_KEY, chain, T0)
    assert reply == "verified" and state.otp_verified


# --- OTP (decision a, OPEN) --------------------------------------------------------------


def test_otp_sms_goes_to_a_registered_representative(
    chain: InMemoryLedger, sms: FakeSmsSender
) -> None:
    state = dl.request_otp(_start(chain), "rep-2", OTP_KEY, sms, chain, T0)
    message = sms.sent[-1]
    assert (message.to, message.language, message.template_key) == (
        "+910000000002",
        "ur",
        "delivery.otp",
    )
    assert len(message.params["code"]) == TRUST_CONFIG.otp_digits
    assert state.otp is not None and state.otp.digits == TRUST_CONFIG.otp_digits
    assert state.otp.expires_at == T0 + VALID
    with pytest.raises(ValueError, match="not registered"):
        dl.request_otp(state, "rep-9", OTP_KEY, sms, chain, T0)


def test_representative_count_must_be_two_to_three(chain: InMemoryLedger) -> None:
    extra = dl.Representative(id="rep-x", stop_id="stop-1", phone="+91", language="en")
    with pytest.raises(ValueError, match="representatives"):
        dl.start_delivery("d", "stop-1", *STOP, "drv", REPS[:1], chain, T0)
    with pytest.raises(ValueError, match="representatives"):
        dl.start_delivery("d", "stop-1", *STOP, "drv", (*REPS, extra, extra), chain, T0)
    other_stop = dl.Representative(id="rep-o", stop_id="stop-2", phone="+91", language="en")
    with pytest.raises(ValueError, match="stop"):
        dl.start_delivery("d", "stop-1", *STOP, "drv", (REPS[0], other_stop), chain, T0)


def test_expired_otp_is_rejected_and_not_counted(chain: InMemoryLedger, sms: FakeSmsSender) -> None:
    state = dl.request_otp(_start(chain), "rep-1", OTP_KEY, sms, chain, T0)
    code = sms.sent[-1].params["code"]
    at_expiry, result = dl.verify_otp(state, code, *_at(20), OTP_KEY, chain, T0 + VALID)
    assert result == "verified"
    late, result = dl.verify_otp(
        state, code, *_at(20), OTP_KEY, chain, T0 + VALID + timedelta(seconds=1)
    )
    assert result == "expired"
    assert not late.otp_verified and late.wrong_attempts == 0


def test_wrong_otp_attempts_lock_the_stop_across_reissues(
    chain: InMemoryLedger, sms: FakeSmsSender
) -> None:
    limit = TRUST_CONFIG.otp_max_attempts
    state = dl.request_otp(_start(chain), "rep-1", OTP_KEY, sms, chain, T0)
    wrong = "0" * TRUST_CONFIG.otp_digits
    if wrong == sms.sent[-1].params["code"]:
        wrong = "1" * TRUST_CONFIG.otp_digits
    for attempt in range(1, limit):
        state, result = dl.verify_otp(state, wrong, *_at(20), OTP_KEY, chain, T0)
        assert (result, state.wrong_attempts) == ("wrong_code", attempt)
    # A new OTP does not reset the per-stop count.
    state = dl.request_otp(state, "rep-2", OTP_KEY, sms, chain, T0)
    code = sms.sent[-1].params["code"]
    bad = wrong if wrong != code else "1" * TRUST_CONFIG.otp_digits
    state, result = dl.verify_otp(state, bad, *_at(20), OTP_KEY, chain, T0)
    assert (result, state.wrong_attempts, state.otp_locked) == ("wrong_code", limit, True)
    state, result = dl.verify_otp(state, code, *_at(20), OTP_KEY, chain, T0)
    assert result == "locked" and not state.otp_verified
    with pytest.raises(ValueError, match="locked"):
        dl.request_otp(state, "rep-1", OTP_KEY, sms, chain, T0)


def test_changing_otp_digits_after_issue_keeps_the_issued_otp_working(
    chain: InMemoryLedger, sms: FakeSmsSender, monkeypatch: pytest.MonkeyPatch
) -> None:
    # S3 review D11: the digit count is stored with the OTP and passed when re-deriving.
    state = dl.request_otp(_start(chain), "rep-1", OTP_KEY, sms, chain, T0)
    code = sms.sent[-1].params["code"]
    assert state.otp is not None and state.otp.digits == len(code) == 6
    shorter = replace(TRUST_CONFIG, otp_digits=4)
    monkeypatch.setattr(dl, "TRUST_CONFIG", shorter)
    monkeypatch.setattr(otp, "TRUST_CONFIG", shorter)
    assert len(otp.derive_code(OTP_KEY, "stop-1", state.otp.nonce)) == 4  # config did change
    assert dl.issued_code(state, OTP_KEY) == code
    state, result = dl.verify_otp(state, code, *_at(20), OTP_KEY, chain, T0)
    assert result == "verified"


def test_naive_time_is_rejected(chain: InMemoryLedger) -> None:
    with pytest.raises(ValueError, match="timezone"):
        dl.start_delivery("d", "stop-1", *STOP, "drv", REPS, chain, datetime(2026, 10, 2))


# --- ledger ------------------------------------------------------------------------------


def test_every_state_change_and_the_outcome_are_in_a_valid_ledger(
    chain: InMemoryLedger, sms: FakeSmsSender
) -> None:
    state = _with_replies(_verified(chain, sms), chain, sms, ["1", "1", "1"])
    state = dl.close_delivery(state, chain, T0 + WINDOW + timedelta(seconds=1))
    types = [entry.event_type for entry in chain.entries]
    assert types[:4] == ["delivery_started", "otp_issued", "geofence_checked", "otp_attempted"]
    assert "residents_sampled" in types
    assert types.count("resident_replied") == 3
    assert types[-1] == "delivery_outcome"
    final = chain.entries[-1]
    assert (final.entity_type, final.entity_id) == ("delivery", "del-1")
    assert final.payload["outcome"] == "Confirmed"
    assert final.payload["counts_toward_debt"] is True
    assert final.payload["actor"] == "system"
    assert ledger.verify_entries(list(chain.entries), LEDGER_KEY)["valid"]


def test_ledger_payloads_hold_no_code_or_phone(chain: InMemoryLedger, sms: FakeSmsSender) -> None:
    _with_replies(_verified(chain, sms), chain, sms, ["1"])
    codes = {m.params["code"] for m in sms.sent if "code" in m.params}
    phones = {m.to for m in sms.sent}
    text = " ".join(ledger.payload_json(e.payload) for e in chain.entries)
    assert not any(secret in text for secret in codes | phones)


def test_outcome_is_recorded_once(chain: InMemoryLedger, sms: FakeSmsSender) -> None:
    state = _with_replies(_verified(chain, sms), chain, sms, [])
    late = T0 + WINDOW + timedelta(seconds=1)
    state = dl.close_delivery(state, chain, late)
    count = len(chain.entries)
    assert dl.close_delivery(state, chain, late) is state
    assert len(chain.entries) == count


def test_ledger_port_needs_known_event_and_entity(chain: InMemoryLedger) -> None:
    with pytest.raises(ValueError, match="Unknown ledger event type"):
        chain.append("not_an_event", {"entity_type": "delivery", "entity_id": "d"}, "system")
    with pytest.raises(ValueError, match="entity"):
        chain.append("delivery_started", {}, "system")
