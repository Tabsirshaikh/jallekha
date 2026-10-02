"""Server-side geofence check (F12). Ported from v1 (S3). The server is the source of truth."""

from __future__ import annotations

import math
from dataclasses import dataclass

from app.config.trust import TRUST_CONFIG
from app.services.geo import haversine_m

# A point exactly on the radius must be inside on every bearing; floating-point error in the
# distance is far below a micrometre (the T1 duplicate rule uses the same tolerance).
BOUNDARY_TOLERANCE_M = 1e-6


@dataclass(frozen=True)
class GeofenceResult:
    inside: bool
    distance_m: float | None  # None when the device sent no location
    radius_m: float


def _require_coordinate(lat: float, lng: float) -> None:
    if not (
        isinstance(lat, int | float)
        and isinstance(lng, int | float)
        and math.isfinite(lat)
        and math.isfinite(lng)
        and -90 <= lat <= 90
        and -180 <= lng <= 180
    ):
        raise ValueError(f"Invalid coordinate: lat={lat}, lng={lng}")


def check(
    lat: float | None,
    lng: float | None,
    stop_lat: float,
    stop_lng: float,
    radius_m: float | None = None,
) -> GeofenceResult:
    if radius_m is None:
        radius_m = TRUST_CONFIG.geofence_radius_metres
    elif radius_m <= 0:
        raise ValueError(f"Geofence radius must be positive, got {radius_m}")
    radius = min(radius_m, TRUST_CONFIG.geofence_max_radius_metres)
    _require_coordinate(stop_lat, stop_lng)
    if lat is None or lng is None:
        return GeofenceResult(False, None, radius)
    _require_coordinate(lat, lng)
    distance = haversine_m(lat, lng, stop_lat, stop_lng)
    return GeofenceResult(distance <= radius + BOUNDARY_TOLERANCE_M, round(distance, 1), radius)
