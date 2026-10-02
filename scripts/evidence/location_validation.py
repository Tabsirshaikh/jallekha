"""Conservative historical-geography validation; numbers and centroids are insufficient."""

from collections import Counter
from urllib.parse import urlparse

from shapely.geometry import shape

KEY_FIELDS = (
    "source_state_code",
    "source_district_code",
    "source_subdistt_code",
    "source_town_code",
    "source_ward_code",
)
WIDTHS = (2, 3, 5, 6, 4)


def source_key(row):
    values = [str(row.get(k, "")).strip() for k in KEY_FIELDS]
    if any(not v.isdigit() or len(v) > width for v, width in zip(values, WIDTHS, strict=True)):
        return ""
    return "-".join(v.zfill(width) for v, width in zip(values, WIDTHS, strict=True))


def geometry_status(source_geometry, target_geometry):
    """Only equal valid polygon footprints establish this MVP's one-to-one transfer.

    No geographic area calculation or population-by-area assumption is made.
    District/mandal containment alone cannot prove ward equivalence after delimitation.
    """
    try:
        source, target = shape(source_geometry), shape(target_geometry)
    except (ValueError, TypeError, KeyError, AttributeError):
        return "INVALID_GEOMETRY"
    if any(
        g.geom_type not in ("Polygon", "MultiPolygon") or g.is_empty or not g.is_valid
        for g in (source, target)
    ):
        return "INVALID_OR_NON_POLYGON"
    return "VERIFIED_EXACT_GEOMETRY" if source.equals(target) else "BOUNDARY_TRANSFER_REQUIRED"


def validate(rows, targets, source_layer=None):
    """Return one result per candidate row; all approval evidence must be reviewable.

    Optional source layer must contain official, reviewed Census 2011 ward polygons
    keyed by state-district-subdistrict-town-ward. Unreviewed/current polygons fail closed.
    """
    layer = source_layer or {"type": "FeatureCollection", "features": []}
    if layer.get("type") != "FeatureCollection" or not isinstance(layer.get("features"), list):
        raise ValueError("Census location source must be a FeatureCollection")
    if layer.get("crs"):
        raise ValueError(
            "Location source must use GeoJSON default EPSG:4326, without a CRS override"
        )
    target_ids = [f["properties"]["@id"] for f in targets]
    if len(target_ids) != len(set(target_ids)):
        raise ValueError("Duplicate target polygon identifiers")
    source_features = {}
    for feature in layer.get("features", []):
        key = source_key(feature.get("properties", {}))
        source_features.setdefault(key, []).append(feature)
    target_by_id = {f["properties"]["@id"]: f for f in targets}
    source_counts = Counter(source_key(r) for r in rows)
    target_counts = Counter(r["target_ward_id"] for r in rows if r["target_ward_id"])
    target_numbers = Counter(str(f["properties"]["name"]).split()[1] for f in targets)
    results = []
    for row in rows:
        key, tid = source_key(row), row["target_ward_id"]
        status = "MISSING_CENSUS2011_WARD_POLYGON"
        evidence_url = ""
        if not tid:
            status = "NO_TARGET_CANDIDATE"
        elif not key:
            status = "INCOMPLETE_SOURCE_KEY"
        elif source_counts[key] > 1 or target_counts[tid] > 1:
            status = "AMBIGUOUS_SOURCE_ASSIGNMENT"
        elif target_numbers[row["target_ward_num"]] > 1:
            status = "AMBIGUOUS_TARGET_NUMBER"
        elif tid not in target_by_id:
            status = "TARGET_NOT_FOUND"
        elif len(source_features.get(key, [])) > 1:
            status = "AMBIGUOUS_SOURCE_POLYGONS"
        elif source_features.get(key):
            feature = source_features[key][0]
            props = feature["properties"]
            evidence_url = str(props.get("source_url", ""))
            parsed = urlparse(evidence_url)
            official = (
                parsed.scheme == "https"
                and parsed.hostname is not None
                and (
                    parsed.hostname == "gov.in"
                    or parsed.hostname.endswith(".gov.in")
                    or parsed.hostname.endswith(".nic.in")
                )
            )
            if (
                props.get("census_year") != 2011
                or not official
                or props.get("reviewer_status") != "approved"
                or not props.get("reviewed_by")
                or not props.get("reviewed_at")
            ):
                status = "UNREVIEWED_OR_WRONG_VINTAGE_SOURCE"
            else:
                status = geometry_status(feature.get("geometry"), target_by_id[tid]["geometry"])
        results.append(
            {
                "source_key": key,
                "target_ward_id": tid,
                "location_status": status,
                "evidence_url": evidence_url,
            }
        )
    return results
