"""S3: road legs (OSRM, cache, straight-line estimate) ported from v1."""

from __future__ import annotations

import io
import json

import pytest

from app.config.allocation import ALLOCATION_CONFIG
from app.services import geo, routing

A = (17.40, 78.40)
B = (17.45, 78.48)


@pytest.fixture(autouse=True)
def empty_cache() -> None:
    routing.clear_cache()


def test_same_point_is_zero() -> None:
    leg = routing.leg(A, A, allow_network=False)
    assert leg["km"] == 0 and leg["min"] == 0 and leg["source"] == "same"


def test_estimate_without_network() -> None:
    leg = routing.leg(A, B, allow_network=False)
    straight = geo.haversine_km(*A, *B)
    assert leg["source"] == "estimate"
    assert leg["km"] == pytest.approx(straight * ALLOCATION_CONFIG.road_factor, abs=0.001)
    assert leg["min"] == pytest.approx(leg["km"] / ALLOCATION_CONFIG.avg_speed_kmph * 60, abs=0.01)


def test_no_osrm_url_means_no_request(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("network must not be used")

    monkeypatch.setattr(routing.urllib.request, "urlopen", fail)
    assert routing.fetch_leg(A, B, base_url=None) is None


def test_osrm_answer_is_parsed_and_cached(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    body = {
        "code": "Ok",
        "routes": [
            {
                "distance": 12345.0,
                "duration": 1800.0,
                "geometry": {"coordinates": [[78.4, 17.4], [78.48, 17.45]]},
            }
        ],
    }

    def fake_urlopen(url: str, timeout: float) -> io.BytesIO:
        calls.append(url)
        return io.BytesIO(json.dumps(body).encode())

    monkeypatch.setattr(routing.urllib.request, "urlopen", fake_urlopen)
    first = routing.leg(A, B, base_url="http://osrm.test")
    second = routing.leg(A, B, base_url="http://osrm.test")
    assert (
        first
        == second
        == {
            "km": 12.345,
            "min": 30.0,
            "geometry": [[78.4, 17.4], [78.48, 17.45]],
            "source": "osrm",
        }
    )
    assert len(calls) == 1
    assert calls[0].startswith("http://osrm.test/route/v1/driving/78.4,17.4;78.48,17.45")


def test_osrm_failure_falls_back_to_estimate(monkeypatch: pytest.MonkeyPatch) -> None:
    def broken(*_args: object, **_kwargs: object) -> None:
        raise OSError("down")

    monkeypatch.setattr(routing.urllib.request, "urlopen", broken)
    assert routing.leg(A, B, base_url="http://osrm.test")["source"] == "estimate"


def test_matrix_shape_and_diagonal() -> None:
    km, minutes = routing.matrix([A, B, A], allow_network=False)
    assert len(km) == 3 and all(len(row) == 3 for row in km)
    assert km[0][0] == 0 and km[0][2] == 0 and km[0][1] > 0
    assert minutes[1][0] == pytest.approx(minutes[0][1])
