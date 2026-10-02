"""Road distance, time and geometry between two points. Ported from v1 (S3).

Order of preference:
1. in-memory cache of earlier OSRM answers
2. OSRM at ALLOCATION_CONFIG.osrm_url (env OSRM_URL), with a short timeout
3. estimate: straight line x road_factor at avg_speed_kmph (works offline)

v1's committed road-leg cache is not ported: it was built on v1's hand-typed filling stations.
"""

from __future__ import annotations

import json
import threading
import urllib.parse
import urllib.request
from collections.abc import Sequence
from typing import Any

from app.config.allocation import ALLOCATION_CONFIG
from app.services.geo import haversine_km

Point = tuple[float, float]  # (lat, lng)

_lock = threading.Lock()
_cache: dict[str, dict[str, Any]] = {}


def key(point: Point) -> str:
    return f"{point[0]:.5f},{point[1]:.5f}"


def pair_key(a: Point, b: Point) -> str:
    return f"{key(a)}|{key(b)}"


def clear_cache() -> None:
    with _lock:
        _cache.clear()


def estimate_leg(a: Point, b: Point) -> dict[str, Any]:
    km = haversine_km(a[0], a[1], b[0], b[1]) * ALLOCATION_CONFIG.road_factor
    return {
        "km": round(km, 3),
        "min": round(km / ALLOCATION_CONFIG.avg_speed_kmph * 60, 2),
        "geometry": [[a[1], a[0]], [b[1], b[0]]],
        "source": "estimate",
    }


def fetch_leg(a: Point, b: Point, base_url: str | None) -> dict[str, Any] | None:
    """One OSRM route request; None when OSRM is not configured or does not answer."""
    if not base_url:
        return None
    query = urllib.parse.urlencode({"overview": "simplified", "geometries": "geojson"})
    url = f"{base_url.rstrip('/')}/route/v1/driving/{a[1]},{a[0]};{b[1]},{b[0]}?{query}"
    try:
        with urllib.request.urlopen(url, timeout=ALLOCATION_CONFIG.osrm_timeout_seconds) as resp:
            data = json.loads(resp.read())
        if data.get("code") != "Ok":
            return None
        route = data["routes"][0]
        return {
            "km": round(route["distance"] / 1000, 3),
            "min": round(route["duration"] / 60, 2),
            "geometry": [[round(x, 5), round(y, 5)] for x, y in route["geometry"]["coordinates"]],
            "source": "osrm",
        }
    except (OSError, ValueError, KeyError, IndexError):
        return None


def leg(
    a: Point, b: Point, *, allow_network: bool = True, base_url: str | None = None
) -> dict[str, Any]:
    if key(a) == key(b):
        return {"km": 0.0, "min": 0.0, "geometry": [[a[1], a[0]]], "source": "same"}
    pair = pair_key(a, b)
    with _lock:
        hit = _cache.get(pair)
    if hit:
        return hit
    url = base_url if base_url is not None else ALLOCATION_CONFIG.osrm_url
    fetched = fetch_leg(a, b, url) if allow_network else None
    if fetched:
        with _lock:
            _cache[pair] = fetched
        return fetched
    return estimate_leg(a, b)


def matrix(
    points: Sequence[Point], *, allow_network: bool = False
) -> tuple[list[list[float]], list[list[float]]]:
    """(km, minutes) between every pair. Planning defaults to cache/estimate (fast, repeatable)."""
    n = len(points)
    km = [[0.0] * n for _ in range(n)]
    minutes = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(n):
            if i != j:
                result = leg(points[i], points[j], allow_network=allow_network)
                km[i][j] = result["km"]
                minutes[i][j] = result["min"]
    return km, minutes
