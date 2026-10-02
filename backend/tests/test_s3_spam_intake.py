"""S3: spam scoring and the pure intake checks ported from v1 (pipeline is T4)."""

from __future__ import annotations

import pytest

from app.services import intake, spam


def sig(**changes: object) -> spam.SpamSignals:
    base: dict[str, object] = {
        "text": "No water since morning",
        "channel": "app",
        "has_category_button": True,
        "recent_from_same_phone": 0,
        "km_outside_area": 0.0,
        "phone_registered": True,
        "area_given": True,
    }
    base.update(changes)
    return spam.SpamSignals(**base)  # type: ignore[arg-type]


def test_normal_complaint_is_not_spam() -> None:
    score, reasons = spam.score(sig())
    assert score == 0 and reasons == []
    assert not spam.is_spam(score)


def test_burst_from_one_phone_is_spam() -> None:
    score, reasons = spam.score(
        sig(channel="sms", has_category_button=False, text="??", recent_from_same_phone=7)
    )
    assert spam.is_spam(score)
    assert any("same phone" in reason for reason in reasons)


def test_burst_alone_is_not_enough() -> None:
    score, _ = spam.score(sig(recent_from_same_phone=7))
    assert score == 0.5 and not spam.is_spam(score)


def test_far_away_gibberish_is_spam() -> None:
    score, reasons = spam.score(sig(text="!!", has_category_button=False, km_outside_area=5.2))
    assert spam.is_spam(score)
    assert len(reasons) == 3


def test_voice_and_missed_call_need_no_text() -> None:
    for channel in ("voice", "missed_call"):
        score, _ = spam.score(sig(channel=channel, has_category_button=False, text=None))
        assert score == 0


def test_indian_scripts_are_not_gibberish() -> None:
    assert spam.non_letter_ratio("दो दिन से पानी नहीं आया") < 0.1
    assert spam.non_letter_ratio("రెండు రోజులుగా నీళ్లు రాలేదు") < 0.1
    assert spam.non_letter_ratio("دو دن سے پانی نہیں آیا") < 0.1
    # digits and address punctuation are neither letters nor gibberish (S3 review D13)
    assert spam.non_letter_ratio("111 222 ###") == 0
    assert spam.non_letter_ratio("!!! *** ~~~") == 1


def test_intake_rejects_unknown_channel() -> None:
    with pytest.raises(ValueError, match="channel"):
        intake.validate(intake.IntakeMessage(channel="fax"))


def test_intake_text_is_trimmed_and_blank_becomes_none() -> None:
    assert intake.clean_text("  no water \n") == "no water"
    assert intake.clean_text("   ") is None
    assert intake.clean_text(None) is None


def test_category_button_wins_then_missed_call_means_no_water() -> None:
    assert intake.preset_category(intake.IntakeMessage(channel="sms", category="leak")) == "leak"
    assert intake.preset_category(intake.IntakeMessage(channel="missed_call")) == "no_water"
    assert intake.preset_category(intake.IntakeMessage(channel="app", text="leak here")) is None
