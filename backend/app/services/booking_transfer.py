"""Approximate section service cells; split counts by nonnegative building mass."""

import math
from collections import defaultdict

from shapely import MultiPoint, Point, voronoi_polygons
from shapely.ops import unary_union


def cells(sites, city, buffer_metres):
    if buffer_metres <= 0:
        raise ValueError("Division extent buffer must be positive")
    coordinates = sorted({(x, y) for x, y, _ in sites.values()})
    if not coordinates:
        return {}
    if len(coordinates) == 1:
        global_cells = {coordinates[0]: city}
    else:
        polygons = voronoi_polygons(MultiPoint(coordinates), extend_to=city.envelope, ordered=True)
        global_cells = dict(zip(coordinates, polygons.geoms, strict=True))
    divisions = defaultdict(list)
    for x, y, division in sites.values():
        divisions[division].append(Point(x, y))
    extents = {
        d: unary_union(points).convex_hull.buffer(buffer_metres).intersection(city)
        for d, points in divisions.items()
    }
    return {
        section: global_cells[(x, y)].intersection(extents[division]).intersection(city)
        for section, (x, y, division) in sites.items()
    }


def split(bookings, masses):
    totals, unplaced = defaultdict(float), {}
    for section, count in bookings.items():
        if not math.isfinite(count) or count < 0:
            raise ValueError("Invalid bookings")
        weights = masses.get(section, {})
        if any(not math.isfinite(v) or v < 0 for v in weights.values()):
            raise ValueError("Invalid building mass")
        denominator = sum(weights.values())
        if not denominator:
            unplaced[section] = count
            continue
        for ward, mass in weights.items():
            if mass > 0:
                totals[ward] += count * mass / denominator
    if not math.isclose(sum(totals.values()) + sum(unplaced.values()), sum(bookings.values())):
        raise ValueError("Transfer lost section booking mass")
    return dict(totals), unplaced
