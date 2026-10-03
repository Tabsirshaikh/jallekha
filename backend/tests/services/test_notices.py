"""T5 supply-notice feed (F15): officer entry -> area matching -> A5 outage -> stored ledger."""

from __future__ import annotations

import csv
import json
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.auth import get_api_config
from app.config.access import ACCESS_CONFIG
from app.config.api import ApiConfig
from app.config.notices import ALERT_TEMPLATES, NOTICE_CONFIG
from app.db import create_all, make_engine
from app.main import app
from app.models import SupplyNotice
from app.routers.notices import get_notice_service
from app.services import notices as nt
from app.services.ledger_store import StoredLedger
from app.services.sms import FakeSmsSender

LEDGER_KEY = "test-ledger-key"
T0 = datetime(2026, 10, 2, 9, 0, tzinfo=UTC)

# Small fixture index (names from P1's tables, ids shortened); the real files are tested below.
SECTIONS = [
    {
        "section": "NACHARAM",
        "lookup_name": "Nacharam",
        "ward_id": "w6",
        "ward_name": "Ward 6 Nacharam",
        "status": "MAPPED",
    },
    {
        "section": "UPPAL",
        "lookup_name": "Uppal",
        "ward_id": "w7",
        "ward_name": "Ward 7 Chilka Nagar",
        "status": "MAPPED",
    },
    {
        "section": "RAMANTHAPUR (DIV 5)",
        "lookup_name": "Ramanthapur",
        "ward_id": "w9",
        "ward_name": "Ward 9 Ramanthapur",
        "status": "MAPPED",
    },
    {
        "section": "ADARSHNAGAR",
        "lookup_name": "Adarshnagar",
        "ward_id": "",
        "ward_name": "",
        "status": "UNMAPPED_NO_RESULT",
    },
]
WARDS = {
    "w1": "Ward 1 Kapra",
    "w6": "Ward 6 Nacharam",
    "w7": "Ward 7 Chilka Nagar",
    "w9": "Ward 9 Ramanthapur",
    "w10": "Ward 10 Uppal",
}
EVIDENCE = [
    {"ward_id": "w1", "population": "50000"},
    {"ward_id": "w6", "population": "40000"},
    {"ward_id": "w9", "population": "30000"},
]


@pytest.fixture
def index() -> nt.AreaIndex:
    return nt.AreaIndex(SECTIONS, WARDS)


@pytest.fixture
def engine(tmp_path: Path) -> Iterator[Engine]:
    eng = make_engine(f"sqlite:///{(tmp_path / 'notices.db').as_posix()}")
    create_all(eng)
    yield eng
    eng.dispose()


@pytest.fixture
def store(engine: Engine) -> StoredLedger:
    return StoredLedger(engine, keyring={"k1": LEDGER_KEY}, key_id="k1")


@pytest.fixture
def service(engine: Engine, store: StoredLedger, index: nt.AreaIndex) -> nt.NoticeService:
    return nt.NoticeService(engine, ledger=store, areas=index, evidence=EVIDENCE, clock=lambda: T0)


def _notice(**overrides: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "source": "hmwssb_press_release",
        "source_ref": "https://example.org/hmwssb/notice-1",
        "raw_text": "Water supply will be interrupted in Kapra and Nacharam for pipeline works.",
        "area_names": ["Kapra", "Nacharam"],
        "start": "2026-10-03T06:00:00+05:30",
        "end": "2026-10-04T06:00:00+05:30",
        "entered_by": "officer-7",
    }
    data.update(overrides)
    return data


# --- a notice creates an outage --------------------------------------------------------------


def test_a_notice_with_area_and_hours_creates_an_outage(
    service: nt.NoticeService, engine: Engine
) -> None:
    result = service.enter(_notice())
    assert result.status == "created" and result.outage_id
    assert sorted(result.ward_ids) == ["w1", "w6"]
    assert result.hours == 24.0
    assert result.outage is not None
    assert (result.outage.source, result.outage.reason) == ("notice", "hmwssb_supply_notice")
    assert result.outage.planned_hours == 24.0 and set(result.outage.ward_ids) == {"w1", "w6"}
    with Session(engine) as session:
        stored = session.scalars(select(SupplyNotice)).one()
        assert stored.raw_text.startswith("Water supply will be interrupted")
        assert json.loads(stored.area_names_json) == ["Kapra", "Nacharam"]
        assert (stored.entered_by, stored.basis, stored.outage_id) == (
            "officer-7",
            "REAL",
            result.outage_id,
        )
        assert stored.hours == 24.0 and stored.hours_basis.startswith("DERIVED")


def test_the_outage_reaches_the_stored_ledger_and_the_chain_verifies(
    service: nt.NoticeService, store: StoredLedger
) -> None:
    result = service.enter(_notice())
    entries = store.entries
    assert [e.event_type for e in entries] == ["outage_created", "notice_published"]
    outage, notice = entries
    assert (outage.entity_type, outage.entity_id) == ("outage", result.outage_id)
    assert (outage.payload["entity_type"], outage.payload["entity_id"]) == (
        "outage",
        result.outage_id,
    )
    assert (
        outage.payload["reason"] == "hmwssb_supply_notice" and outage.payload["source"] == "notice"
    )
    assert (notice.entity_type, notice.entity_id) == ("supply_notice", result.notice_id)
    assert notice.payload["outage_id"] == result.outage_id
    assert result.ledger_seqs == [1, 2]
    assert store.verify().valid


def test_no_free_text_or_phone_in_ledger_payloads(
    service: nt.NoticeService, store: StoredLedger
) -> None:
    service.enter(_notice(raw_text="Call 9800000001, pipeline burst near Ramesh's shop"))
    text = json.dumps([e.payload for e in store.entries], ensure_ascii=False)
    for secret in ("9800000001", "Ramesh", "pipeline burst", "Kapra", "Nacharam", "example.org"):
        assert secret not in text


# --- duplicates ------------------------------------------------------------------------------


def test_a_duplicate_notice_is_not_entered_twice(
    service: nt.NoticeService, engine: Engine, store: StoredLedger
) -> None:
    first = service.enter(_notice())
    again = service.enter(
        _notice(area_names=["nacharam", " KAPRA "], raw_text="same notice, retyped")
    )
    assert (again.status, again.notice_id, again.outage_id) == (
        "duplicate",
        first.notice_id,
        first.outage_id,
    )
    with Session(engine) as session:
        assert len(session.scalars(select(SupplyNotice)).all()) == 1
    assert len(store.entries) == 2


def test_a_different_time_is_a_different_notice(service: nt.NoticeService) -> None:
    service.enter(_notice())
    later = service.enter(
        _notice(start="2026-10-05T06:00:00+05:30", end="2026-10-05T18:00:00+05:30")
    )
    assert later.status == "created"


# --- area matching ---------------------------------------------------------------------------


def test_matching_gives_a_confidence(index: nt.AreaIndex) -> None:
    kapra = index.match("Kapra")
    assert (kapra.status, kapra.ward_id, kapra.confidence, kapra.method) == (
        "matched",
        "w1",
        1.0,
        "ward_name",
    )
    section = index.match("Ramanthapur (Div 5)")
    assert (section.status, section.ward_id, section.method) == ("matched", "w9", "section_name")


def test_an_unmatched_area_is_flagged_and_not_guessed(
    service: nt.NoticeService, index: nt.AreaIndex
) -> None:
    unknown = index.match("Narnia Colony")
    assert (unknown.status, unknown.ward_id, unknown.reason) == (
        "flagged",
        None,
        "no_confident_match",
    )
    result = service.enter(_notice(area_names=["Kapra", "Narnia Colony"]))
    assert result.status == "created" and result.ward_ids == ["w1"]
    assert result.needs_officer_review
    assert [f.name for f in result.flagged] == ["Narnia Colony"]


def test_a_near_miss_is_flagged_with_a_suggestion_not_used(index: nt.AreaIndex) -> None:
    close = index.match("Nacharm")  # a typo: similar, but below the acceptance threshold
    assert close.status == "flagged" and close.ward_id is None
    assert close.suggestion == "Ward 6 Nacharam"
    assert 0 < close.confidence < NOTICE_CONFIG.area_match_min_confidence


def test_a_name_that_points_to_two_wards_is_flagged(index: nt.AreaIndex) -> None:
    # "Uppal" is Ward 10's name, but P1 placed the UPPAL section in Ward 7.
    uppal = index.match("Uppal")
    assert (uppal.status, uppal.ward_id, uppal.reason) == ("flagged", None, "ambiguous")


def test_an_unplaced_section_is_flagged(index: nt.AreaIndex) -> None:
    match = index.match("Adarshnagar")
    assert (match.status, match.reason) == ("flagged", "section_unplaced")


def test_a_notice_with_no_matched_area_creates_no_outage(
    service: nt.NoticeService, store: StoredLedger
) -> None:
    result = service.enter(_notice(area_names=["Narnia Colony", "Uppal"]))
    assert (result.status, result.outage_id, result.ward_ids) == ("needs_review", None, [])
    assert result.needs_officer_review and len(result.flagged) == 2
    assert [e.event_type for e in store.entries] == ["notice_published"]
    assert store.verify().valid


def test_real_area_tables_load() -> None:
    # Counts come from P1's files, read here with plain csv / json (not AreaIndex), so the test
    # checks that T5 loads the tables and does not break when P1 places more sections.
    repo = Path(__file__).resolve().parents[3]
    with (repo / "data/derived/crosswalk/section_to_ward_2016.csv").open(
        encoding="utf-8", newline=""
    ) as handle:
        rows = list(csv.DictReader(handle))
    total = len(rows)
    placed = sum(1 for row in rows if row["status"] == "MAPPED" and row["ward_id"])
    geojson = json.loads(
        (repo / "data/raw/geography/datameet/ghmc-wards.geojson").read_text(encoding="utf-8")
    )
    wards = len(geojson["features"])
    assert total >= 200 and 0 < placed < total and wards == 145

    real = nt.AreaIndex.from_files()
    assert (real.section_count, real.placed_section_count, real.ward_count) == (
        total,
        placed,
        wards,
    )
    assert real.match("Kapra").status == "matched"
    assert real.match("Uppal").reason == "ambiguous"


# --- time range ------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "times",
    [
        {"start": "2026-10-04T06:00:00+05:30", "end": "2026-10-03T06:00:00+05:30"},  # backwards
        {"start": "2026-10-03T06:00:00+05:30", "end": "2026-10-03T06:00:00+05:30"},  # empty
        {"start": "tomorrow morning", "end": "2026-10-03T18:00:00+05:30"},  # not a time
        {"start": "2026-10-03T06:00:00", "end": "2026-10-03T18:00:00"},  # no zone
        {"start": "2026-10-03T06:00:00+05:30"},  # no end
        {"end": "2026-10-03T18:00:00+05:30"},  # no start
    ],
)
def test_a_malformed_time_range_is_rejected(
    service: nt.NoticeService, engine: Engine, times: dict[str, str]
) -> None:
    data = _notice()
    data.pop("start")
    data.pop("end")
    result = service.enter({**data, **times})
    assert result.status == "invalid" and result.error
    with Session(engine) as session:
        assert session.scalars(select(SupplyNotice)).all() == []


def test_other_bad_input_is_rejected(service: nt.NoticeService) -> None:
    assert service.enter(_notice(area_names=[])).status == "invalid"
    assert service.enter(_notice(source="whatsapp_forward")).status == "invalid"
    assert service.enter(_notice(entered_by="")).status == "invalid"
    assert service.enter(_notice(people_affected=-5)).status == "invalid"


# --- people affected (OPEN rule) ------------------------------------------------------------


def test_people_affected_uses_the_officer_figure(service: nt.NoticeService) -> None:
    result = service.enter(_notice(people_affected=1200))
    assert (result.people_affected, result.people_affected_basis) == (
        1200.0,
        "REPORTED: officer figure",
    )
    assert result.outage is not None and result.outage.people_affected == 1200.0
    assert not result.needs_officer_review


def test_people_affected_falls_back_to_census_with_labels(service: nt.NoticeService) -> None:
    result = service.enter(_notice())
    assert result.people_affected == 90000.0  # Kapra 50,000 + Nacharam 40,000
    assert result.people_affected_basis.startswith("DERIVED")
    assert (
        "HISTORICAL" in result.people_affected_basis
        and "Census 2011" in result.people_affected_basis
    )
    assert "OPEN" in result.people_affected_basis
    assert result.needs_officer_review  # whole-ward figure: an officer should check it


# --- resident alerts -------------------------------------------------------------------------


def test_alert_text_exists_in_all_four_languages() -> None:
    for key, by_language in ALERT_TEMPLATES.items():
        assert (
            set(by_language) == set(ACCESS_CONFIG.supported_languages) == {"te", "ur", "hi", "en"}
        )
        for language in by_language:
            rendered = nt.render_alert(
                key,
                language,
                {"areas": "Kapra", "start": "03 Oct 06:00", "end": "04 Oct 06:00", "hours": "24"},
            )
            assert "{" not in rendered and "Kapra" in rendered and "24" in rendered, (key, language)


def test_alerts_are_template_keys_sent_by_language(service: nt.NoticeService) -> None:
    result = service.enter(_notice())
    sms = FakeSmsSender()
    sent = service.send_alerts(
        result.notice_id,
        [("+919800000001", "te"), ("+919800000002", "ur"), ("+919800000003", "fr")],
        sms,
    )
    assert sent == 3
    assert [(m.template_key, m.language) for m in sms.sent] == [
        ("notice.supply_interruption", "te"),
        ("notice.supply_interruption", "ur"),
        ("notice.supply_interruption", "en"),  # unsupported language falls back
    ]
    assert sms.sent[0].params["hours"] == "24"


def test_alert_wording_is_marked_open() -> None:
    assert "OPEN, owner to confirm" in NOTICE_CONFIG.alert_wording_basis


# --- endpoint --------------------------------------------------------------------------------


def test_officer_entry_endpoint(service: nt.NoticeService) -> None:
    app.dependency_overrides[get_notice_service] = lambda: service
    app.dependency_overrides[get_api_config] = lambda: ApiConfig(tokens={"test-token": "officer"})
    try:
        client = TestClient(app, headers={"Authorization": "Bearer test-token"})
        body = client.post("/notices", json=_notice()).json()
        assert body["status"] == "created" and body["outage_id"]
        bad = client.post("/notices", json=_notice(end="2026-10-02T00:00:00+05:30"))
        # T10, agreed with P4: an invalid notice is 422 in the shared error shape.
        assert bad.status_code == 422
        assert bad.json()["error"]["code"] == "validation_error"
    finally:
        app.dependency_overrides.clear()


def test_a_ledger_failure_keeps_the_notice_and_marks_it(
    engine: Engine, store: StoredLedger, index: nt.AreaIndex
) -> None:
    keyless = StoredLedger(engine, keyring={}, key_id="k1")
    failing = nt.NoticeService(
        engine, ledger=keyless, areas=index, evidence=EVIDENCE, clock=lambda: T0
    )
    lost = failing.enter(_notice())
    assert lost.status == "created" and lost.ledger_seqs == []
    assert failing.notice_ids_missing_ledger() == [lost.notice_id]
    working = nt.NoticeService(
        engine, ledger=store, areas=index, evidence=EVIDENCE, clock=lambda: T0
    )
    working.enter(_notice(start="2026-10-06T06:00:00+05:30", end="2026-10-06T12:00:00+05:30"))
    assert working.notice_ids_missing_ledger() == [lost.notice_id]
