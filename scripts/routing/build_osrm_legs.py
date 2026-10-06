"""Road km and minutes between the sandbox points from OSRM on OpenStreetMap (item 20).

The solution document promises "OR-Tools, OSRM with cached legs" (section 7). No OSRM server
runs with the app, so the legs are computed once here and committed; the sandbox (F19) and the
planner read the committed files, never a live server, so results stay repeatable. Run by hand
(about 5 minutes), never in tests:

1. download Geofabrik's India southern-zone extract (or take --pbf) and log its size,
   Last-Modified and SHA-256;
2. crop it to the HMWSSB area (BBOX: the section points and stations plus about 11 km, so
   routes can use the Outer Ring Road) with pyosmium (`pip install osmium`; a build tool, not
   a project dependency);
3. prepare it with OSRM's car profile (osrm-extract, osrm-partition, osrm-customize: MLD);
4. start osrm-routed on localhost and ask /table for every section point and station, both
   directions (one-way streets make A to B differ from B to A);
5. write data/derived/routing/osrm_section_station.csv, osrm_station_station.csv,
   osrm_points.csv (how far OSRM moved each point to reach a road) and BUILD_LOG.md.

OSRM: release v26.10.0 prebuilt binaries (GitHub Project-OSRM/osrm-backend, asset
node_osrm-v26.10.0-8-win32-x64-Release.tar.gz or linux-x64) and profiles/car.lua of the same
tag. The car profile gives free-flow car speeds: no traffic, no tanker (truck) limits, so
minutes are optimistic; km are road km on OSM as mapped.

Usage:
    python scripts/routing/build_osrm_legs.py --osrm-bin DIR --profile DIR/car.lua \
        --work DIR [--pbf FILE]
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import subprocess
import sys
import time
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PBF_URL = "https://download.geofabrik.de/asia/india/southern-zone-latest.osm.pbf"
OSRM_RELEASE = "v26.10.0"
# min lng, min lat, max lng, max lat: points span 78.243-78.602 E, 17.303-17.546 N.
BBOX = (78.10, 17.15, 78.75, 17.70)
PORT = 5005
SECTIONS = "data/derived/sandbox/section_points.csv"
STATIONS = "data/derived/sandbox/stations.csv"
OUT_DIR = "data/derived/routing"
SECTION_STATION = f"{OUT_DIR}/osrm_section_station.csv"
STATION_STATION = f"{OUT_DIR}/osrm_station_station.csv"
POINTS = f"{OUT_DIR}/osrm_points.csv"
LOG = f"{OUT_DIR}/BUILD_LOG.md"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def download(work: Path) -> tuple[Path, str]:
    target = work / "southern-zone-latest.osm.pbf"
    with urllib.request.urlopen(PBF_URL, timeout=600) as resp, target.open("wb") as out:
        modified = resp.headers.get("Last-Modified", "")
        while block := resp.read(1 << 20):
            out.write(block)
    return target, modified


def crop(src: Path, dst: Path) -> dict[str, int]:
    """Highways with at least one node in BBOX, all their nodes, and turn restrictions."""
    import osmium  # build tool only

    west, south, east, north = BBOX
    inside = osmium.index.IdSet()
    for node in osmium.FileProcessor(str(src), osmium.osm.NODE):
        loc = node.location
        if west <= loc.lon <= east and south <= loc.lat <= north:
            inside.set(node.id)
    keep = osmium.IdTracker()
    ways = 0
    for way in osmium.FileProcessor(str(src), osmium.osm.WAY).with_filter(
        osmium.filter.KeyFilter("highway")
    ):
        if any(inside.get(ref.ref) for ref in way.nodes):
            keep.add_way(way.id)
            ways += 1
    restrictions = 0
    way_ids = keep.way_ids()
    for rel in osmium.FileProcessor(str(src), osmium.osm.RELATION).with_filter(
        osmium.filter.TagFilter(("type", "restriction"))
    ):
        members = [m for m in rel.members if m.type == "w"]
        if members and all(way_ids.get(m.ref) for m in members):
            keep.add_relation(rel.id)
            restrictions += 1
    keep.complete_backward_references(str(src), relation_depth=0)
    with osmium.SimpleWriter(str(dst), overwrite=True) as writer:
        for obj in osmium.FileProcessor(str(src)).with_filter(keep.id_filter()):
            writer.add(obj)
    return {"ways": ways, "restrictions": restrictions}


def prepare(osrm_bin: Path, profile: Path, pbf: Path) -> Path:
    def tool(name: str) -> str:
        exe = osrm_bin / (name + (".exe" if sys.platform == "win32" else ""))
        return str(exe)

    subprocess.run([tool("osrm-extract"), "-p", str(profile), str(pbf)], check=True)
    base = pbf.with_suffix("").with_suffix(".osrm")
    subprocess.run([tool("osrm-partition"), str(base)], check=True)
    subprocess.run([tool("osrm-customize"), str(base)], check=True)
    return base


def serve(osrm_bin: Path, base: Path) -> subprocess.Popen:
    exe = osrm_bin / ("osrm-routed" + (".exe" if sys.platform == "win32" else ""))
    proc = subprocess.Popen(
        [str(exe), "--algorithm", "mld", "--max-table-size", "1000", "-p", str(PORT), str(base)]
    )
    for _ in range(120):
        try:
            with urllib.request.urlopen(
                f"http://127.0.0.1:{PORT}/nearest/v1/driving/78.4867,17.385", timeout=2
            ) as resp:
                if json.loads(resp.read()).get("code") == "Ok":
                    return proc
        except OSError:
            time.sleep(1)
    proc.kill()
    raise RuntimeError("osrm-routed did not start")


def table(points: list[tuple[float, float]]) -> dict:
    """Full table: distances (m) and durations (s) between every pair, by row (from) and column."""
    coords = ";".join(f"{lng:.6f},{lat:.6f}" for lat, lng in points)
    url = f"http://127.0.0.1:{PORT}/table/v1/driving/{coords}?annotations=distance,duration"
    with urllib.request.urlopen(url, timeout=300) as resp:
        data = json.loads(resp.read())
    if data.get("code") != "Ok":
        raise RuntimeError(f"OSRM table failed: {data.get('code')} {data.get('message')}")
    return data


def _csv(rows: list[dict]) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode()


def _km(metres: float | None) -> str:
    return "" if metres is None else f"{metres / 1000:.3f}"


def _min(seconds: float | None) -> str:
    return "" if seconds is None else f"{seconds / 60:.2f}"


def legs(data: dict, sections: list[dict], stations: list[dict]) -> dict[str, bytes]:
    n = len(sections)
    dist, dur = data["distances"], data["durations"]
    section_station = [
        {
            "section": sec["section"],
            "station_id": st["station_id"],
            "out_km": _km(dist[n + j][i]),  # station to section
            "out_min": _min(dur[n + j][i]),
            "back_km": _km(dist[i][n + j]),  # section to station
            "back_min": _min(dur[i][n + j]),
        }
        for i, sec in enumerate(sections)
        for j, st in enumerate(stations)
    ]
    station_station = [
        {
            "station_a": a["station_id"],
            "station_b": b["station_id"],
            "ab_km": _km(dist[n + i][n + j]),
            "ab_min": _min(dur[n + i][n + j]),
            "ba_km": _km(dist[n + j][n + i]),
            "ba_min": _min(dur[n + j][n + i]),
        }
        for i, a in enumerate(stations)
        for j, b in enumerate(stations)
        if i < j
    ]
    points = [
        {
            "kind": kind,
            "id": p.get("section") or p.get("station_id"),
            "lat": p["lat"],
            "lng": p["lng"],
            "snap_m": f"{src['distance']:.1f}",
        }
        for (kind, p), src in zip(
            [("section", s) for s in sections] + [("station", s) for s in stations],
            data["sources"],
            strict=True,
        )
    ]
    return {
        SECTION_STATION: _csv(section_station),
        STATION_STATION: _csv(station_station),
        POINTS: _csv(points),
    }


def read_points(root: Path) -> tuple[list[dict], list[dict]]:
    with (root / SECTIONS).open(encoding="utf-8", newline="") as handle:
        sections = [r for r in csv.DictReader(handle) if r["lat"]]
    with (root / STATIONS).open(encoding="utf-8", newline="") as handle:
        stations = list(csv.DictReader(handle))
    return sections, stations


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--osrm-bin", type=Path, required=True)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--pbf", type=Path, default=None)
    parser.add_argument("--last-modified", default="", help="when --pbf is given")
    args = parser.parse_args(argv)
    args.work.mkdir(parents=True, exist_ok=True)

    if args.pbf is None:
        pbf, modified = download(args.work)
    else:
        pbf, modified = args.pbf, args.last_modified
    source = {"size": pbf.stat().st_size, "sha256": sha256(pbf), "modified": modified}
    cropped = args.work / "hyderabad.osm.pbf"
    counts = crop(pbf, cropped)
    base = prepare(args.osrm_bin, args.profile, cropped)

    sections, stations = read_points(ROOT)
    points = [(float(p["lat"]), float(p["lng"])) for p in sections + stations]
    proc = serve(args.osrm_bin, base)
    try:
        data = table(points)
    finally:
        proc.terminate()
        proc.wait(timeout=30)

    artifacts = legs(data, sections, stations)
    missing = sum(row.count(None) for row in data["distances"])
    snaps = sorted(s["distance"] for s in data["sources"])
    inputs = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in
              (SECTIONS, STATIONS)}  # fmt: skip
    crop_note = f"{counts['ways']:,} highways, {counts['restrictions']:,} turn restrictions"
    snap_note = (
        f"median {snaps[len(snaps) // 2]:.1f}, 90th percentile "
        f"{snaps[int(len(snaps) * 0.9)]:.1f}, max {snaps[-1]:.1f}"
    )
    log = f"""# OSRM road legs: build log

Built {datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")} by `scripts/routing/build_osrm_legs.py`.

| Item | Value |
|---|---|
| Map | [{PBF_URL}]({PBF_URL}), Last-Modified {source["modified"] or "not given"} |
| Map size, SHA-256 | {source["size"]:,} bytes, `{source["sha256"]}` |
| Licence | OpenStreetMap contributors, ODbL 1.0 |
| Crop | bbox {BBOX} (lng/lat): {crop_note} |
| Router | OSRM {OSRM_RELEASE} prebuilt binaries, `profiles/car.lua` of the same tag, MLD |
| Points | {len(sections)} section points, {len(stations)} stations ({SECTIONS}, {STATIONS}) |
| Input SHA-256 | {", ".join(f"`{k}` `{v[:16]}...`" for k, v in inputs.items())} |
| Pairs with no route | {missing} |
| Snap to road (m) | {snap_note} |

Basis: DERIVED (OSRM shortest-time car route on OSM roads as mapped). Free-flow car speeds:
no traffic and no tanker (truck) limits, so minutes are optimistic. Points are the sandbox's
section points and ASSUMED stand-in stations, so the legs are road distances between assumed
places, not HMWSSB's real station-to-household trips.
"""
    artifacts[LOG] = log.encode()
    for name, content in artifacts.items():
        path = ROOT / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    print(f"OSRM legs written: {len(sections)} sections x {len(stations)} stations.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
