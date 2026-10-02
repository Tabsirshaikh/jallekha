"""HMWSSB sections placed on 2016 wards (closes the A3 section/ward gap).

Sections have no published boundaries; each is placed by an OSM lookup of its locality name,
assigned to the 2016 ward containing it, and dropped to a flagged fallback when it lies far
from the rest of its HMWSSB division (likely a wrong lookup).
"""

from __future__ import annotations

import csv
import importlib.util
import io
import json
import re
from datetime import date
from pathlib import Path

import pytest

from app.services import booking_groups, fair_queue, hmwssb, replay, service_models

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "section_wards", ROOT / "scripts/evidence/build_section_wards.py"
)
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


@pytest.fixture(scope="module")
def built() -> dict[str, bytes]:
    return builder.build()


def rows(built: dict[str, bytes]) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(built[builder.OUTPUT].decode())))


def test_artifacts_are_reproducible_and_committed(built) -> None:
    assert built == builder.build()
    for path, content in built.items():
        assert (ROOT / path).read_bytes() == content


def test_every_section_before_the_recut_has_one_row(built) -> None:
    table = rows(built)
    assert len(table) == len({r["section"] for r in table}) == 221
    assert {r["status"] for r in table} <= {
        "MAPPED",
        "UNMAPPED_NO_RESULT",
        "UNMAPPED_NO_WARD",
        "UNMAPPED_DIVISION_OUTLIER",
    }
    assert {r["ward_method"] for r in table if r["status"] == "MAPPED"} <= {
        "INSIDE",
        "NEAREST_500M",
        "OSM_NEAR_DIVISION",
        "WARD_NAME",
    }
    for row in table:
        if row["status"] == "MAPPED":
            assert row["ward_id"].startswith("relation/") and row["basis"] == "DERIVED"
        else:
            assert row["ward_id"] == ""


def test_most_bookings_are_placed(built) -> None:
    summary = json.loads(built[builder.SUMMARY])
    assert summary["mapped_booking_share"] >= 0.85
    assert summary["mapped_section_count"] >= 160


def test_sections_named_like_a_ward_land_in_or_next_to_it(built) -> None:
    """Independent check: names are not used to assign wards, only to look up a location."""
    summary = json.loads(built[builder.SUMMARY])
    assert summary["checks"]["same_name_ward_pairs"] >= 20
    assert summary["checks"]["same_name_in_or_adjacent_share"] >= 0.8


def test_division_outliers_are_not_used(built) -> None:
    for row in rows(built):
        if row["status"] == "UNMAPPED_DIVISION_OUTLIER":
            assert float(row["division_distance_km"]) > builder.OUTLIER_KM
    table = {r["section"]: r for r in rows(built)}
    # the only OSM answer is another place with the same name, 22 km away: not used
    assert table["PRAGATHINAGAR (PD 7)"]["status"] == "UNMAPPED_DIVISION_OUTLIER"
    # the first answer was the wrong Meerpet (13.8 km); the second pass picks the one in division
    assert table["MEERPET (DIV 20)"]["ward_method"] == "OSM_NEAR_DIVISION"
    assert float(table["MEERPET (DIV 20)"]["division_distance_km"]) < 2
    # a wide edge-of-city division keeps its correctly placed sections
    assert table["MANIKONDA (DIV 18)"]["status"] == "MAPPED"


def test_spelling_variants_and_common_names_are_resolved_inside_the_division(built) -> None:
    table = {r["section"]: r for r in rows(built)}
    # spelling variant of a 2016 ward name
    assert table["MEHIDIPATNAM"]["ward_method"] == "WARD_NAME"
    assert table["MEHIDIPATNAM"]["ward_name"] == "Ward 70 Mehdipatnam"
    assert table["VENGALRAONAGAR"]["ward_name"] == "Ward 99 Vengal Rao Nagar"
    # a common name with several OSM places: the one inside its own division
    assert table["SRINIVAS NAGAR"]["ward_method"] == "OSM_NEAR_DIVISION"
    # a similar-looking ward name 20 km from the division is rejected
    assert table["SHAPOORNAGAR"]["ward_name"] != "Ward 19 Saroornagar"
    for row in table.values():
        if row["ward_method"] in ("OSM_NEAR_DIVISION", "WARD_NAME") and row["division_distance_km"]:
            assert float(row["division_distance_km"]) <= builder.OUTLIER_KM


# ---------------- booking groups for the A3 queue ----------------


def test_groups_and_entitlements_cover_every_section() -> None:
    mapping = booking_groups.load_section_wards(ROOT)
    needs = service_models.build_ward_needs(service_models.load_evidence(ROOT), ())
    entitlement, fallback = booking_groups.group_entitlements(needs, mapping)
    for section, link in mapping.items():
        group = booking_groups.group_for(section, mapping)
        assert entitlement[group] > 0
        if link.ward_id is None:
            assert group == f"section:{section}" and group in fallback
        else:
            assert group == f"ward:{link.ward_id}"


def test_a_replayed_day_runs_through_the_fair_queue() -> None:
    mapping = booking_groups.load_section_wards(ROOT)
    needs = service_models.build_ward_needs(service_models.load_evidence(ROOT), ())
    entitlement, _ = booking_groups.group_entitlements(needs, mapping)
    data = hmwssb.read_rows(ROOT / "data/raw/hmwssb_tankers_portal")
    days = [d for d in replay.daily_counts(data, ((2025, 5),), seed=1) if d.day == date(2025, 5, 6)]
    pending = [
        fair_queue.QueueBooking(
            b.booking_id,
            booking_groups.group_for(b.section, mapping),
            b.arrived_at,
            2,
            b.booking_id,
            "domestic",
        )
        for b in replay.arrivals(days, seed=1)
    ]
    result = fair_queue.order_bookings(
        pending, len(pending) // 2, entitlement, fair_queue.QueueState()
    )
    assert len(result.served) == len(pending) // 2
    assert all(re.match(r"(ward|section):", d.booking.group) for d in result.served)
