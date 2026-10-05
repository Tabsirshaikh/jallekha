"""Which ward a point is in (F20): the delivery stop's ward, so its deliveries count for that ward.

An officer may name the ward when registering a stop (OFFICER). Otherwise the stop's position is
placed on the 2016 ward polygons (DERIVED; the polygons are approximate, see LIMITATIONS 1.2).
A point outside every ward stays UNPLACED: its deliveries count for no ward.
"""

from __future__ import annotations

import json
from functools import lru_cache

from shapely import STRtree
from shapely.geometry import Point, shape
from shapely.geometry.base import BaseGeometry

from app.config.env import REPO_ROOT
from app.config.report_cards import REPORT_CARD_CONFIG
from app.services import service_models

OFFICER, DERIVED, UNPLACED = "OFFICER", "DERIVED", "UNPLACED"


@lru_cache(maxsize=1)
def _polygons() -> tuple[tuple[str, ...], tuple[BaseGeometry, ...], STRtree]:
    path = REPO_ROOT / REPORT_CARD_CONFIG.ward_polygons
    features = json.loads(path.read_text(encoding="utf-8"))["features"]
    ids = tuple(str(f["properties"]["@id"]) for f in features)
    shapes = tuple(shape(f["geometry"]) for f in features)
    return ids, shapes, STRtree(shapes)


@lru_cache(maxsize=1)
def _names() -> dict[str, str]:
    return {r["ward_id"]: r["ward_name"] for r in service_models.load_evidence(REPO_ROOT)}


def known_wards() -> frozenset[str]:
    """Ward ids of the evidence table (the ids plans, cards and debts use)."""
    return frozenset(_names())


def ward_name(ward_id: str | None) -> str | None:
    return _names().get(ward_id) if ward_id is not None else None


def locate(lat: float, lon: float) -> str | None:
    """The ward whose polygon contains the point, or None. GeoJSON is (lon, lat)."""
    ids, shapes, tree = _polygons()
    point = Point(lon, lat)
    hits = sorted(ids[i] for i in tree.query(point) if shapes[i].covers(point))
    return hits[0] if hits else None


def place(lat: float, lon: float, ward_id: str | None = None) -> tuple[str | None, str]:
    """(ward id, basis) of a stop: the officer's ward if given (must be known), else the map."""
    if ward_id is not None:
        if ward_id not in known_wards():
            raise ValueError(f"Unknown ward: {ward_id}")
        return ward_id, OFFICER
    found = locate(lat, lon)
    return (found, DERIVED) if found is not None else (None, UNPLACED)
