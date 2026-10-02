"""Fetch GHS-POP R2023A (EU JRC) population grids for 2015 and 2025 and crop them to GHMC.

Usage:
    python scripts/data/fetch_ghs_pop.py [cache_dir]

GHS-POP R2023A, 3 arc-second (~90 m) WGS84 grid, tile R8_C26 (10 x 10 degrees around
Hyderabad), epochs 2015 and 2025. Licence CC BY 4.0, (c) European Union 1995-2026. Values are
modelled residents per cell (census totals disaggregated by built-up volume), not counts.

A tile is 168 MB (over GitHub's file limit), so only the GHMC crop is committed:
data/derived/population_inputs/ghs_pop_<year>_ghmc.tif, with the source URL, the zip's
SHA-256 and size, and the crop window in data/derived/population_inputs/manifest.json, so the
crop can be re-made from the original. The server limits speed per connection; the download
uses parallel byte ranges and is verified against the published Content-Length.
"""

from __future__ import annotations

import hashlib
import json
import sys
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

import rasterio
from rasterio.windows import from_bounds

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "derived" / "population_inputs"
BASE = "https://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/GHSL/GHS_POP_GLOBE_R2023A"
TILE = "R8_C26"
YEARS = (2015, 2025)
# GHMC bounding box with a margin: west, south, east, north (degrees)
CROP = (78.15, 17.15, 78.75, 17.70)
PARTS = 12


def tile_url(year: int) -> str:
    name = f"GHS_POP_E{year}_GLOBE_R2023A_4326_3ss"
    return f"{BASE}/{name}/V1-0/tiles/{name}_V1_0_{TILE}.zip"


def download(url: str, target: Path) -> None:
    head = urllib.request.urlopen(urllib.request.Request(url, method="HEAD"), timeout=60)
    size = int(head.headers["Content-Length"])
    if target.exists() and target.stat().st_size == size:
        return
    step = size // PARTS + 1
    ranges = [(i * step, min(size, (i + 1) * step) - 1) for i in range(PARTS)]

    def fetch(item: tuple[int, tuple[int, int]]) -> None:
        index, (start, end) = item
        part = target.with_suffix(f".part{index}")
        have = part.stat().st_size if part.exists() else 0
        for _attempt in range(20):
            if start + have > end:
                return
            request = urllib.request.Request(url, headers={"Range": f"bytes={start + have}-{end}"})
            try:
                with urllib.request.urlopen(request, timeout=120) as resp, part.open("ab") as fh:
                    while chunk := resp.read(1 << 16):
                        fh.write(chunk)
                        have += len(chunk)
            except OSError as error:
                print(f"  part {index} retry: {error}", flush=True)

    with ThreadPoolExecutor(PARTS) as pool:
        list(pool.map(fetch, enumerate(ranges)))
    with target.open("wb") as fh:
        for index in range(PARTS):
            part = target.with_suffix(f".part{index}")
            fh.write(part.read_bytes())
            part.unlink()
    if target.stat().st_size != size:
        raise RuntimeError(f"Size mismatch for {url}")


def main() -> int:
    cache = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / ".cache" / "ghs_pop"
    cache.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    entries = []
    for year in YEARS:
        url = tile_url(year)
        archive = cache / f"ghs_{year}.zip"
        download(url, archive)
        with zipfile.ZipFile(archive) as zf:
            tif = next(n for n in zf.namelist() if n.endswith(".tif"))
        with rasterio.open(f"zip://{archive.as_posix()}!/{tif}") as src:
            window = from_bounds(*CROP, transform=src.transform).round_offsets().round_lengths()
            data = src.read(1, window=window)
            profile = src.profile | {
                "height": data.shape[0],
                "width": data.shape[1],
                "transform": src.window_transform(window),
                "compress": "deflate",
                "predictor": 3,
                "tiled": False,
            }
        crop = OUT / f"ghs_pop_{year}_ghmc.tif"
        with rasterio.open(crop, "w", **profile) as dst:
            dst.write(data, 1)
        entries.append(
            {
                "year": year,
                "source_url": url,
                "source_zip_sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
                "source_zip_bytes": archive.stat().st_size,
                "source_tif": tif,
                "crop_bounds_wsen": list(CROP),
                "crop_file": crop.relative_to(ROOT).as_posix(),
                "crop_sha256": hashlib.sha256(crop.read_bytes()).hexdigest(),
                "licence": "CC BY 4.0, (c) European Union 1995-2026 (GHSL, JRC)",
                "basis": "REAL (modelled grid as published)",
            }
        )
        print(f"  {year}: {crop.relative_to(ROOT).as_posix()} {data.shape}", flush=True)
    manifest = {
        "dataset": "GHS-POP R2023A, 3 arc-second, WGS84",
        "citation": (
            "Schiavina M., Freire S., Carioli A., MacManus K. (2023): GHS-POP R2023A - GHS "
            "population grid multitemporal (1975-2030). European Commission, JRC. "
            "doi:10.2905/2FF68A52-5B5B-4A22-8F40-C41DA8332CFE"
        ),
        "retrieved_at_utc": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "files": entries,
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print("GHS-POP crops written.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
