"""Service models and need weights per ward (A2, F7).

Each ward gets a service class and a route:
- no_connection           -> scheduled supply to fixed points (F9)
- piped_intermittent      -> booked tankers through the fair queue (F8)
- piped_normal            -> booked tankers (F8)
- piped_regularity_unknown-> booked tankers (F8); the default, because Census 2011 records
                             the water source but not supply hours.
Sudden loss of piped supply is an outage event (F10), not a class.

The Census rule only decides no_connection (most households without tap water). Officers can
set any class with a written reason; each override becomes a ledger entry.

Need weight = 1 + w_wad*WAD + w_cad*CAD + w_hardship*hardship, and entitlement = households x
need weight (the deficit-round-robin share in F8). Distance never enters the need weight.
"""

from __future__ import annotations

import csv
import math
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.config.allocation import ALLOCATION_CONFIG

EVIDENCE = "data/derived/evidence/ward_evidence.csv"
SERVICE_CLASSES = (
    "piped_regularity_unknown",
    "piped_normal",
    "piped_intermittent",
    "no_connection",
)
ROUTES = {
    "piped_regularity_unknown": "booked",
    "piped_normal": "booked",
    "piped_intermittent": "booked",
    "no_connection": "scheduled",
}


@dataclass(frozen=True)
class Override:
    ward_id: str
    service_class: str
    reason: str
    officer: str


@dataclass(frozen=True)
class WardNeed:
    ward_id: str
    ward_name: str
    households: int | None
    wad: float | None
    cad: float | None
    hardship: float | None
    non_tap_share: float | None
    service_class: str
    service_route: str
    class_basis: str  # CENSUS_2011_RULE | OFFICER | UNAVAILABLE
    override_reason: str | None
    need_weight: float | None
    entitlement: float | None  # household-equivalents for the F8 fair queue
    need_basis: str  # DERIVED | UNAVAILABLE
    scheduled_supply_candidate: bool
    needs_officer_check: bool
    check_reasons: tuple[str, ...]


def load_evidence(root: Path) -> list[dict[str, str]]:
    with (root / EVIDENCE).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _number(value: str | None) -> float | None:
    return float(value) if value not in (None, "") else None


def _validated(overrides: Iterable[Override], ward_ids: set[str]) -> dict[str, Override]:
    by_ward: dict[str, Override] = {}
    for override in overrides:
        if override.ward_id not in ward_ids:
            raise ValueError(f"Override for unknown ward: {override.ward_id}")
        if override.service_class not in SERVICE_CLASSES:
            raise ValueError(f"Unknown service class: {override.service_class}")
        if not override.reason.strip():
            raise ValueError("An override needs a written reason")
        if override.ward_id in by_ward:
            raise ValueError(f"Only one override per ward: {override.ward_id}")
        by_ward[override.ward_id] = override
    return by_ward


@dataclass(frozen=True)
class NeedWeights:
    """The three need weights of F7 (water access, phone access, hardship).

    The defaults are the configured policy weights; an officer may try others for one plan.
    """

    wad: float
    cad: float
    hardship: float

    @classmethod
    def default(cls) -> NeedWeights:
        cfg = ALLOCATION_CONFIG
        return cls(cfg.need_weight_wad, cfg.need_weight_cad, cfg.need_weight_hardship)

    def validated(self) -> NeedWeights:
        """Each weight between 0 and the configured maximum, rounded to two decimals."""
        top = ALLOCATION_CONFIG.need_weight_max
        for name, value in self.as_dict().items():
            if (
                not isinstance(value, int | float)
                or not math.isfinite(value)
                or not 0 <= value <= top
            ):
                raise ValueError(f"The {name} weight must be a number between 0 and {top:g}")
        return NeedWeights(round(self.wad, 2), round(self.cad, 2), round(self.hardship, 2))

    def as_dict(self) -> dict[str, float]:
        return {"wad": self.wad, "cad": self.cad, "hardship": self.hardship}


def need_weight(
    wad: float, cad: float, hardship: float, weights: NeedWeights | None = None
) -> float:
    w = weights or NeedWeights.default()
    return 1 + w.wad * wad + w.cad * cad + w.hardship * hardship


def build_ward_needs(
    evidence: list[dict[str, str]],
    overrides: Iterable[Override],
    weights: NeedWeights | None = None,
) -> list[WardNeed]:
    cfg = ALLOCATION_CONFIG
    by_ward = _validated(overrides, {row["ward_id"] for row in evidence})
    needs = []
    for row in evidence:
        eligible = row.get("allocation_eligible", "").lower() == "true"
        households = _number(row.get("households"))
        wad, cad = _number(row.get("wad")), _number(row.get("cad"))
        hardship, non_tap = _number(row.get("hardship")), _number(row.get("non_tap_share"))
        complete = eligible and None not in (households, wad, cad, hardship, non_tap)

        override = by_ward.get(row["ward_id"])
        if override:
            service_class, basis = override.service_class, "OFFICER"
        elif complete and non_tap >= cfg.no_connection_non_tap_share:
            service_class, basis = "no_connection", "CENSUS_2011_RULE"
        elif complete:
            service_class, basis = "piped_regularity_unknown", "CENSUS_2011_RULE"
        else:
            service_class, basis = "piped_regularity_unknown", "UNAVAILABLE"
        route = ROUTES[service_class]

        weight = need_weight(wad, cad, hardship, weights) if complete else None
        candidate = (
            complete and not override and route == "booked" and wad >= cfg.scheduled_candidate_wad
        )
        reasons = []
        if not complete:
            reasons.append("CENSUS_UNAVAILABLE")
        if row.get("review_required", "").lower() == "true":
            reasons.append("E2_REVIEW_REQUIRED")
        if candidate:
            reasons.append("SCHEDULED_SUPPLY_CANDIDATE")

        needs.append(
            WardNeed(
                ward_id=row["ward_id"],
                ward_name=row.get("ward_name", ""),
                households=int(households) if households is not None else None,
                wad=wad,
                cad=cad,
                hardship=hardship,
                non_tap_share=non_tap,
                service_class=service_class,
                service_route=route,
                class_basis=basis,
                override_reason=override.reason if override else None,
                need_weight=weight,
                entitlement=households * weight if weight is not None else None,
                need_basis="DERIVED" if weight is not None else "UNAVAILABLE",
                scheduled_supply_candidate=bool(candidate),
                needs_officer_check=bool(reasons),
                check_reasons=tuple(reasons),
            )
        )
    return needs


def override_event(override: Override, previous_class: str) -> dict[str, Any]:
    """Arguments for ledger.next_entry (with created_at_iso and key) recording an override."""
    return {
        "event_type": "override",
        "entity_type": "ward",
        "entity_id": override.ward_id,
        "payload": {
            "field": "service_class",
            "from": previous_class,
            "to": override.service_class,
            "reason": override.reason,
            "officer": override.officer,
        },
    }
