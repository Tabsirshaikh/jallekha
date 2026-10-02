"""S3 review fixes (P3 review of PR #20): D1, D3, D6, D7, D8, D9, D11, D13."""

from __future__ import annotations

import math
from dataclasses import fields, replace

import pytest

from app.config.trust import TRUST_CONFIG
from app.services import geo, geofence, ledger, otp, spam

KEY = "test-ledger-key"
STOP = (17.37, 78.43)


def chain(n: int) -> list[ledger.LedgerEntry]:
    entries: list[ledger.LedgerEntry] = []
    for i in range(n):
        entries.append(
            ledger.next_entry(
                entries[-1] if entries else None,
                "override",
                "plan",
                f"p{i}",
                {"i": i},
                f"2026-10-02T06:00:{i:02d}+00:00",
                KEY,
            )
        )
    return entries


def _changed(value: object) -> object:
    if isinstance(value, int):
        return value + 7
    if isinstance(value, dict):
        return {**value, "tampered": True}
    return f"{value}x"


@pytest.mark.parametrize("field_name", [f.name for f in fields(ledger.LedgerEntry)])
def test_d1_editing_any_stored_field_is_detected(field_name: str) -> None:
    entries = chain(5)
    entries[2] = replace(entries[2], **{field_name: _changed(getattr(entries[2], field_name))})
    result = ledger.verify_entries(entries, KEY)
    assert not result["valid"]
    assert result["broken_at"] in (entries[2].seq, 3)


def test_d1_entity_type_is_part_of_the_hash() -> None:
    entry = chain(1)[0]
    assert ledger.entry_hash(entry) != ledger.entry_hash(replace(entry, entity_type="ward"))


def test_d1_reorder_and_delete_still_detected() -> None:
    entries = chain(5)
    swapped = [entries[0], entries[2], entries[1], entries[3], entries[4]]
    assert not ledger.verify_entries(swapped, KEY)["valid"]
    assert not ledger.verify_entries(entries[:1] + entries[2:], KEY)["valid"]


@pytest.mark.parametrize("bad", [math.nan, math.inf, -math.inf])
def test_d3_nan_and_infinity_are_rejected(bad: float) -> None:
    with pytest.raises(ValueError):
        ledger.next_entry(None, "override", "plan", "p1", {"x": bad}, "2026-10-02", KEY)


def test_d6_points_exactly_on_the_radius_are_inside_on_every_bearing() -> None:
    radius = TRUST_CONFIG.geofence_radius_metres
    for bearing in range(360):
        point = geo.offset_point(*STOP, radius, bearing)
        assert geofence.check(*point, *STOP).inside, bearing
    outside = geo.offset_point(*STOP, radius + 0.001, 45)
    assert not geofence.check(*outside, *STOP).inside


@pytest.mark.parametrize("radius", [0, -10])
def test_d7_zero_or_negative_radius_is_an_error(radius: float) -> None:
    with pytest.raises(ValueError, match="radius"):
        geofence.check(*STOP, *STOP, radius_m=radius)


def test_d7_default_radius_only_when_none() -> None:
    assert geofence.check(*STOP, *STOP, radius_m=None).radius_m == 150
    assert geofence.check(*STOP, *STOP, radius_m=100).radius_m == 100


def test_d8_missing_coordinates_give_no_distance() -> None:
    result = geofence.check(None, None, *STOP)
    assert result.inside is False and result.distance_m is None


@pytest.mark.parametrize(
    "lat,lng",
    [(math.nan, 78.4), (17.4, math.inf), (91.0, 78.4), (17.4, -181.0)],
)
def test_d9_invalid_coordinates_are_errors(lat: float, lng: float) -> None:
    with pytest.raises(ValueError, match="coordinate"):
        geofence.check(lat, lng, *STOP)
    with pytest.raises(ValueError, match="coordinate"):
        geofence.check(*STOP, lat, lng)


def test_d11_code_depends_only_on_its_inputs_including_digits() -> None:
    four = otp.derive_code("k", "stop-1", "nonce", digits=4)
    assert four == otp.derive_code("k", "stop-1", "nonce", digits=4)
    assert len(four) == 4
    six = otp.derive_code("k", "stop-1", "nonce", digits=6)
    assert len(six) == 6
    assert otp.derive_code("k", "stop-1", "nonce") == otp.derive_code(
        "k", "stop-1", "nonce", digits=TRUST_CONFIG.otp_digits
    )


def test_d13_address_text_is_not_gibberish() -> None:
    assert spam.non_letter_ratio("H.No 12-3-456/7") == 0
    assert spam.non_letter_ratio("Flat #4, 2-1-17/A, Road No. 3") == 0
    score, reasons = spam.score(
        spam.SpamSignals(
            text="H.No 12-3-456/7",
            channel="sms",
            has_category_button=False,
            recent_from_same_phone=0,
            km_outside_area=None,
            phone_registered=False,
            area_given=False,
        )
    )
    assert not any("gibberish" in reason for reason in reasons)
    assert not spam.is_spam(score)


def test_d13_symbols_are_still_gibberish() -> None:
    assert spam.non_letter_ratio("!!! ??? ***") == 1
    assert spam.non_letter_ratio("దో దిన్ से پانی") == 0
