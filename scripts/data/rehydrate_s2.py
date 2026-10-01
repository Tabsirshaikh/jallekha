"""Rehydrate the public raw sources available for S2 and write their manifest.

This script never transforms source bytes. It exists because the legacy research-data
archive named in the planning documents was not present in any local or remote checkout.
"""

from __future__ import annotations

import csv
import hashlib
import http.cookiejar
import json
import re
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"
VERIFICATION = ROOT / "data" / "verification"
USER_AGENT = "JalLekha-data-rehydration/1.0"


def get_bytes(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=120) as response:
        return response.read()


def get_json(url: str) -> dict:
    return json.loads(get_bytes(url))


def get_census_bytes(catalog_url: str, download_url: str) -> bytes:
    opener = urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar())
    )
    opener.open(
        urllib.request.Request(catalog_url, headers={"User-Agent": "Mozilla/5.0"}), timeout=120
    ).read()
    request = urllib.request.Request(
        download_url,
        headers={"User-Agent": "Mozilla/5.0", "Referer": catalog_url},
    )
    with opener.open(request, timeout=120) as response:
        return response.read()


def write_source(
    rows: list[dict[str, str | int]],
    *,
    dataset_id: str,
    relative_path: str,
    url: str,
    license_name: str,
    geography: str,
    granularity: str,
    notes: str,
    source_modified: str = "",
    payload: bytes | None = None,
) -> None:
    if payload is None:
        payload = get_bytes(url)
    path = ROOT / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    rows.append(
        {
            "dataset_id": dataset_id,
            "file_path": path.relative_to(ROOT).as_posix(),
            "source_url": url,
            "retrieved_at_utc": RETRIEVED_AT,
            "source_modified": source_modified,
            "license": license_name,
            "geography": geography,
            "granularity": granularity,
            "basis": "REAL",
            "sha256": hashlib.sha256(payload).hexdigest(),
            "bytes": len(payload),
            "notes": notes,
        }
    )


def tanker_slug(name: str) -> str:
    months = {
        "jan": "01",
        "feb": "02",
        "march": "03",
        "april": "04",
        "may": "05",
        "june": "06",
        "july": "07",
        "aug": "08",
        "sept": "09",
        "oct": "10",
        "nov": "11",
        "dec": "12",
    }
    match = re.search(
        r"for (Jan|Feb|March|April|May|June|July|Aug|Sept|Oct|Nov|Dec) (20\d{2})", name
    )
    if not match:
        raise ValueError(f"Cannot derive month from resource name: {name}")
    return f"{match.group(2)}-{months[match.group(1).lower()]}"


RETRIEVED_AT = datetime.now(UTC).replace(microsecond=0).isoformat()
records: list[dict[str, str | int]] = []

tanker_package = get_json(
    "https://data.opencity.in/api/3/action/package_show?id=hyderabad-water-supply-through-tankers-data"
)["result"]
for resource in tanker_package["resources"]:
    if resource.get("format", "").upper() != "CSV":
        continue
    slug = tanker_slug(resource["name"])
    write_source(
        records,
        dataset_id=f"D1-HMWSSB-{slug}",
        relative_path=f"data/raw/hmwssb_tankers/{slug}.csv",
        url=resource["url"],
        license_name=tanker_package.get("license_title") or "Not specified by portal",
        geography="HMWSSB divisions and sections, Hyderabad",
        granularity="monthly section-level bookings and delivered counts",
        notes="Exact OpenCity resource bytes; December 2022 is retained even if empty.",
        source_modified=resource.get("last_modified") or "",
    )

datameet_base = "https://raw.githubusercontent.com/datameet/Municipal_Spatial_Data/master/Hyderabad"
for filename, granularity in (
    ("Readme.md", "source documentation"),
    ("ghmc-wards.geojson", "historical municipal ward polygons"),
    ("ghmc-zones.geojson", "historical municipal zone polygons"),
):
    write_source(
        records,
        dataset_id=f"D2-DATAMEET-{filename.upper()}",
        relative_path=f"data/raw/geography/datameet/{filename}",
        url=f"{datameet_base}/{filename}",
        license_name="CC BY 4.0 (DataMeet repository default)",
        geography="Historical GHMC 2016-era municipal geography",
        granularity=granularity,
        notes="Community/OSM-derived historical geometry; not an authoritative current boundary.",
    )

census_package = get_json(
    "https://data.opencity.in/api/3/action/package_show?id=hyderabad-census-2011-data"
)["result"]
census_resources = census_package["resources"]
for resource, filename, granularity in (
    (census_resources[0], "pca.csv", "Census 2011 ward-level primary census abstract"),
    (census_resources[2], "hh14.xlsx", "Census 2011 ward-level household amenities HH-14"),
):
    write_source(
        records,
        dataset_id=f"D3-HYDERABAD-{filename.upper()}",
        relative_path=f"data/raw/census/hyderabad/{filename}",
        url=resource["url"],
        license_name=census_package.get("license_title") or "Not specified by portal",
        geography="Hyderabad district, Census 2011 geography",
        granularity=granularity,
        notes=("OpenCity Census mirror; preserve source geography before crosswalk."),
        source_modified=resource.get("last_modified") or "",
    )

for dataset_id, filename, catalog_url, url, granularity in (
    (
        "D4-RANGAREDDY-PCA",
        "pca.xlsx",
        "https://censusindia.gov.in/nada/index.php/catalog/6728",
        "https://censusindia.gov.in/nada/index.php/catalog/6728/download/9805/DDW_PCA2806_2011_MDDS%20with%20UI.xlsx",
        "Census 2011 district PCA with urban identifiers",
    ),
    (
        "D4-RANGAREDDY-HH14",
        "hh14.xlsx",
        "https://censusindia.gov.in/nada/index.php/catalog/9835",
        "https://censusindia.gov.in/nada/index.php/catalog/9835/download/12947/HLPCA-28537-2011_H14_census.xlsx",
        "Census 2011 household amenities HH-14",
    ),
):
    write_source(
        records,
        dataset_id=dataset_id,
        relative_path=f"data/raw/census/rangareddy/{filename}",
        url=url,
        license_name="Census of India official catalog; reuse terms require source attribution",
        geography="Rangareddy district, Census 2011 geography",
        granularity=granularity,
        notes="Downloaded directly from the official Census of India NADA catalog.",
        payload=get_census_bytes(catalog_url, url),
    )

VERIFICATION.mkdir(parents=True, exist_ok=True)
fields = [
    "dataset_id",
    "file_path",
    "source_url",
    "retrieved_at_utc",
    "source_modified",
    "license",
    "geography",
    "granularity",
    "basis",
    "sha256",
    "bytes",
    "notes",
]
with (VERIFICATION / "source_manifest.csv").open("w", encoding="utf-8", newline="") as handle:
    writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(records)

print(f"Wrote {len(records)} exact raw resources and source_manifest.csv")
