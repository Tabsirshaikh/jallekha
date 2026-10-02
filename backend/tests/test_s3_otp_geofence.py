"""S3: OTP, geofence and geometry helpers ported from v1."""

from __future__ import annotations

from datetime import datetime

import pytest

from app.config.trust import TRUST_CONFIG
from app.services import geo, geofence, otp

KEY = "test-otp-key"


def test_otp_derivation_and_hash() -> None:
    code = otp.derive_code(KEY, "stop-1", "abc")
    assert len(code) == TRUST_CONFIG.otp_digits and code.isdigit()
    assert otp.derive_code(KEY, "stop-1", "abc") == code
    stored = otp.code_hash(KEY, code, "stop-1")
    assert otp.check(KEY, f" {code} ", "stop-1", stored)
    assert not otp.check(KEY, "9999" if code != "9999" else "0000", "stop-1", stored)
    assert not otp.check(KEY, code, "stop-2", stored)


def test_otp_expiry() -> None:
    assert otp.is_expired(datetime(2026, 1, 1), datetime(2026, 1, 1, 0, 1))
    assert not otp.is_expired(datetime(2026, 1, 1), datetime(2026, 1, 1))


def test_otp_needs_a_key() -> None:
    with pytest.raises(ValueError, match="key"):
        otp.derive_code(None, "stop-1", "abc")


def test_nonces_differ() -> None:
    assert otp.new_nonce() != otp.new_nonce()


def test_haversine_and_offset_agree() -> None:
    lat, lng = 17.37, 78.43
    moved = geo.offset_point(lat, lng, 1000, 90)
    assert geo.haversine_m(lat, lng, *moved) == pytest.approx(1000, abs=0.5)
    assert geo.haversine_km(lat, lng, *moved) == pytest.approx(1.0, abs=0.001)


def test_geofence_inside_and_outside() -> None:
    lat, lng = 17.37, 78.43
    inside = geo.offset_point(lat, lng, 120, 30)
    outside = geo.offset_point(lat, lng, 240, 30)
    assert geofence.check(*inside, lat, lng).inside
    result = geofence.check(*outside, lat, lng)
    assert not result.inside and 230 < result.distance_m < 250
    assert result.radius_m == TRUST_CONFIG.geofence_radius_metres
    assert not geofence.check(None, None, lat, lng).inside


def test_geofence_override_is_capped() -> None:
    lat, lng = 17.37, 78.43
    outside = geo.offset_point(lat, lng, 240, 30)
    assert geofence.check(*outside, lat, lng, radius_m=1000).radius_m == 300
