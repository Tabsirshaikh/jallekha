"""T4 unified intake (F14): channels, spam, languages, offline sync, voice fallback, T1 dedup."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.config.intake import INTAKE_CONFIG
from app.db import create_all, make_engine
from app.models import Complaint, DuplicateLink, IntakeItemRecord, VoiceNote
from app.services import intake_pipeline as ip
from app.services import ledger
from app.services.intake import IntakeMessage
from app.services.sms import FakeSmsSender

PHONE_KEY = "test-phone-key"
T0 = datetime(2026, 10, 2, 9, 0, tzinfo=UTC)
HERE = (17.385, 78.4867)
NEARBY = (17.3853, 78.4867)  # about 33 m north
FAR = (17.395, 78.4867)  # about 1.1 km north


class Clock:
    def __init__(self) -> None:
        self.now = T0

    def __call__(self) -> datetime:
        return self.now


class RecordingLedger:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any], str]] = []

    def append(self, entry_type: str, payload: Mapping[str, Any], actor: str) -> None:
        self.calls.append((entry_type, dict(payload), actor))


class TextTranscriber:
    def transcribe(
        self, audio: bytes, content_type: str, language_hint: str | None
    ) -> ip.Transcript | None:
        return ip.Transcript(text="నీళ్లు రాలేదు", language="te", confidence=0.82)


@pytest.fixture
def engine(tmp_path: Path) -> Iterator[Engine]:
    eng = make_engine(f"sqlite:///{(tmp_path / 'intake.db').as_posix()}")
    create_all(eng)
    yield eng
    eng.dispose()


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def sms() -> FakeSmsSender:
    return FakeSmsSender()


@pytest.fixture
def service(engine: Engine, sms: FakeSmsSender, clock: Clock, tmp_path: Path) -> ip.IntakeService:
    return ip.IntakeService(
        engine,
        sms=sms,
        transcriber=ip.FallbackTranscriber(),
        audio_store=ip.LocalAudioStore(tmp_path / "audio"),
        phone_hash_key=PHONE_KEY,
        clock=clock,
    )


def _app(text: str, where: tuple[float, float] = HERE, **extra: Any) -> dict[str, Any]:
    return {"channel": "app", "text": text, "lat": where[0], "lon": where[1], **extra}


def _complaints(engine: Engine) -> list[Complaint]:
    with Session(engine) as session:
        return list(session.scalars(select(Complaint).order_by(Complaint.created_at)))


# --- each channel creates a complaint ----------------------------------------------------


def test_app_report_creates_a_complaint(service: ip.IntakeService, engine: Engine) -> None:
    result = service.receive_json(_app("No water since morning"))
    assert (result.status, result.complaint_status, result.category) == (
        "created",
        "open",
        "no_water",
    )
    stored = _complaints(engine)[0]
    assert (stored.channel, stored.language, stored.category) == ("app", "en", "no_water")
    assert stored.category_basis.startswith("DERIVED: keyword")
    assert stored.language_basis.startswith("DERIVED: script")


def test_sms_webhook_with_any_provider_field_names(
    service: ip.IntakeService, engine: Engine
) -> None:
    for payload in (
        {"From": "+919800000001", "Body": "tanker did not come"},
        {
            "msisdn": "919800000002",
            "message": "dirty water in tap",
            "timestamp": "2026-10-02T08:59:00+00:00",
        },
        {"sender": "+919800000003", "text": "pipe leak near school"},
    ):
        assert service.receive_sms(payload).status == "created"
    assert [c.category for c in _complaints(engine)] == ["tanker_missed", "dirty_water", "leak"]
    assert all(c.channel == "sms" for c in _complaints(engine))


def test_sms_gateway_time_is_kept_when_it_has_a_zone(
    service: ip.IntakeService, engine: Engine
) -> None:
    service.receive_sms(
        {"From": "+919800000001", "Body": "no water", "timestamp": "2026-10-02T14:00:00+05:30"}
    )
    service.receive_sms({"From": "+919800000002", "Body": "no water", "time": "yesterday"})
    with Session(engine) as session:
        times = [r.client_created_at for r in session.scalars(select(IntakeItemRecord))]
    assert ip.as_utc(times[0]) == datetime(2026, 10, 2, 8, 30, tzinfo=UTC) and times[1] is None


def test_sms_payload_without_sender_or_text_is_invalid(service: ip.IntakeService) -> None:
    assert service.receive_sms({"Body": "no water"}).status == "invalid"
    assert service.receive_sms({"From": "+919800000001"}).status == "invalid"


def test_missed_call_is_no_water_assumed_and_asks_back_for_location(
    service: ip.IntakeService, engine: Engine, sms: FakeSmsSender
) -> None:
    result = service.receive_missed_call({"caller": "+919800000009"})
    assert (result.status, result.complaint_status, result.category) == (
        "created",
        "awaiting_location",
        "no_water",
    )
    stored = _complaints(engine)[0]
    assert stored.category_basis.startswith("ASSUMED")  # S3 review D14
    assert stored.lat is None and stored.lon is None
    assert [(m.to, m.template_key) for m in sms.sent] == [("+919800000009", "intake.ask_location")]


def test_field_worker_report_links_to_a_household(
    service: ip.IntakeService, engine: Engine
) -> None:
    result = service.receive_json(
        {
            "channel": "field_worker",
            "text": "నీళ్లు రాలేదు",
            "reporter_id": "fw-12",
            "household_id": "hh-77",
        }
    )
    assert result.status == "created"
    stored = _complaints(engine)[0]
    assert (stored.household_id, stored.reporter_id, stored.channel) == (
        "hh-77",
        "fw-12",
        "field_worker",
    )


def test_field_worker_report_needs_a_reporter_and_a_household_or_location(
    service: ip.IntakeService,
) -> None:
    no_reporter = {"channel": "field_worker", "text": "no water", "household_id": "hh-1"}
    no_target = {"channel": "field_worker", "text": "no water", "reporter_id": "fw-1"}
    assert service.receive_json(no_reporter).status == "invalid"
    assert service.receive_json(no_target).status == "invalid"


def test_field_worker_report_for_a_location(service: ip.IntakeService, engine: Engine) -> None:
    item = {
        "channel": "field_worker",
        "text": "leak",
        "reporter_id": "fw-1",
        "lat": HERE[0],
        "lon": HERE[1],
    }
    assert service.receive_json(item).status == "created"
    assert _complaints(engine)[0].lat == HERE[0]


# --- spam ------------------------------------------------------------------------------------


def test_spam_is_rejected_and_kept_as_an_intake_record(
    service: ip.IntakeService, engine: Engine
) -> None:
    result = service.receive_sms({"From": "+919800000001", "Body": "@!"})
    assert result.status == "spam" and result.complaint_id is None
    assert result.spam_score is not None and result.spam_score >= 0.7
    assert _complaints(engine) == []
    with Session(engine) as session:
        record = session.scalars(select(IntakeItemRecord)).one()
        assert (record.status, record.complaint_id) == ("spam", None)


def test_a_burst_from_one_phone_becomes_spam(service: ip.IntakeService) -> None:
    statuses = [
        service.receive_sms({"From": "+919800000001", "Body": f"no water street {i}"}).status
        for i in range(7)
    ]
    assert statuses[:5].count("spam") == 0 and statuses[-1] == "spam"


# --- languages -------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "language", "category"),
    [
        ("మా వీధిలో నీళ్లు రాలేదు", "te", "no_water"),
        ("ట్యాంకర్ రాలేదు", "te", "tanker_missed"),
        ("नल में गंदा पानी आ रहा है", "hi", "dirty_water"),
        ("हमारे यहाँ पानी नहीं आया", "hi", "no_water"),
        ("ہمارے علاقے میں پانی نہیں آیا", "ur", "no_water"),
        ("پائپ لیک ہو رہا ہے", "ur", "leak"),
        ("neellu raledu", "en", "no_water"),
    ],
)
def test_telugu_hindi_urdu_text_is_accepted_and_categorised(
    service: ip.IntakeService, text: str, language: str, category: str
) -> None:
    result = service.receive_json(_app(text))
    assert (result.status, result.language, result.category) == ("created", language, category)


def test_address_only_text_is_not_rejected(service: ip.IntakeService) -> None:
    result = service.receive_json(_app("H.No 12-3-456/7, 500028"))
    assert result.status == "created" and result.category == "other"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("నీరు", "te"),
        ("पानी", "hi"),
        ("پانی", "ur"),
        ("water", "en"),
        ("12-3-456", None),
        ("", None),
    ],
)
def test_language_by_script(text: str, expected: str | None) -> None:
    assert ip.detect_language(text)[0] == expected


def test_language_hint_used_when_text_has_no_letters() -> None:
    assert ip.detect_language("", hint="ur") == ("ur", "REPORTED: client language hint")
    assert ip.detect_language("", hint="xx")[0] is None


def test_arabic_letter_variants_match_urdu_keywords() -> None:
    # Arabic yeh (U+064A) typed instead of Urdu yeh (U+06CC).
    assert ip.classify("پاني نہيں", "ur")[0] == "no_water"


def test_button_category_wins_over_keywords(service: ip.IntakeService) -> None:
    result = service.receive_json(_app("tanker", category="leak"))
    assert result.category == "leak"


def test_unknown_category_or_channel_is_invalid(service: ip.IntakeService) -> None:
    assert service.receive_json(_app("x y z", category="flood")).status == "invalid"
    assert service.receive_json({"channel": "fax", "text": "no water"}).status == "invalid"


# --- offline sync ----------------------------------------------------------------------------


def test_same_client_id_twice_creates_one_item(service: ip.IntakeService, engine: Engine) -> None:
    item = _app("no water", client_id="c-1", client_created_at="2026-10-02T08:30:00+00:00")
    first = service.receive_json(item)
    second = service.receive_json(item)
    assert (first.status, second.status) == ("created", "duplicate")
    assert second.complaint_id == first.complaint_id
    assert len(_complaints(engine)) == 1
    with Session(engine) as session:
        record = session.scalars(select(IntakeItemRecord)).one()
        assert record.client_id == "c-1"
        assert record.client_created_at is not None and record.created_at is not None


def test_batch_with_one_bad_item_processes_the_others(
    service: ip.IntakeService, engine: Engine
) -> None:
    results = service.receive_batch(
        [
            _app("no water", client_id="b-1"),
            {"channel": "app", "client_id": "b-2", "lat": "not-a-number", "text": "leak"},
            _app("dirty water", FAR, client_id="b-3"),
            _app("no water", client_id="b-1"),
        ]
    )
    assert [r.status for r in results] == ["created", "invalid", "created", "duplicate"]
    assert [r.client_id for r in results] == ["b-1", "b-2", "b-3", "b-1"]
    assert results[1].error
    assert len(_complaints(engine)) == 2


def test_client_time_is_kept_next_to_server_time(service: ip.IntakeService, engine: Engine) -> None:
    service.receive_json(
        _app("no water", client_id="t-1", client_created_at="2026-10-02T07:00:00+05:30")
    )
    with Session(engine) as session:
        record = session.scalars(select(IntakeItemRecord)).one()
        assert ip.as_utc(record.client_created_at) == datetime(2026, 10, 2, 1, 30, tzinfo=UTC)
        assert ip.as_utc(record.created_at) == T0
    complaint = _complaints(engine)[0]
    expected = (
        T0
        if INTAKE_CONFIG.offline_report_time == "server"
        else datetime(2026, 10, 2, 1, 30, tzinfo=UTC)
    )
    assert ip.as_utc(complaint.created_at) == expected


def test_client_time_must_have_a_timezone(service: ip.IntakeService) -> None:
    result = service.receive_json(_app("no water", client_created_at="2026-10-02T07:00:00"))
    assert result.status == "invalid"


# --- voice -----------------------------------------------------------------------------------


def test_voice_with_asr_unavailable_gives_the_fallback_record(
    service: ip.IntakeService, engine: Engine, tmp_path: Path
) -> None:
    result = service.receive_voice(b"RIFF....WAVEfmt fake", "audio/wav", lat=HERE[0], lon=HERE[1])
    assert (result.status, result.complaint_status) == ("created", "needs_transcription")
    stored = _complaints(engine)[0]
    assert stored.needs_human_transcription and stored.text is None
    assert stored.transcript_confidence is None
    with Session(engine) as session:
        note = session.scalars(select(VoiceNote)).one()
        assert (note.complaint_id, note.needs_human, note.transcriber) == (
            stored.id,
            True,
            "fallback",
        )
        assert (tmp_path / "audio" / note.audio_ref).read_bytes() == b"RIFF....WAVEfmt fake"


def test_voice_with_a_transcript_stores_text_language_and_confidence(
    engine: Engine, sms: FakeSmsSender, clock: Clock, tmp_path: Path
) -> None:
    service = ip.IntakeService(
        engine,
        sms=sms,
        transcriber=TextTranscriber(),
        audio_store=ip.LocalAudioStore(tmp_path / "audio"),
        phone_hash_key=PHONE_KEY,
        clock=clock,
    )
    result = service.receive_voice(b"audio", "audio/ogg", lat=HERE[0], lon=HERE[1])
    assert (result.status, result.complaint_status, result.category, result.language) == (
        "created",
        "open",
        "no_water",
        "te",
    )
    stored = _complaints(engine)[0]
    assert (stored.text, stored.transcript_confidence, stored.channel) == (
        "నీళ్లు రాలేదు",
        0.82,
        "voice",
    )


def test_empty_or_oversized_audio_is_invalid(service: ip.IntakeService) -> None:
    assert service.receive_voice(b"", "audio/wav").status == "invalid"
    too_big = b"0" * (INTAKE_CONFIG.max_audio_bytes + 1)
    assert service.receive_voice(too_big, "audio/wav").status == "invalid"


def test_asr_mode_picks_the_transcriber(monkeypatch: pytest.MonkeyPatch) -> None:
    assert isinstance(ip.get_transcriber("fallback"), ip.FallbackTranscriber)

    def unavailable(*args: object, **kwargs: object) -> None:
        raise ip.TranscriberUnavailable("transformers not installed")

    monkeypatch.setattr(ip.IndicConformerTranscriber, "__init__", unavailable)
    assert isinstance(ip.get_transcriber("indicconformer"), ip.FallbackTranscriber)
    with pytest.raises(ValueError, match="ASR_MODE"):
        ip.get_transcriber("whisper")


# --- T1 duplicates ---------------------------------------------------------------------------


def test_duplicate_report_is_merged_by_t1(
    service: ip.IntakeService, engine: Engine, clock: Clock
) -> None:
    first = service.receive_json(_app("no water"))
    clock.now += timedelta(hours=3)
    second = service.receive_json(_app("no water here too", NEARBY))
    clock.now += timedelta(hours=1)
    third = service.receive_json(_app("no water", NEARBY))
    far = service.receive_json(_app("no water", FAR))
    assert (second.status, second.parent_id) == ("merged", first.complaint_id)
    assert (third.status, third.parent_id) == ("merged", first.complaint_id)  # cluster root
    assert far.status == "created"
    with Session(engine) as session:
        links = list(session.scalars(select(DuplicateLink)))
        assert {(link.child_id, link.parent_id) for link in links} == {
            (second.complaint_id, first.complaint_id),
            (third.complaint_id, first.complaint_id),
        }


def test_reports_without_location_are_not_deduplicated(service: ip.IntakeService) -> None:
    a = service.receive_missed_call({"caller": "+919800000001"})
    b = service.receive_missed_call({"caller": "+919800000002"})
    assert (a.status, b.status) == ("created", "created")


# --- privacy and ledger ----------------------------------------------------------------------


def test_raw_phone_numbers_are_never_stored(service: ip.IntakeService, engine: Engine) -> None:
    service.receive_sms({"From": "+919800000001", "Body": "no water"})
    with Session(engine) as session:
        record = session.scalars(select(IntakeItemRecord)).one()
        assert record.phone_hash and "9800000001" not in record.phone_hash
        assert len(record.phone_hash) == 64


def test_phone_needs_a_hash_key(engine: Engine, sms: FakeSmsSender, tmp_path: Path) -> None:
    keyless = ip.IntakeService(
        engine,
        sms=sms,
        transcriber=ip.FallbackTranscriber(),
        audio_store=ip.LocalAudioStore(tmp_path),
        phone_hash_key=None,
    )
    result = keyless.receive_sms({"From": "+919800000001", "Body": "no water"})
    assert result.status == "invalid" and "PHONE_HASH_KEY" in (result.error or "")


def test_no_ledger_entries_while_no_intake_event_type_exists(
    engine: Engine, sms: FakeSmsSender, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The intake types now exist; remove them for this test only to keep its purpose.
    monkeypatch.setattr(
        ledger, "EVENT_TYPES", ledger.EVENT_TYPES - set(ip.PROPOSED_EVENTS.values())
    )
    recorder = RecordingLedger()
    service = ip.IntakeService(
        engine,
        sms=sms,
        transcriber=ip.FallbackTranscriber(),
        audio_store=ip.LocalAudioStore(tmp_path),
        phone_hash_key=PHONE_KEY,
        ledger=recorder,
    )
    service.receive_json(_app("no water"))
    assert recorder.calls == []


def test_ledger_payloads_hold_ids_and_numbers_only_once_types_exist(
    engine: Engine,
    sms: FakeSmsSender,
    clock: Clock,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        ledger, "EVENT_TYPES", ledger.EVENT_TYPES | set(ip.PROPOSED_EVENTS.values())
    )
    recorder = RecordingLedger()
    service = ip.IntakeService(
        engine,
        sms=sms,
        transcriber=ip.FallbackTranscriber(),
        audio_store=ip.LocalAudioStore(tmp_path),
        phone_hash_key=PHONE_KEY,
        ledger=recorder,
        clock=clock,
    )
    service.receive_sms({"From": "+919800000001", "Body": "no water at H.No 4-5 Ramesh house"})
    service.receive_sms({"From": "+919800000002", "Body": "@!"})
    assert [call[0] for call in recorder.calls] == ["complaint_received", "complaint_marked_spam"]
    for _, payload, _ in recorder.calls:
        assert set(payload) <= ip.LEDGER_PAYLOAD_KEYS
        assert all(
            isinstance(v, int | float | bool | type(None)) or isinstance(v, str) and len(v) <= 64
            for v in payload.values()
        )
        text = repr(payload)
        assert "9800000001" not in text and "Ramesh" not in text and "no water" not in text


def test_p2_intake_message_is_used_as_is() -> None:
    item = ip.item_from_json(_app("no water", client_id="c-9"))
    assert isinstance(item.message, IntakeMessage)
    assert (item.message.channel, item.message.client_uuid, item.message.lng) == (
        "app",
        "c-9",
        HERE[1],
    )
