"""Server-side geofence check (F12). Ported from v1 (S3). The server is the source of truth."""

from __future__ import annotations

from dataclasses import dataclass

from app.config.trust import TRUST_CONFIG
from app.services.geo import haversine_m


@dataclass(frozen=True)
class GeofenceResult:
    inside: bool
    distance_m: float
    radius_m: float


def check(
    lat: float | None,
    lng: float | None,
    stop_lat: float,
    stop_lng: float,
    radius_m: float | None = None,
) -> GeofenceResult:
    radius = min(
        radius_m or TRUST_CONFIG.geofence_radius_metres, TRUST_CONFIG.geofence_max_radius_metres
    )
    if lat is None or lng is None:
        return GeofenceResult(False, float("inf"), radius)
    distance = haversine_m(lat, lng, stop_lat, stop_lng)
    return GeofenceResult(distance <= radius, round(distance, 1), radius)
