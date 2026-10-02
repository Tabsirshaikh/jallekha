"""Explanations for wards and bookings, with a counterfactual (F16, T7). No LLM.

Ward: service class, need weight and its components (WAD, CAD, hardship) with their `_basis`,
households and entitlement, exactly as E2 (`ward_evidence.csv`) and A2 (`build_ward_needs`)
give them, labelled "Census 2011 / historical 2016 geography", with the join-quality flags. A
ward with no usable Census data says so and shows no number.

Booking: from A3's `order_bookings` (`Decision`): tier / reason, position, arrival rank,
group, entitlement, quantum and deficit, caps that rejected it, and waiting time.

Counterfactual (Wachter et al. 2017): the smallest single change that moves a booking up at
least one place, found by re-running P2's `order_bookings` with one input changed at a time:
the booking's tier, its arrival time (= waiting time), its group's entitlement, or its group's
carried-over round-robin credit. These are the only inputs of today's ordering. Water debt is
not one (A6 does not feed A3), so it is reported as "not part of today's ordering".

A booking's place is its position in the full order of today's queue: `order_bookings` run with
capacity = all pending bookings. Serving stops at capacity, so the first `capacity` places are
exactly today's served positions.

Debt is shown only when the caller passes a `DebtAccount` (A6 stores none until A7).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import date, datetime, timedelta
from typing import Any

from app.config.explain import EXPLAIN_CONFIG, TEMPLATES, ExplainConfig
from app.services import fair_queue as fq
from app.services import water_debt
from app.services.service_models import WardNeed
from app.services.sms import message_language

NOT_INPUTS: tuple[tuple[str, str], ...] = (("water_debt", "not part of today's ordering"),)


def _number(value: str | None) -> float | None:
    return float(value) if value not in (None, "") else None


def _fmt(value: float | int | None, decimals: int = 2) -> str:
    if value is None:
        return ""
    if float(value).is_integer():
        return str(int(value))
    return f"{value:.{decimals}f}"


def render(key: str, language: str, params: Mapping[str, Any]) -> str:
    """Fill a template (TEMPLATES in config/explain.py) for a supported language."""
    return TEMPLATES[key][message_language(language)].format(**params)


# --- debt --------------------------------------------------------------------------------


@dataclass(frozen=True)
class DebtView:
    available: bool
    account_id: str | None = None
    debt_litres: float | None = None
    cap_litres: float | None = None
    in_debt_since: date | None = None


def debt_view(account: water_debt.DebtAccount | None) -> DebtView:
    if account is None:
        return DebtView(False)
    return DebtView(
        True,
        account.account_id,
        account.debt_litres,
        water_debt.cap_litres(account),
        account.in_debt_since,
    )


def _debt_line(debt: DebtView, language: str) -> str:
    if not debt.available:
        return render("explain.debt.unavailable", language, {})
    return render("explain.debt.amount", language, {"debt": _fmt(debt.debt_litres, 1)})


# --- ward --------------------------------------------------------------------------------


@dataclass(frozen=True)
class WardExplanation:
    ward_id: str
    ward_name: str
    status: str  # census | no_census_data
    service_class: str
    class_basis: str
    join_status: str
    allocation_eligible: bool
    review_required: bool
    quality_flags: tuple[str, ...]
    check_reasons: tuple[str, ...]
    census_label: str
    need_weight: float | None = None
    need_basis: str | None = None
    wad: float | None = None
    wad_basis: str | None = None
    cad: float | None = None
    cad_basis: str | None = None
    hardship: float | None = None
    hardship_basis: str | None = None
    households: int | None = None
    households_basis: str | None = None
    entitlement: float | None = None
    critical_facilities: float | None = None
    critical_facilities_basis: str | None = None
    debt: DebtView = field(default_factory=lambda: DebtView(False))


def explain_ward(
    row: Mapping[str, str], need: WardNeed, debt: water_debt.DebtAccount | None = None
) -> WardExplanation:
    """Explain one ward from its E2 row and its A2 need. Values are copied, never computed."""
    if row.get("ward_id") != need.ward_id:
        raise ValueError(f"E2 row ward {row.get('ward_id')} is not A2 need ward {need.ward_id}")
    eligible = row.get("allocation_eligible", "").lower() == "true"
    common: dict[str, Any] = {
        "ward_id": need.ward_id,
        "ward_name": row.get("ward_name", need.ward_name),
        "service_class": need.service_class,
        "class_basis": need.class_basis,
        "join_status": row.get("join_status", ""),
        "allocation_eligible": eligible,
        "review_required": row.get("review_required", "").lower() == "true",
        "quality_flags": tuple(f for f in row.get("quality_flags", "").split(";") if f),
        "check_reasons": need.check_reasons,
        "census_label": EXPLAIN_CONFIG.census_label,
        "critical_facilities": _number(row.get("critical_facilities")),
        "critical_facilities_basis": row.get("critical_facilities_basis"),
        "debt": debt_view(debt),
    }
    if not eligible or need.need_weight is None:
        return WardExplanation(status="no_census_data", **common)
    return WardExplanation(
        status="census",
        need_weight=need.need_weight,
        need_basis=need.need_basis,
        wad=need.wad,
        wad_basis=row.get("wad_basis"),
        cad=need.cad,
        cad_basis=row.get("cad_basis"),
        hardship=need.hardship,
        hardship_basis=row.get("hardship_basis"),
        households=need.households,
        households_basis=row.get("households_basis"),
        entitlement=need.entitlement,
        **common,
    )


def render_ward(e: WardExplanation, language: str) -> str:
    lines = [
        render(
            "explain.ward.class",
            language,
            {"ward": e.ward_name, "service_class": e.service_class, "class_basis": e.class_basis},
        )
    ]
    if e.status == "census":
        lines.append(
            render(
                "explain.ward.need",
                language,
                {
                    "ward": e.ward_name,
                    "need_weight": _fmt(e.need_weight),
                    "wad": _fmt(e.wad, 4),
                    "cad": _fmt(e.cad, 4),
                    "hardship": _fmt(e.hardship, 4),
                    "households": _fmt(e.households),
                    "entitlement": _fmt(e.entitlement, 1),
                    "census_label": e.census_label,
                },
            )
        )
    else:
        lines.append(
            render(
                "explain.ward.no_census",
                language,
                {"ward": e.ward_name, "join_status": e.join_status},
            )
        )
    lines.append(_debt_line(e.debt, language))
    return " ".join(lines)


# --- booking -----------------------------------------------------------------------------


@dataclass(frozen=True)
class QueueDay:
    """The inputs of one station-day for A3's order_bookings."""

    pending: Sequence[fq.QueueBooking]
    capacity: int
    entitlement: Mapping[str, float]
    state: fq.QueueState

    def run(self, capacity: int | None = None) -> fq.QueueResult:
        return fq.order_bookings(
            list(self.pending),
            self.capacity if capacity is None else capacity,
            dict(self.entitlement),
            self.state,
        )

    def places(self) -> dict[str, int]:
        """Each booking's place in the full order of today's queue."""
        full = self.run(capacity=len(self.pending))
        return {d.booking.booking_id: d.position for d in full.served}


@dataclass(frozen=True)
class BookingExplanation:
    booking_id: str
    status: str  # served | waiting | rejected
    group: str
    tier: int
    arrived_at: datetime
    place: int | None  # place in the full order of today's queue
    position: int | None = None  # today's served position (A3 Decision)
    reason: str | None = None  # TIER_0 | TIER_1 | DRR
    arrival_rank: int | None = None
    entitlement: float | None = None
    quantum: float | None = None
    deficit_before: float | None = None
    capacity: int | None = None
    cap_reason: str | None = None  # CAP_DAYS_BETWEEN | CAP_PER_DAY | CAP_PER_MONTH
    waiting_hours: float | None = None
    debt: DebtView = field(default_factory=lambda: DebtView(False))


def explain_booking(
    day: QueueDay,
    booking_id: str,
    rejections: Iterable[fq.Rejection] = (),
    debt: water_debt.DebtAccount | None = None,
    now: datetime | None = None,
) -> BookingExplanation:
    debt_info = debt_view(debt)
    for rejection in rejections:
        b = rejection.booking
        if b.booking_id == booking_id:
            return BookingExplanation(
                booking_id, "rejected", b.group, b.tier, b.arrived_at, None,
                cap_reason=rejection.reason, debt=debt_info,
                waiting_hours=_hours(now, b.arrived_at),
            )  # fmt: skip
    booking = next((b for b in day.pending if b.booking_id == booking_id), None)
    if booking is None:
        raise ValueError(f"Booking {booking_id} is not in this queue day")
    place = day.places()[booking_id]
    today = day.run()
    decision = next((d for d in today.served if d.booking.booking_id == booking_id), None)
    waited = _hours(now, booking.arrived_at)
    if decision is not None:
        return BookingExplanation(
            booking_id, "served", booking.group, booking.tier, booking.arrived_at, place,
            decision.position, decision.reason, decision.arrival_rank, decision.entitlement,
            decision.quantum, decision.deficit_before, day.capacity, None, waited, debt_info,
        )  # fmt: skip
    return BookingExplanation(
        booking_id, "waiting", booking.group, booking.tier, booking.arrived_at, place,
        capacity=day.capacity, waiting_hours=waited, debt=debt_info,
    )  # fmt: skip


def _hours(now: datetime | None, since: datetime) -> float | None:
    return round((now - since).total_seconds() / 3600, 4) if now is not None else None


def render_booking(e: BookingExplanation, language: str) -> str:
    if e.status == "served":
        line = render(
            "explain.booking.served",
            language,
            {
                "booking": e.booking_id,
                "position": e.position,
                "reason": e.reason,
                "arrival_rank": e.arrival_rank,
            },
        )
    elif e.status == "waiting":
        line = render(
            "explain.booking.waiting",
            language,
            {"booking": e.booking_id, "place": e.place, "capacity": e.capacity},
        )
    else:
        line = render(
            "explain.booking.rejected",
            language,
            {"booking": e.booking_id, "cap_reason": e.cap_reason},
        )
    return f"{line} {_debt_line(e.debt, language)}"


# --- counterfactual ----------------------------------------------------------------------


@dataclass(frozen=True)
class Change:
    input: str  # tier | arrival | group_entitlement | group_deficit
    amount: float  # minutes earlier, tier levels, entitlement ratio added, deficit added
    step: float
    from_value: Any
    to_value: Any
    after_place: int


@dataclass(frozen=True)
class Counterfactual:
    booking_id: str
    status: str  # found | no_change_within_limits | already_first
    before_place: int
    changes: tuple[Change, ...]
    not_inputs: tuple[tuple[str, str], ...] = NOT_INPUTS


def _apply(day: QueueDay, booking_id: str, change_input: str, amount: float) -> QueueDay:
    booking = next(b for b in day.pending if b.booking_id == booking_id)
    if change_input == "tier":
        new = replace(booking, tier=booking.tier - int(amount))
        return replace(day, pending=[new if b is booking else b for b in day.pending])
    if change_input == "arrival":
        new = replace(booking, arrived_at=booking.arrived_at - timedelta(minutes=amount))
        return replace(day, pending=[new if b is booking else b for b in day.pending])
    if change_input == "group_entitlement":
        entitlement = dict(day.entitlement)
        entitlement[booking.group] = entitlement[booking.group] * (1 + amount)
        return replace(day, entitlement=entitlement)
    if change_input == "group_deficit":
        deficits = dict(day.state.deficits)
        deficits[booking.group] = deficits.get(booking.group, 0.0) + amount
        return replace(day, state=replace(day.state, deficits=deficits))
    raise ValueError(f"Not an input of today's ordering: {change_input}")


def _place(day: QueueDay, booking_id: str) -> int:
    return day.places()[booking_id]


def reproduce(day: QueueDay, booking_id: str, change: Change) -> int:
    """Re-run A3 with the change applied; the booking's new place."""
    return _place(_apply(day, booking_id, change.input, change.amount), booking_id)


def step_back(change: Change) -> Change | None:
    """The same change one step smaller (None when one step is the smallest possible)."""
    smaller = round(change.amount - change.step, 9)
    if smaller <= 0:
        return None
    return replace(change, amount=smaller)


def _search(
    day: QueueDay, booking_id: str, change_input: str, step: float, limit: float, before: int
) -> tuple[float, int] | None:
    k = 1
    while round(k * step, 9) <= limit + 1e-9:
        amount = round(k * step, 9)
        place = _place(_apply(day, booking_id, change_input, amount), booking_id)
        if place <= before - 1:
            return amount, place
        k += 1
    return None


def find_counterfactual(
    day: QueueDay, booking_id: str, config: ExplainConfig = EXPLAIN_CONFIG
) -> Counterfactual:
    """For each input of today's ordering, the smallest change that moves the booking up."""
    booking = next((b for b in day.pending if b.booking_id == booking_id), None)
    if booking is None:
        raise ValueError(f"Booking {booking_id} is not in this queue day")
    before = _place(day, booking_id)
    if before == 1:
        return Counterfactual(booking_id, "already_first", before, ())
    changes: list[Change] = []
    if config.try_tier_change and booking.tier > 0:
        found = _search(day, booking_id, "tier", 1, 1, before)
        if found:
            changes.append(Change("tier", 1, 1, booking.tier, booking.tier - 1, found[1]))
    if config.arrival_max_minutes > 0:
        found = _search(
            day, booking_id, "arrival", config.arrival_step_minutes, config.arrival_max_minutes,
            before,
        )  # fmt: skip
        if found:
            amount, place = found
            changes.append(
                Change(
                    "arrival",
                    amount,
                    config.arrival_step_minutes,
                    booking.arrived_at,
                    booking.arrived_at - timedelta(minutes=amount),
                    place,
                )  # fmt: skip
            )
    if booking.tier not in (0, 1):  # entitlement and deficit only matter in round robin
        group = booking.group
        limit = config.entitlement_max_ratio - 1
        if limit > 0:
            found = _search(
                day, booking_id, "group_entitlement", config.entitlement_step_ratio, limit, before
            )
            if found:
                amount, place = found
                base = day.entitlement[group]
                changes.append(
                    Change(
                        "group_entitlement",
                        amount,
                        config.entitlement_step_ratio,
                        base,
                        base * (1 + amount),
                        place,
                    )  # fmt: skip
                )
        if config.deficit_max > 0:
            found = _search(
                day, booking_id, "group_deficit", config.deficit_step, config.deficit_max, before
            )
            if found:
                amount, place = found
                base = day.state.deficits.get(group, 0.0)
                changes.append(
                    Change("group_deficit", amount, config.deficit_step, base, base + amount, place)
                )
    status = "found" if changes else "no_change_within_limits"
    return Counterfactual(booking_id, status, before, tuple(changes))


_CF_KEYS = {
    "tier": "explain.cf.tier",
    "arrival": "explain.cf.arrival",
    "group_entitlement": "explain.cf.entitlement",
    "group_deficit": "explain.cf.deficit",
}


def render_counterfactual(cf: Counterfactual, language: str) -> str:
    if cf.status == "already_first":
        return render("explain.cf.first", language, {})
    lines: list[str] = []
    if cf.status == "no_change_within_limits":
        lines.append(render("explain.cf.none", language, {"before": cf.before_place}))
    for change in cf.changes:
        params: dict[str, Any] = {"before": cf.before_place, "after": change.after_place}
        if change.input == "tier":
            params["to"] = change.to_value
        elif change.input == "group_entitlement":
            params["amount"] = _fmt(change.amount * 100, 0)
        else:
            params["amount"] = _fmt(change.amount)
        lines.append(render(_CF_KEYS[change.input], language, params))
    lines.append(render("explain.cf.not_input", language, {}))
    return " ".join(lines)
