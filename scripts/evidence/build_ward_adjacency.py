"""Ward adjacency graph for the E5 BYM2 models (F4), on the historical GHMC_2016_150 layer.

Usage:
    python scripts/evidence/build_ward_adjacency.py

Two wards are neighbours when they share at least MIN_SHARED_M of border. Borders are compared in
UTM zone 44N (metres) with a SNAP_M tolerance, because the DataMeet polygons have small gaps and
overlaps between wards. Corner touches (shorter than MIN_SHARED_M) do not count (rook-style
contiguity). Both values are ASSUMED engineering choices and are written into the output.

Outputs:
- data/derived/underserved/ward_adjacency.json: edges with shared border length, the settings,
  per-ward neighbour counts, components and wards with no neighbour;
- data/derived/underserved/ward_adjacency_review.png: map of wards and edges for the reviewer.

BYM2 refuses to run until data/derived/underserved/ward_adjacency_review.json records a named
reviewer and the SHA-256 of ward_adjacency.json (see services/underserved_models.py).
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

from pyproj import Transformer
from shapely.geometry import shape
from shapely.ops import transform

ROOT = Path(__file__).resolve().parents[2]
WARDS = "data/raw/geography/datameet/ghmc-wards.geojson"
OUTPUT = "data/derived/underserved/ward_adjacency.json"
FIGURE = "data/derived/underserved/ward_adjacency_review.png"
REVIEW = "data/derived/underserved/ward_adjacency_review.json"
GEOGRAPHY_VERSION = "GHMC_2016_150"
SNAP_M = 10.0  # tolerance for digitising gaps between neighbouring polygons. Basis: ASSUMED.
MIN_SHARED_M = 50.0  # shorter shared borders are corner touches. Basis: ASSUMED.


def load_wards(root: Path) -> dict[str, tuple[str, object]]:
    features = json.loads((root / WARDS).read_text(encoding="utf-8-sig"))["features"]
    to_utm = Transformer.from_crs("EPSG:4326", "EPSG:32644", always_xy=True).transform
    return {
        f["properties"]["@id"]: (f["properties"]["name"], transform(to_utm, shape(f["geometry"])))
        for f in features
    }


def components(ids: list[str], edges: list[tuple[str, str]]) -> list[list[str]]:
    neighbours: dict[str, set[str]] = {i: set() for i in ids}
    for a, b in edges:
        neighbours[a].add(b)
        neighbours[b].add(a)
    seen: set[str] = set()
    out = []
    for start in ids:
        if start in seen:
            continue
        stack, part = [start], []
        while stack:
            node = stack.pop()
            if node in seen:
                continue
            seen.add(node)
            part.append(node)
            stack.extend(neighbours[node] - seen)
        out.append(sorted(part))
    return sorted(out, key=lambda c: (-len(c), c))


def build(root: Path = ROOT) -> dict:
    wards = load_wards(root)
    ids = sorted(wards)
    edges = []
    for i, a in enumerate(ids):
        geom_a = wards[a][1]
        reach = geom_a.buffer(SNAP_M)
        for b in ids[i + 1 :]:
            geom_b = wards[b][1]
            if not reach.intersects(geom_b):
                continue
            shared = geom_a.boundary.intersection(geom_b.buffer(SNAP_M)).length
            if shared >= MIN_SHARED_M:
                edges.append({"a": a, "b": b, "shared_border_m": round(shared, 1)})
    pairs = [(e["a"], e["b"]) for e in edges]
    degree = {i: 0 for i in ids}
    for a, b in pairs:
        degree[a] += 1
        degree[b] += 1
    parts = components(ids, pairs)
    return {
        "geography_version": GEOGRAPHY_VERSION,
        "source": WARDS,
        "source_sha256": hashlib.sha256((root / WARDS).read_bytes()).hexdigest(),
        "method": (
            f"rook-style contiguity: shared border >= {MIN_SHARED_M:g} m after a "
            f"{SNAP_M:g} m snap tolerance, in UTM 44N (EPSG:32644)"
        ),
        "snap_m": SNAP_M,
        "min_shared_border_m": MIN_SHARED_M,
        "basis": "DERIVED (geometry); thresholds ASSUMED",
        "ward_count": len(ids),
        "edge_count": len(edges),
        "edges": edges,
        "neighbour_count": {i: degree[i] for i in ids},
        "ward_names": {i: wards[i][0] for i in ids},
        "components": parts,
        "wards_without_neighbours": [i for i in ids if degree[i] == 0],
    }


def figure(root: Path, graph: dict) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    wards = load_wards(root)
    centre = {i: g.representative_point() for i, (_, g) in wards.items()}
    fig, ax = plt.subplots(figsize=(14, 14), dpi=110)
    for _, geom in wards.values():
        for poly in getattr(geom, "geoms", [geom]):
            x, y = poly.exterior.xy
            ax.fill(x, y, facecolor="#eef3f8", edgecolor="#7a8a99", linewidth=0.6)
    for e in graph["edges"]:
        a, b = centre[e["a"]], centre[e["b"]]
        ax.plot([a.x, b.x], [a.y, b.y], color="#c0392b", linewidth=0.8)
    lonely = set(graph["wards_without_neighbours"])
    for i, point in centre.items():
        name = wards[i][0].replace("Ward ", "")
        ax.plot(point.x, point.y, "o", ms=3, color="#000" if i not in lonely else "#e67e22")
        ax.annotate(name, (point.x, point.y), fontsize=4.5, ha="center", va="bottom")
    ax.set_title(
        f"E5 ward adjacency for review: {graph['ward_count']} wards, {graph['edge_count']} edges, "
        f"{len(graph['components'])} component(s); orange = no neighbour"
    )
    ax.set_aspect("equal")
    ax.axis("off")
    fig.tight_layout()
    fig.savefig(root / FIGURE)
    plt.close(fig)


if __name__ == "__main__":
    graph = build()
    path = ROOT / OUTPUT
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(graph, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    figure(ROOT, graph)
    print(
        f"{graph['edge_count']} edges, {len(graph['components'])} component(s), "
        f"{len(graph['wards_without_neighbours'])} ward(s) without neighbours"
    )
    sys.exit(0)
