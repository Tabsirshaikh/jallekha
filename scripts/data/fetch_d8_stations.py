"""Fetch D8b: daily weather per mandal from the Telangana automatic weather stations (TGDPS).

Source: Open Data Telangana, "Telangana Weather Data from 2018 - 2022" and "... 2023 - 2026"
(Telangana State Development Planning Society; Government Open Data License - India). One CSV per
month; the download links are the `downloadURL`s the portal's own catalogue API publishes
(https://data.telangana.gov.in/api/1/search?fulltext=weather).

Only the four districts HMWSSB sections lie in are kept (Hyderabad, Medchal-Malkajgiri,
Rangareddy, Sangareddy). The two series use different layouts; both are written to one CSV with
the original date text beside the parsed date. The 2023-2026 files write days 1-12 with day and
month swapped ("01-Apr-23" in the January 2023 file is 4 January): the file's own month decides,
and every corrected date is flagged. Each source file's SHA-256 is in RETRIEVAL_LOG.md.

    python scripts/data/fetch_d8_stations.py
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
OUT_DIR = ROOT / "data/raw/d8_weather_stations"
# gzip with a fixed timestamp: about 3 MB instead of 21 MB, and the same bytes on a re-run.
OUT = OUT_DIR / "tgdps_daily_hmwssb_districts.csv.gz"
CATALOGUE = "https://data.telangana.gov.in/api/1/search?fulltext=weather&page-size=50"
DATASETS = {
    "60fb90f9-cc37-4c6a-a160-cb76c711698f": "Telangana Weather Data from 2018 - 2022",
    "d0cdc94a-01c4-45fc-8b67-c61ba78dc58d": "Telangana Weather Data from 2023 - 2026",
}
DISTRICTS = {"Hyderabad", "Medchal-Malkajgiri", "Rangareddy", "Sangareddy"}
MONTHS = {name: i for i, name in enumerate(
    ("January", "February", "March", "April", "May", "June", "July", "August", "September",
     "October", "November", "December"), start=1)}  # fmt: skip
FIELDS = ("source_month", "district", "mandal", "station", "date", "date_raw", "date_note",
          "rain_mm", "tmin_c", "tmax_c")  # fmt: skip
USER_AGENT = "jallekha-d8b-fetch"


# Downloaded months are kept here (outside the repo) so a network drop does not restart the run.
CACHE = Path(tempfile.gettempdir()) / "jallekha_d8b_cache"


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
    """'TS Weather data January 2023' -> (2023, 1)."""
    words = title.split()
    # Match on the first three letters: one title is spelled "Janaury".
    by_prefix = {name[:3]: number for name, number in MONTHS.items()}
    return int(words[-1]), by_prefix[words[-2][:3]]


def _column(header: list[str], *keys: str) -> str:
    for name in header:
        low = name.lower()
        if all(k in low for k in keys):
            return name
    raise KeyError(f"no column with {keys} in {header}")


def parse_date(text: str, month: tuple[int, int]) -> tuple[date | None, str]:
    """The date of a row in the file for `month`, and a note when it was corrected or failed."""
    text = text.strip()
    for fmt in ("%Y-%m-%d", "%d-%b-%y", "%d-%m-%Y", "%d/%m/%Y"):
        try:
            parsed = datetime.strptime(text, fmt).date()
            break
        except ValueError:
            continue
    else:
        return None, "unparsed"
    year, number = month
    if (parsed.year, parsed.month) == month:
        return parsed, ""
    # Days 1-12 written with day and month swapped: the "day" is the file's month.
    if parsed.year == year and parsed.day == number:
        return date(year, number, parsed.month), "day_month_swapped"
    return None, "outside_file_month"


def rows_of(content: bytes, month: tuple[int, int]) -> tuple[list[dict[str, str]], Counter]:
    text = content.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    header = reader.fieldnames or []
    col = {
        "district": _column(header, "district"),
        "mandal": _column(header, "mandal"),
        "date": _column(header, "date"),
        "rain": _column(header, "rain"),
        "tmin": next(h for h in header if "min" in h.lower() and "temp" in h.lower()),
        "tmax": next(h for h in header if "max" in h.lower() and "temp" in h.lower()),
    }
    station = next((h for h in header if h.lower() == "location"), None)
    out, notes = [], Counter()
    for r in reader:
        district = (r[col["district"]] or "").strip()
        if district not in DISTRICTS:
            continue
        day, note = parse_date(r[col["date"]] or "", month)
        notes[note or "ok"] += 1
        out.append(
            {
                "source_month": f"{month[0]}-{month[1]:02d}",
                "district": district,
                "mandal": (r[col["mandal"]] or "").strip(),
                "station": (r[station] or "").strip() if station else "",
                "date": day.isoformat() if day else "",
                "date_raw": (r[col["date"]] or "").strip(),
                "date_note": note,
                "rain_mm": (r[col["rain"]] or "").strip(),
                "tmin_c": (r[col["tmin"]] or "").strip(),
                "tmax_c": (r[col["tmax"]] or "").strip(),
            }
        )
    return out, notes


def main() -> None:
    catalogue = json.loads(_get(CATALOGUE))
    files = []
    for item in catalogue["results"].values():
        if item.get("identifier") in DATASETS:
            for dist in item["distribution"]:
                files.append((file_month(dist["title"]), dist["title"], dist["downloadURL"]))
    files.sort()
    rows: list[dict[str, str]] = []
    log_rows, total_notes = [], Counter()
    for month, title, url in files:
        content = _get(url, cache=True)
        found, notes = rows_of(content, month)
        rows.extend(found)
        total_notes.update(notes)
        log_rows.append(
            f"| {month[0]}-{month[1]:02d} | [{title}]({url}) | {len(content):,} | "
            f"`{hashlib.sha256(content).hexdigest()}` | {len(found):,} | "
            f"{notes.get('day_month_swapped', 0)} | "
            f"{notes.get('unparsed', 0) + notes.get('outside_file_month', 0)} |"
        )
        time.sleep(1)  # be gentle with the portal
    rows.sort(key=lambda r: (r["date"], r["district"], r["mandal"], r["station"]))
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=FIELDS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    OUT.write_bytes(gzip.compress(stream.getvalue().encode("utf-8"), mtime=0))
    digest = hashlib.sha256(OUT.read_bytes()).hexdigest()
    first, last = files[0][0], files[-1][0]
    table = "\n".join(log_rows)
    bad = total_notes.get("unparsed", 0) + total_notes.get("outside_file_month", 0)
    dates = (
        f"{total_notes.get('ok', 0):,} as written; "
        f"{total_notes.get('day_month_swapped', 0):,} corrected (day and month swapped, days "
        f"1-12 of 2023-2026 files); {bad:,} not usable (left blank, `date_note` says why)"
    )
    (OUT_DIR / "RETRIEVAL_LOG.md").write_text(
        f"""# D8b Daily weather per mandal (TGDPS automatic weather stations) — Retrieval Log

**Dataset:** Open Data Telangana, "Telangana Weather Data from 2018 - 2022" and "Telangana
Weather Data from 2023 - 2026" (Telangana State Development Planning Society)
**Basis:** REAL (station measurements; 2018-2022 per station, 2023-2026 per mandal)
**Licence:** Government Open Data License - India
**Used by:** F5 gradient-boosting candidate with weather per section (research follow-up B)

| Field | Value |
|---|---|
| Catalogue | `{CATALOGUE}` (each file's `downloadURL`) |
| Months | {first[0]}-{first[1]:02d} to {last[0]}-{last[1]:02d} ({len(files)} monthly files) |
| Districts kept | {", ".join(sorted(DISTRICTS))} |
| Rows | {len(rows):,} |
| Dates | {dates} |
| Retrieved | {datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")} |
| File | `{OUT.name}` |
| SHA-256 | `{digest}` |

Raw values are copied as written (rain in mm, minimum and maximum temperature in deg C); only the
date is parsed, with the original text kept in `date_raw`. Rows of other districts are dropped.

## Source files

| Month | File | Bytes | SHA-256 | Rows kept | Dates corrected | Dates not usable |
|---|---|---|---|---|---|---|
{table}
""",
        encoding="utf-8",
    )
    print(f"Wrote {OUT} ({len(rows):,} rows from {len(files)} files, sha256 {digest[:12]})")
    print(dict(total_notes))


if __name__ == "__main__":
    main()
