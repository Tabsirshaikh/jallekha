"""Fetch D7: monthly groundwater levels of the Telangana Ground Water Department's wells (REAL).

Source: Open Data Telangana, "Telangana Ground Water Department Water Level Data" (one CSV per
month from January 2021; Government Open Data License - India). The links are the `downloadURL`s
of the portal's catalogue API, as for the D8b weather files. This replaces the National Water
Data Portal route, which needs an account (NWDP_NOTE.md).

Only wells in the four districts HMWSSB sections lie in are kept (Hyderabad, Medchal-Malkajgiri,
Rangareddy, Sangareddy). Each row: the well (district, mandal, village, position), the date and
the depth to water in metres below ground level (m bgl; larger = deeper = drier). Dates are
written dd/mm/yy or dd/mm/yyyy; a date outside the file's month is left blank and counted.
Written as gzip with a fixed timestamp; each source file's SHA-256 is in RETRIEVAL_LOG.md.

    python scripts/data/fetch_d7_groundwater.py
"""

from __future__ import annotations

import csv
import gzip
import hashlib
import io
import json
import tempfile
import time
import urllib.request
from collections import Counter
from datetime import UTC, date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "data/raw/d7_groundwater"
OUT = OUT_DIR / "tggwd_levels_hmwssb_districts.csv.gz"
CATALOGUE = "https://data.telangana.gov.in/api/1/search?fulltext=ground%20water&page-size=50"
TITLE = "Telangana Ground Water Department Water Level Data"
# District names as the files write them (upper or mixed case).
DISTRICTS = {"HYDERABAD": "Hyderabad", "MEDCHAL": "Medchal-Malkajgiri",
             "MEDCHAL-MALKAJGIRI": "Medchal-Malkajgiri", "RANGAREDDY": "Rangareddy",
             "RANGA REDDY": "Rangareddy", "SANGAREDDY": "Sangareddy"}  # fmt: skip
MONTHS = {name[:3]: i for i, name in enumerate(
    ("January", "February", "March", "April", "May", "June", "July", "August", "September",
     "October", "November", "December"), start=1)}  # fmt: skip
FIELDS = ("source_month", "district", "mandal", "village", "lat", "lon", "date", "date_raw",
          "depth_m_bgl")  # fmt: skip
USER_AGENT = "jallekha-d7-fetch"
CACHE = Path(tempfile.gettempdir()) / "jallekha_d7_cache"


def _get(url: str, cache: bool = False) -> bytes:
    cached = CACHE / hashlib.sha256(url.encode()).hexdigest()
    if cache and cached.is_file():
        return cached.read_bytes()
    for attempt in range(6):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(request, timeout=180) as response:
                content = response.read()
            if cache:
                CACHE.mkdir(parents=True, exist_ok=True)
                cached.write_bytes(content)
            return content
        except OSError:
            if attempt == 5:
                raise
            time.sleep(20 * (attempt + 1))
    raise AssertionError("unreachable")


def file_month(title: str) -> tuple[int, int]:
    """'... Water Level Data January 2021' -> (2021, 1)."""
    words = title.split()
    return int(words[-1]), MONTHS[words[-2][:3]]


def parse_date(text: str, month: tuple[int, int]) -> date | None:
    for fmt in ("%d/%m/%y", "%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            parsed = datetime.strptime(text.strip(), fmt).date()
        except ValueError:
            continue
        return parsed if (parsed.year, parsed.month) == month else None
    return None


def rows_of(content: bytes, month: tuple[int, int]) -> tuple[list[dict[str, str]], Counter]:
    reader = csv.DictReader(io.StringIO(content.decode("utf-8-sig", errors="replace")))
    out, notes = [], Counter()
    for r in reader:
        r = {(k or "").strip().lower(): (v or "").strip() for k, v in r.items()}
        district = DISTRICTS.get(r.get("district", "").upper())
        if district is None:
            continue
        day = parse_date(r.get("date", ""), month)
        notes["ok" if day else "date_not_usable"] += 1
        out.append(
            {
                "source_month": f"{month[0]}-{month[1]:02d}",
                "district": district,
                "mandal": r.get("mandal", ""),
                "village": r.get("village", ""),
                "lat": r.get("lat", ""),
                "lon": r.get("long", r.get("lon", "")),
                "date": day.isoformat() if day else "",
                "date_raw": r.get("date", ""),
                "depth_m_bgl": r.get("value", ""),
            }
        )
    return out, notes


def main() -> None:
    catalogue = json.loads(_get(CATALOGUE))
    results = catalogue["results"]
    items = results.values() if isinstance(results, dict) else results
    files = sorted(
        (file_month(d["title"]), d["title"], d["downloadURL"])
        for item in items
        if item.get("title") == TITLE
        for d in item["distribution"]
    )
    rows: list[dict[str, str]] = []
    log_rows, total = [], Counter()
    for month, title, url in files:
        content = _get(url, cache=True)
        found, notes = rows_of(content, month)
        rows.extend(found)
        total.update(notes)
        log_rows.append(
            f"| {month[0]}-{month[1]:02d} | [{title}]({url}) | {len(content):,} | "
            f"`{hashlib.sha256(content).hexdigest()}` | {len(found):,} | "
            f"{notes.get('date_not_usable', 0)} |"
        )
        time.sleep(1)
    rows.sort(key=lambda r: (r["source_month"], r["district"], r["mandal"], r["village"]))
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=FIELDS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT.write_bytes(gzip.compress(stream.getvalue().encode("utf-8"), mtime=0))
    digest = hashlib.sha256(OUT.read_bytes()).hexdigest()
    first, last = files[0][0], files[-1][0]
    table = "\n".join(log_rows)
    bad = total.get("date_not_usable", 0)
    (OUT_DIR / "RETRIEVAL_LOG.md").write_text(
        f"""# D7 Groundwater levels (Telangana Ground Water Department) — Retrieval Log

**Dataset:** Open Data Telangana, "{TITLE}"
**Basis:** REAL (monthly depth to water at the department's observation wells, m below ground)
**Licence:** Government Open Data License - India
**Used by:** F6 shortage reasons (groundwater anomaly near each section); F5 candidate feature
**Note:** the National Water Data Portal route needs an account and was not used (NWDP_NOTE.md).

| Field | Value |
|---|---|
| Catalogue | `{CATALOGUE}` (each file's `downloadURL`) |
| Months | {first[0]}-{first[1]:02d} to {last[0]}-{last[1]:02d} ({len(files)} monthly files) |
| Districts kept | Hyderabad, Medchal-Malkajgiri, Rangareddy, Sangareddy |
| Rows | {len(rows):,} ({bad:,} with a date outside the file's month, left blank) |
| Retrieved | {datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")} |
| File | `{OUT.name}` (gzip, fixed timestamp) |
| SHA-256 | `{digest}` |

Values are copied as written; only the date is parsed (original text in `date_raw`).

## Source files

| Month | File | Bytes | SHA-256 | Rows kept | Dates not usable |
|---|---|---|---|---|---|
{table}
""",
        encoding="utf-8",
    )
    print(f"Wrote {OUT} ({len(rows):,} rows from {len(files)} files, sha256 {digest[:12]})")
    print(dict(total))


if __name__ == "__main__":
    main()
