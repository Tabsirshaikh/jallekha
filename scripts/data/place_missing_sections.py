"""Find coordinates for HMWSSB sections that are not placed yet (run on a computer with internet).

Why: 45 of the 197 sections with 2025 bookings have no building-weighted placement
(data/derived/crosswalk/section_ward_building_weights.csv), so they get no area or need on the U5
map. 19 of them were found by the old Nominatim search but rejected by its rules, and 28 returned
nothing because of spelling (Chanukyapuri -> Chanakyapuri, Deepthisri -> Deepthi Sri, ...) or were
never searched (names that appeared in 2025 only).

What this does, for each unplaced section:
1. builds spelling variants (a manual alias list plus automatic rules);
2. asks Nominatim (text search, Hyderabad box) and Overpass (OSM place nodes with those names);
3. keeps every candidate and measures its distance from the median position of the already
   placed sections of the same HMWSSB division (the division check of build_section_wards.py);
4. marks ACCEPT only when exactly one place is plausible, otherwise AMBIGUOUS / REVIEW /
   NOT_FOUND. A person looks at the table before anything is used.

It writes NEW files only and changes nothing existing:
- data/raw/geography/nominatim/missing_sections_search.json   (raw answers, as received)
- data/raw/geography/overpass/missing_sections_places.json    (raw answer, as received)
- data/derived/crosswalk/section_placement_candidates.csv     (every candidate)
- data/derived/crosswalk/section_placement_best.csv           (one row per section, for review)

Usage (repo root, internet needed, Nominatim policy: one request per second):
    python scripts/data/place_missing_sections.py                 # all unplaced sections
    python scripts/data/place_missing_sections.py --dry-run       # no network: targets + variants
    python scripts/data/place_missing_sections.py --only "Bachupally"
    python scripts/data/place_missing_sections.py --no-overpass

Basis: DERIVED (OpenStreetMap as mapped); the accept rule is ASSUMED. A point is where a place is
named on the map, not a service area.
"""

# ruff: noqa: E501
from __future__ import annotations

import argparse
import csv
import json
import math
import re
import statistics
import sys
import time
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[2]
CHECKS = "data/derived/underserved/section_checks.csv"
WEIGHTS = "data/derived/crosswalk/section_ward_building_weights.csv"
PLACED = "data/derived/crosswalk/section_to_ward_2016.csv"
RAW_NOMINATIM = "data/raw/geography/nominatim/missing_sections_search.json"
RAW_OVERPASS = "data/raw/geography/overpass/missing_sections_places.json"
OUT_ALL = "data/derived/crosswalk/section_placement_candidates.csv"
OUT_BEST = "data/derived/crosswalk/section_placement_best.csv"

NOMINATIM = "https://nominatim.openstreetmap.org/search"
OVERPASS = "https://overpass-api.de/api/interpreter"
HEADERS = {"User-Agent": "JalLekha-data/1.0 (github.com/Tabsirshaikh/jallekha)"}
# Wider than GHMC: the peripheral divisions (PD) lie outside the city wards. west, north, east, south
VIEWBOX = "78.00,17.80,78.80,17.00"
BBOX = (17.00, 78.00, 17.80, 78.80)  # south, west, north, east (Overpass order)
PLACE_CLASSES = "suburb|neighbourhood|quarter|locality|village|hamlet|town|city_block"

# ASSUMED: a candidate is plausible when it is within this many km of its division's centre, or
# within SPREAD_FACTOR x the division's own median spread, whichever is larger.
MIN_KM = 6.0
SPREAD_FACTOR = 3.0
# ASSUMED: two plausible candidates closer than this are the same place.
SAME_PLACE_KM = 1.5

# Spellings to try, by cleaned lower-case section name. Checked by hand against the HMWSSB names.
ALIASES: dict[str, list[str]] = {
    "chanukyapuri": ["Chanakyapuri", "Chanakya Puri"],
    "deepthisri nagar": [
        "Deepthi Sri Nagar",
        "Deepthisri Nagar",
        "Deepthi Sree Nagar",
        "Deepthisree Nagar",
    ],
    "shapoornagar": ["Shapur Nagar", "Shapoor Nagar", "Shapurnagar"],
    "maruthinagar": ["Maruthi Nagar", "Maruti Nagar"],
    "vaishalinagar": ["Vaishali Nagar", "Vaisali Nagar"],
    "vajpayee nagar": ["Vajpayee Nagar", "Vajpai Nagar", "Atal Bihari Vajpayee Nagar"],
    "boats club": ["Boat Club", "Boats Club"],
    "asmangarh": ["Asmangadh", "Asman Garh", "Asmangarh"],
    "hussainsagar": ["Hussain Sagar", "Hussainsagar"],
    "gode ki kabar": ["Gode Ki Kabar", "Godekikhabar", "Gode Ki Khabar"],
    "tappa chabutra": ["Tappachabutra", "Tappa Chabutra", "Tappachabutara"],
    "adarshnagar": ["Adarsh Nagar", "Adarshnagar"],
    "bhagatsingh nagar": ["Bhagat Singh Nagar", "Bhagatsingh Nagar"],
    "jagathgirigutta": ["Jagadgirigutta", "Jagathgiri Gutta", "Jagadgiri Gutta"],
    "suchitra": ["Suchitra", "Suchitra Junction", "Suchitra Circle"],
    "father balaiahnagar": ["Father Balaiah Nagar", "Father Balaiah Nagar Colony"],
    "doyens section": ["Doyens Township", "Doyen's Township", "Doyens"],
    "thattikhana": ["Thattikhana", "Thatti Khana", "Thattikhana Mahalla", "Thattiannaram"],
    "vigyanpuri": ["Vigyanpuri", "Vignanpuri", "Vignan Puri", "Vigyan Puri"],
    "hindi nagar": ["Hindi Nagar", "Hindinagar"],
    "m r g filters": ["MRG Filters", "Mir Alam Filter Beds", "Mir Alam Filters"],
    "misrigunj": ["Misrigunj", "Misri Ganj", "Misrigunj Hyderabad"],
    "chanudlal bharadari": ["Chandulal Baradari", "Chandulal Bharadari", "Chanudlal Baradari"],
    "peerjadiguda": ["Peerzadiguda", "Peerzadiguda Medipally", "Pirzadiguda"],
    "bachupally": ["Bachupally", "Bachupalli", "Bachupally Hyderabad"],
    "yakatpura": ["Yakutpura", "Yakatpura"],
    "mysaram": ["Mysaram", "Maisaram", "Mysarm"],
    "nagaram": ["Nagaram", "Nagaram Keesara"],
    "thoomkunta": ["Thumkunta", "Thoomkunta"],
    "turkayamjal": ["Turkayamjal", "Thurkayamjal"],
    "gundlapochampally": ["Gundlapochampally", "Gundla Pochampally", "Gundlapochampalli"],
    "adibatla": ["Adibatla", "Adibatla Hyderabad"],
    "cheng icherla": ["Cherlapally", "Chengicherla"],
}
# Localities HMWSSB shutdown notices list under each O&M division (as reported by The News Minute
# and Siasat, read from search summaries on 2026-10-06; the pages themselves were not opened).
# Used only as a cross-check column. Basis: REAL as reported, incomplete.
LISTED_IN_NOTICES: dict[str, set[str]] = {
    "12": {
        "chintal",
        "suchitra",
        "jeedimetla",
        "shapoor nagar",
        "shapur nagar",
        "gajularamaram",
        "suraram",
        "adarsh nagar",
        "bhagat singh nagar",
        "jagadgirigutta",
    },
    "13": {
        "alwal",
        "father balaiah nagar",
        "venkatapuram",
        "machabollaram",
        "defence colony",
        "vajpayee nagar",
        "yapral",
        "chanakyapuri",
        "gautam nagar",
        "sainathapuram",
    },
    "22": {"nizampet", "bachupally", "pragati nagar", "gandi maisamma", "tellapur", "bolla"},
}


def rows(path: str) -> list[dict[str, str]]:
    with (ROOT / path).open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def clean(section: str) -> str:
    """'KONDAPUR (DIV 15)' -> 'Kondapur' (same rule as fetch_section_geocodes.clean_name)."""
    name = re.sub(r"\s*\(.*$", "", section)
    name = re.sub(r"\s+DMA-?\d+$", "", name)
    name = re.sub(r"[.\-]", " ", name)
    return re.sub(r"\s+", " ", name).strip().title()


def variants(name: str) -> list[str]:
    key = name.lower()
    found = [name, *ALIASES.get(key, [])]
    spaced = re.sub(r"(?i)(nagar|colony|puri|guda|gutta|pally|palli|pet)$", r" \1", name).replace(
        "  ", " "
    )
    found.append(spaced.title())
    for old, new in (("oo", "u"), ("ee", "i"), ("th", "t"), ("ph", "f"), ("aa", "a")):
        if old in key:
            found.append(re.sub(old, new, key).title())
    seen: set[str] = set()
    return [v for v in found if not (v.lower() in seen or seen.add(v.lower()))][:10]


def km(a: tuple[float, float], b: tuple[float, float]) -> float:
    p1, p2 = math.radians(a[0]), math.radians(b[0])
    dp, dl = p2 - p1, math.radians(b[1] - a[1])
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 12742.0 * math.asin(math.sqrt(h))


def targets(only: str | None) -> list[dict]:
    placed_sections = {r["section"] for r in rows(WEIGHTS)}
    out = []
    for r in rows(CHECKS):
        if r["section"] in placed_sections:
            continue
        if only and only.lower() not in r["section"].lower():
            continue
        out.append(
            {
                "section": r["section"],
                "division": r["division"],
                "bookings": int(float(r["bookings"])),
            }
        )
    return sorted(out, key=lambda t: -t["bookings"])


def division_centres() -> dict[str, tuple[float, float, float]]:
    """Median lat, lng and median distance to it, of the located sections of each division."""
    points = defaultdict(list)
    for r in rows(PLACED):
        if r["status"] == "MAPPED" and r["lat"] and r["lng"]:
            points[r["division"]].append((float(r["lat"]), float(r["lng"])))
    out = {}
    for division, pts in points.items():
        centre = (statistics.median(p[0] for p in pts), statistics.median(p[1] for p in pts))
        spread = statistics.median(km(centre, p) for p in pts) if len(pts) > 1 else MIN_KM
        out[division] = (centre[0], centre[1], spread)
    return out


def get(url: str, data: bytes | None = None) -> bytes:
    for attempt in range(1, 5):
        try:
            request = urllib.request.Request(url, data=data, headers=HEADERS)
            with urllib.request.urlopen(request, timeout=90) as response:
                return response.read()
        except OSError as error:
            print(f"  retry {attempt}: {url[:90]} ({error})", flush=True)
            time.sleep(5 * attempt)
    raise RuntimeError(f"Request failed: {url[:120]}")


def nominatim(query: str) -> tuple[str, list[dict]]:
    params = {
        "q": query, "format": "jsonv2", "limit": 5, "viewbox": VIEWBOX, "bounded": 1,
        "countrycodes": "in", "addressdetails": 1,
    }  # fmt: skip
    url = f"{NOMINATIM}?{urllib.parse.urlencode(params)}"
    return url, json.loads(get(url).decode("utf-8"))


def overpass(names: list[str]) -> dict:
    pattern = "|".join(sorted({re.escape(n) for n in names}, key=str.lower))
    s, w, n, e = BBOX
    query = (
        f'[out:json][timeout:90];(node["place"~"^({PLACE_CLASSES})$"]["name"~"^({pattern})$",i]'
        f'({s},{w},{n},{e});way["place"~"^({PLACE_CLASSES})$"]["name"~"^({pattern})$",i]'
        f"({s},{w},{n},{e}););out center;"
    )
    return json.loads(
        get(OVERPASS, urllib.parse.urlencode({"data": query}).encode()).decode("utf-8")
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument(
        "--dry-run", action="store_true", help="no network: show targets and variants"
    )
    parser.add_argument("--only", help="only sections whose name contains this text")
    parser.add_argument("--no-overpass", action="store_true")
    args = parser.parse_args()

    todo = targets(args.only)
    centres = division_centres()
    print(f"{len(todo)} unplaced sections; {sum(t['bookings'] for t in todo):,} bookings in 2025")
    plan = {t["section"]: variants(clean(t["section"])) for t in todo}
    if args.dry_run:
        for t in todo:
            c = centres.get(t["division"])
            where = (
                f"centre {c[0]:.3f},{c[1]:.3f} spread {c[2]:.1f} km"
                if c
                else "no placed section in division"
            )
            print(
                f"{t['section']:34} div {t['division']:>4} {t['bookings']:>7}  {where}\n    {plan[t['section']]}"
            )
        return 0

    stamp = datetime.now(UTC).replace(microsecond=0).isoformat()
    raw_n, candidates = [], []
    for i, t in enumerate(todo, 1):
        for variant in plan[t["section"]]:
            url, answer = nominatim(f"{variant}, Hyderabad, Telangana")
            raw_n.append(
                {"section": t["section"], "variant": variant, "url": url, "results": answer}
            )
            for a in answer:
                candidates.append((t, variant, "nominatim", float(a["lat"]), float(a["lon"]),
                                   a.get("category") or a.get("class", ""), a.get("type", ""),
                                   a.get("display_name", ""), f"{a.get('osm_type')}/{a.get('osm_id')}"))  # fmt: skip
            time.sleep(1.1)
        print(f"  {i}/{len(todo)} {t['section']}", flush=True)
    raw_o: dict = {}
    if not args.no_overpass:
        names = sorted({v for vs in plan.values() for v in vs})
        raw_o = overpass(names)
        by_name = defaultdict(list)
        for section, vs in plan.items():
            for v in vs:
                by_name[v.lower()].append(section)
        for el in raw_o.get("elements", []):
            name = el.get("tags", {}).get("name", "")
            lat = el.get("lat") or el.get("center", {}).get("lat")
            lon = el.get("lon") or el.get("center", {}).get("lon")
            for section in by_name.get(name.lower(), []):
                t = next(x for x in todo if x["section"] == section)
                candidates.append((t, name, "overpass", float(lat), float(lon), "place",
                                   el["tags"].get("place", ""), name, f"{el['type']}/{el['id']}"))  # fmt: skip

    for path, payload in ((RAW_NOMINATIM, {"retrieved_at_utc": stamp, "queries": raw_n}),
                          (RAW_OVERPASS, {"retrieved_at_utc": stamp, **raw_o})):  # fmt: skip
        if payload.get("queries") or raw_o:
            (ROOT / path).parent.mkdir(parents=True, exist_ok=True)
            (ROOT / path).write_text(
                json.dumps(payload, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
            )

    listed = {d: names for d, names in LISTED_IN_NOTICES.items()}
    cand_rows = []
    for t, variant, source, lat, lon, cls, typ, label, ref in candidates:
        c = centres.get(t["division"])
        dist = km(c[:2], (lat, lon)) if c else None
        limit = max(MIN_KM, SPREAD_FACTOR * c[2]) if c else None
        inside = BBOX[0] <= lat <= BBOX[2] and BBOX[1] <= lon <= BBOX[3]
        cand_rows.append({
            "section": t["section"], "division": t["division"], "bookings_2025": t["bookings"],
            "variant": variant, "source": source, "lat": round(lat, 6), "lng": round(lon, 6),
            "osm_ref": ref, "osm_class": cls, "osm_type": typ, "label": label[:120],
            "km_to_division_centre": "" if dist is None else round(dist, 2),
            "division_limit_km": "" if limit is None else round(limit, 2),
            "plausible": bool(inside and (dist is None or dist <= limit)),
            "listed_in_notice_for_division": variant.lower() in listed.get(t["division"], set()),
        })  # fmt: skip
    best_rows = []
    for t in todo:
        mine = [r for r in cand_rows if r["section"] == t["section"]]
        ok = [r for r in mine if r["plausible"]]
        ok.sort(key=lambda r: (r["source"] != "overpass", r["osm_class"] not in ("place", "boundary"),
                               r["km_to_division_centre"] or 0))  # fmt: skip
        if not mine:
            status, pick = "NOT_FOUND", None
        elif not ok:
            status, pick = (
                "REVIEW_FAR_FROM_DIVISION",
                min(mine, key=lambda r: r["km_to_division_centre"] or 1e9),
            )
        elif all(
            km((ok[0]["lat"], ok[0]["lng"]), (r["lat"], r["lng"])) <= SAME_PLACE_KM for r in ok
        ):
            status, pick = "ACCEPT", ok[0]
        else:
            status, pick = "AMBIGUOUS", ok[0]
        best_rows.append({
            "section": t["section"], "division": t["division"], "bookings_2025": t["bookings"],
            "status": status, "candidates": len(mine), "plausible_candidates": len(ok),
            "lat": "" if pick is None else pick["lat"], "lng": "" if pick is None else pick["lng"],
            "variant": "" if pick is None else pick["variant"], "source": "" if pick is None else pick["source"],
            "km_to_division_centre": "" if pick is None else pick["km_to_division_centre"],
            "listed_in_notice_for_division": bool(pick and pick["listed_in_notice_for_division"]),
            "basis": "DERIVED", "rule_basis": "ASSUMED",
        })  # fmt: skip
    for path, data in ((OUT_ALL, cand_rows), (OUT_BEST, best_rows)):
        if not data:
            continue
        with (ROOT / path).open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(data[0]), lineterminator="\n")
            writer.writeheader()
            writer.writerows(data)
    print(
        "\nstatus counts:",
        {
            s: sum(1 for r in best_rows if r["status"] == s)
            for s in ("ACCEPT", "AMBIGUOUS", "REVIEW_FAR_FROM_DIVISION", "NOT_FOUND")
        },
    )
    print(
        "bookings covered by ACCEPT:",
        sum(r["bookings_2025"] for r in best_rows if r["status"] == "ACCEPT"),
    )
    print(f"wrote {OUT_BEST} and {OUT_ALL}; look at the table before using any point")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
