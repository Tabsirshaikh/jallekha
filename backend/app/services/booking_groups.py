"""Turn a booking's HMWSSB section into a fair-queue group with an entitlement (A3, F8).

Bookings are published per section; need (A2 entitlement) is per 2016 ward. A section placed
on a ward (scripts/evidence/build_section_wards.py) joins that ward's group "ward:<id>".
A section that could not be placed, or a ward without an A2 entitlement, gets the median
ward entitlement as a flagged fallback (ASSUMED), so no booking is ever dropped.
"""

from __future__ import annotations

import csv
import statistics
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SECTION_WARDS = "data/derived/crosswalk/section_to_ward_2016.csv"


@dataclass(frozen=True)
class SectionLink:
    section: str
    ward_id: str | None
    status: str


def load_section_wards(root: Path) -> dict[str, SectionLink]:
    with (root / SECTION_WARDS).open(encoding="utf-8", newline="") as handle:
        return {
            row["section"]: SectionLink(row["section"], row["ward_id"] or None, row["status"])
            for row in csv.DictReader(handle)
        }


WARD_PREFIX = "ward:"


def ward_group(ward_id: str) -> str:
    return f"{WARD_PREFIX}{ward_id}"


def group_for(section: str, mapping: dict[str, SectionLink]) -> str:
    link = mapping.get(section)
    if link is not None and link.ward_id:
        return ward_group(link.ward_id)
    return f"section:{section}"


def group_entitlements(
    needs: list[Any], mapping: dict[str, SectionLink]
) -> tuple[dict[str, float], set[str]]:
    """Entitlement per group, and the set of groups that use the fallback."""
    by_ward = {n.ward_id: n.entitlement for n in needs if n.entitlement}
    fallback_value = statistics.median(by_ward.values())
    entitlement: dict[str, float] = {}
    fallback: set[str] = set()
    for section in mapping:
        group = group_for(section, mapping)
        if group in entitlement:
            continue
        ward_id = group.removeprefix(WARD_PREFIX) if group.startswith(WARD_PREFIX) else None
        if ward_id in by_ward:
            entitlement[group] = by_ward[ward_id]
        else:
            entitlement[group] = fallback_value
            fallback.add(group)
    return entitlement, fallback
