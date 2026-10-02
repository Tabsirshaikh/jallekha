"""F12 delivery proof (T3): OTP + server-side geofence + resident check -> four outcomes.

| OTP          | Residents   | Outcome     |
|--------------|-------------|-------------|
| verified     | mostly yes  | Confirmed   |
| verified     | mostly no   | Disputed    |
| not verified | mostly yes  | Unconfirmed |
| not verified | mostly no   | Failed      |

Silence counts for nothing: only replies are counted. With no majority (a tie or zero
replies) the outcome waits for the reply window, then falls back to the OTP alone. That
rule, the majority margin and the OTP length / validity / attempt limit are OPEN decisions
(config/trust.py). Only Confirmed counts toward water debt (F11, P2's A6).

The service holds no database: state is an immutable `DeliveryState`, and every state change
is written through a `LedgerPort`. OTP codes and the geofence distance come from the S3
functions (`services/otp.py`, `services/geofence.py`), used unchanged.
"""

from __future__ import annotations

import math
import random
import unicodedata
from collections.abc import Collection, Iterable
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from typing import Any, Literal, cast

from app.config.trust import TRUST_CONFIG
from app.services import geofence, otp
from app.services.ledger_port import LedgerPort
from app.services.sms import SmsMessage, SmsSender, message_language

Outcome = Literal["Confirmed", "Disputed", "Unconfirmed", "Failed"]
Answer = Literal["yes", "no"]
VerifyResult = Literal[
    "verified",
    "already_verified",
    "wrong_code",
    "expired",
    "locked",
    "outside_geofence",
    "invalid_location",
    "no_otp",
]
LocationStatus = Literal["inside", "outside", "no_location", "invalid_location"]

OTP_TEMPLATE = "delivery.otp"
RESIDENT_CHECK_TEMPLATE = "delivery.resident_check"
SYSTEM = "system"

_TABLE: dict[tuple[bool, Answer], Outcome] = {
    (True, "yes"): "Confirmed",
    (True, "no"): "Disputed",
    (False, "yes"): "Unconfirmed",
    (False, "no"): "Failed",
}


@dataclass(frozen=True)
class Representative:
    id: str
    stop_id: str
    phone: str
    language: str


@dataclass(frozen=True)
class Resident:
    id: str
    phone: str
    language: str


@dataclass(frozen=True)
class OtpChallenge:
    representative_id: str
    nonce: str
    code_hash: str
    digits: int  # stored with the OTP (S3 review D11)
    issued_at: datetime
    expires_at: datetime


@dataclass(frozen=True)
class OutcomeDecision:
    outcome: Outcome
    rule: Literal["majority", "no_majority_fallback"]
    otp_verified: bool
    yes: int
    no: int
    silent: int
    basis: str


@dataclass(frozen=True)
class LocationCheck:
    """T3's geofence result. Invalid input is a status here, never an unhandled error."""

    status: LocationStatus
    inside: bool
    distance_m: float | None  # None when there is no usable position
    radius_m: float | None  # None when the radius itself is invalid
    reason: str | None = None  # invalid_coordinates | invalid_radius


@dataclass(frozen=True)
class DeliveryState:
    delivery_id: str
    stop_id: str
    stop_lat: float
    stop_lon: float
    driver_id: str
    representatives: tuple[Representative, ...]
    started_at: datetime
    geofence_radius_m: float | None = None  # per-stop override; None = config (150 m)
    otp: OtpChallenge | None = None
    wrong_attempts: int = 0
    outside_tries: int = 0
    otp_verified: bool = False
    sampled_resident_ids: tuple[str, ...] = ()
    sample_seed: str | None = None
    sampled_at: datetime | None = None
    responses: tuple[tuple[str, Answer], ...] = ()
    outcome: OutcomeDecision | None = None

    @property
    def otp_locked(self) -> bool:
        return self.wrong_attempts >= TRUST_CONFIG.otp_max_attempts


def _aware(now: datetime) -> datetime:
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("Use a timezone-aware UTC datetime")
    return now


def _log(
    ledger: LedgerPort,
    event: str,
    state: DeliveryState,
    now: datetime,
    actor: str = SYSTEM,
    **fields: Any,
) -> None:
    payload: dict[str, Any] = {
        "entity_type": "delivery",
        "entity_id": state.delivery_id,
        "stop_id": state.stop_id,
        "at": now.isoformat(),
        **fields,
    }
    ledger.append(event, payload, actor)


def start_delivery(
    delivery_id: str,
    stop_id: str,
    stop_lat: float,
    stop_lon: float,
    driver_id: str,
    representatives: Iterable[Representative],
    ledger: LedgerPort,
    now: datetime,
    radius_m: float | None = None,
) -> DeliveryState:
    reps = tuple(representatives)
    low, high = TRUST_CONFIG.delivery_representatives_min, TRUST_CONFIG.delivery_representatives_max
    if not low <= len(reps) <= high:
        raise ValueError(f"A stop needs {low}-{high} registered representatives, got {len(reps)}")
    if any(rep.stop_id != stop_id for rep in reps):
        raise ValueError(f"Every representative must belong to stop {stop_id}")
    state = DeliveryState(
        delivery_id, stop_id, stop_lat, stop_lon, driver_id, reps, _aware(now), radius_m
    )
    _log(
        ledger,
        "delivery_started",
        state,
        now,
        actor=driver_id,
        representative_ids=[rep.id for rep in reps],
    )
    return state


def locate(state: DeliveryState, lat: float | None, lon: float | None) -> LocationCheck:
    """Run the S3 geofence check; turn its input errors (S3 review D7, D9) into a status."""
    radius = state.geofence_radius_m
    if radius is not None and not (
        isinstance(radius, int | float) and math.isfinite(radius) and radius > 0
    ):
        return LocationCheck("invalid_location", False, None, None, "invalid_radius")
    try:
        fence = geofence.check(lat, lon, state.stop_lat, state.stop_lon, radius_m=radius)
    except ValueError:  # NaN, infinite or out-of-range coordinates (driver or stop)
        return LocationCheck("invalid_location", False, None, None, "invalid_coordinates")
    if fence.distance_m is None:
        return LocationCheck("no_location", False, None, fence.radius_m)
    status: LocationStatus = "inside" if fence.inside else "outside"
    return LocationCheck(status, fence.inside, fence.distance_m, fence.radius_m)


def check_geofence(
    state: DeliveryState, lat: float | None, lon: float | None, ledger: LedgerPort, now: datetime
) -> tuple[DeliveryState, LocationCheck]:
    """Server-side check of the driver's position against the stop (150 m, F12)."""
    location = locate(state, lat, lon)
    _log_location(state, location, ledger, _aware(now))
    return state, location


def _log_location(
    state: DeliveryState, location: LocationCheck, ledger: LedgerPort, now: datetime
) -> None:
    _log(
        ledger,
        "geofence_checked",
        state,
        now,
        actor=state.driver_id,
        status=location.status,
        reason=location.reason,
        inside=location.inside,
        distance_m=location.distance_m,
        radius_m=location.radius_m,
    )


def request_otp(
    state: DeliveryState,
    representative_id: str,
    otp_key: str,
    sms: SmsSender,
    ledger: LedgerPort,
    now: datetime,
    nonce: str | None = None,
) -> DeliveryState:
    """Issue (or reissue) the OTP to one registered representative. Reissue keeps the count."""
    now = _aware(now)
    if state.otp_verified:
        raise ValueError("OTP already verified for this delivery")
    if state.otp_locked:
        raise ValueError("OTP locked: wrong-attempt limit reached for this stop")
    rep = next((r for r in state.representatives if r.id == representative_id), None)
    if rep is None:
        raise ValueError(f"Representative {representative_id} is not registered for this stop")
    nonce = nonce or otp.new_nonce()
    digits = TRUST_CONFIG.otp_digits
    code = otp.derive_code(otp_key, state.stop_id, nonce, digits=digits)
    expires_at = now + timedelta(minutes=TRUST_CONFIG.otp_valid_minutes)
    challenge = OtpChallenge(
        rep.id, nonce, otp.code_hash(otp_key, code, state.stop_id), digits, now, expires_at
    )
    sms.send(
        SmsMessage(
            to=rep.phone,
            template_key=OTP_TEMPLATE,
            language=message_language(rep.language),
            params={"code": code, "valid_minutes": str(TRUST_CONFIG.otp_valid_minutes)},
        )
    )
    _log(
        ledger,
        "otp_issued",
        state,
        now,
        actor=state.driver_id,
        representative_id=rep.id,
        expires_at=expires_at.isoformat(),
        wrong_attempts=state.wrong_attempts,
    )
    return replace(state, otp=challenge)


def issued_code(state: DeliveryState, otp_key: str) -> str:
    """Re-derive the issued code (e.g. to resend it) with the digit count stored at issue."""
    if state.otp is None:
        raise ValueError("No OTP issued for this delivery")
    return otp.derive_code(otp_key, state.stop_id, state.otp.nonce, digits=state.otp.digits)


def verify_otp(
    state: DeliveryState,
    code: str,
    lat: float | None,
    lon: float | None,
    otp_key: str,
    ledger: LedgerPort,
    now: datetime,
) -> tuple[DeliveryState, VerifyResult]:
    """Check the code at the stop. Only a wrong code inside the geofence uses up an attempt.

    The geofence is checked before the code, so a try from outside reveals nothing about the
    code. An invalid position or radius gives `invalid_location` and counts as an outside try.
    Outside tries are logged up to `outside_tries_max` per visit, then one
    `outside_tries_exceeded` entry, then nothing (OPEN value, config/trust.py).
    """
    now = _aware(now)
    result: VerifyResult
    if state.otp_verified:
        result = "already_verified"
    elif state.otp_locked:
        result = "locked"
    elif state.otp is None:
        result = "no_otp"
    elif otp.is_expired(state.otp.expires_at, now):
        result = "expired"
    else:
        location = locate(state, lat, lon)
        if not location.inside:
            invalid = location.status == "invalid_location"
            result = "invalid_location" if invalid else "outside_geofence"
            state = replace(state, outside_tries=state.outside_tries + 1)
            cap = TRUST_CONFIG.outside_tries_max
            if state.outside_tries > cap:
                if state.outside_tries == cap + 1:
                    _log(
                        ledger,
                        "outside_tries_exceeded",
                        state,
                        now,
                        actor=state.driver_id,
                        outside_tries=state.outside_tries,
                        outside_tries_max=cap,
                    )
                return state, result
        _log_location(state, location, ledger, now)
        if location.inside:
            if otp.check(otp_key, code, state.stop_id, state.otp.code_hash):
                result = "verified"
                state = replace(state, otp_verified=True)
            else:
                result = "wrong_code"
                state = replace(state, wrong_attempts=state.wrong_attempts + 1)
    _log(
        ledger,
        "otp_attempted",
        state,
        now,
        actor=state.driver_id,
        result=result,
        wrong_attempts=state.wrong_attempts,
        max_attempts=TRUST_CONFIG.otp_max_attempts,
        locked=state.otp_locked,
        outside_tries=state.outside_tries,
    )
    return state, result


def sample_residents(
    resident_ids: Iterable[str], seed: str, exclude: Collection[str] = ()
) -> tuple[str, ...]:
    """Seeded random sample of 3-5 residents (F12); everyone if fewer than the minimum."""
    pool = sorted(set(resident_ids) - set(exclude))
    rng = random.Random(seed)
    size = rng.randint(TRUST_CONFIG.delivery_residents_min, TRUST_CONFIG.delivery_residents_max)
    return tuple(rng.sample(pool, min(size, len(pool))))


def send_resident_check(
    state: DeliveryState,
    residents: Iterable[Resident],
    seed: str,
    sms: SmsSender,
    ledger: LedgerPort,
    now: datetime,
) -> DeliveryState:
    """Ask a fresh sample "Did you get water? 1 yes / 2 no". Starts the reply window."""
    now = _aware(now)
    if state.sampled_at is not None:
        raise ValueError("Residents already sampled for this delivery")
    by_id = {resident.id: resident for resident in residents}
    sampled = sample_residents(by_id, seed, exclude={rep.id for rep in state.representatives})
    for resident_id in sampled:
        resident = by_id[resident_id]
        sms.send(
            SmsMessage(
                to=resident.phone,
                template_key=RESIDENT_CHECK_TEMPLATE,
                language=message_language(resident.language),
            )
        )
    _log(
        ledger,
        "residents_sampled",
        state,
        now,
        resident_ids=list(sampled),
        seed=seed,
        reply_window_minutes=TRUST_CONFIG.delivery_reply_window_minutes,
    )
    return replace(state, sampled_resident_ids=sampled, sample_seed=seed, sampled_at=now)


def parse_reply(text: str) -> Answer | None:
    """ "1" = yes, "2" = no, in any script's digits (e.g. Telugu, Devanagari, Arabic-Indic)."""
    cleaned = text.strip()
    if len(cleaned) != 1:
        return None
    value = unicodedata.decimal(cleaned, None)
    return "yes" if value == 1 else "no" if value == 2 else None


def _window_end(state: DeliveryState) -> datetime | None:
    if state.sampled_at is None:
        return None
    return state.sampled_at + timedelta(minutes=TRUST_CONFIG.delivery_reply_window_minutes)


def record_response(
    state: DeliveryState, resident_id: str, text: str, ledger: LedgerPort, now: datetime
) -> tuple[DeliveryState, bool]:
    """Count a sampled resident's first valid reply inside the window; ignore anything else."""
    now = _aware(now)
    answer = parse_reply(text)
    end = _window_end(state)
    if (
        answer is None
        or end is None
        or now > end
        or state.outcome is not None
        or resident_id not in state.sampled_resident_ids
        or any(rid == resident_id for rid, _ in state.responses)
    ):
        return state, False
    _log(ledger, "resident_replied", state, now, actor=resident_id, answer=answer)
    return replace(state, responses=(*state.responses, (resident_id, answer))), True


def majority(yes: int, no: int, margin: int | None = None) -> Answer | None:
    margin = TRUST_CONFIG.delivery_majority_margin if margin is None else margin
    if yes - no >= margin:
        return "yes"
    if no - yes >= margin:
        return "no"
    return None


def compute_outcome(
    otp_verified: bool,
    yes: int,
    no: int,
    window_closed: bool,
    all_replied: bool,
    silent: int = 0,
) -> OutcomeDecision | None:
    """F12 table. None means pending: replies may still arrive."""
    if not (window_closed or all_replied):
        return None
    otp_text = "OTP verified" if otp_verified else "OTP not verified"
    counts = f"{yes} yes / {no} no, {silent} silent (not counted)"
    side = majority(yes, no)
    if side is not None:
        return OutcomeDecision(
            _TABLE[(otp_verified, side)],
            "majority",
            otp_verified,
            yes,
            no,
            silent,
            f"DERIVED: F12 table; {otp_text}; residents mostly {side} ({counts}; "
            f"margin {TRUST_CONFIG.delivery_majority_margin}, OPEN)",
        )
    fallback = dict(TRUST_CONFIG.delivery_no_majority_outcome)
    return OutcomeDecision(
        cast(Outcome, fallback[otp_verified]),
        "no_majority_fallback",
        otp_verified,
        yes,
        no,
        silent,
        f"DERIVED: F12 table; {otp_text}; no resident majority ({counts}); "
        "OTP-only fallback after the reply window (OPEN)",
    )


def close_delivery(state: DeliveryState, ledger: LedgerPort, now: datetime) -> DeliveryState:
    """Decide the outcome if it can be decided now; write it to the ledger once."""
    now = _aware(now)
    if state.outcome is not None:
        return state
    end = _window_end(state)
    yes = sum(answer == "yes" for _, answer in state.responses)
    no = len(state.responses) - yes
    sampled = len(state.sampled_resident_ids)
    decision = compute_outcome(
        state.otp_verified,
        yes,
        no,
        window_closed=end is not None and now > end,
        all_replied=end is not None and sampled > 0 and len(state.responses) == sampled,
        silent=sampled - len(state.responses),
    )
    if decision is None:
        return state
    _log(
        ledger,
        "delivery_outcome",
        state,
        now,
        outcome=decision.outcome,
        rule=decision.rule,
        otp_verified=decision.otp_verified,
        yes=decision.yes,
        no=decision.no,
        silent=decision.silent,
        counts_toward_debt=counts_toward_debt(decision.outcome),
    )
    return replace(state, outcome=decision)


def counts_toward_debt(outcome: str) -> bool:
    """F11: only Confirmed deliveries reduce water debt (P2's A6 reads this)."""
    return outcome == "Confirmed"
