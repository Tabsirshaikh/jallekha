"""Rebuild and compare exact-section screening artifacts, including source digests."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.evidence.build_section_checks import OUTPUT, build, encode  # noqa: E402


def main():
    rows, summary = build()
    assert (ROOT / OUTPUT / "section_checks.csv").read_text(encoding="utf-8") == encode(rows)
    assert json.loads((ROOT / OUTPUT / "section_checks_summary.json").read_text()) == summary
    snapshot = json.loads((ROOT / "frontend/src/data/u5SectionChecks.json").read_text())
    assert snapshot == {"items": rows, "total": len(rows)}
    assert all(r["section"] not in r["peer_sections"] for r in rows)
    print(f"Section checks verified: {len(rows)} sections; {summary['flagged_count']} candidates")


if __name__ == "__main__":
    main()
