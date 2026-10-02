from __future__ import annotations

import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    research_path = ROOT / "docs" / "research" / "P1.md"
    solution_path = ROOT / "docs" / "JALLEKHA_FINAL_SOLUTION.md"
    tracker_path = ROOT / "docs" / "features.csv"
    worklog_path = ROOT / "docs" / "BRANCH_WORKLOG.md"
    tasks_path = ROOT / "docs" / "P1_TASKS.md"

    for path in (research_path, solution_path, tracker_path, worklog_path, tasks_path):
        require(path.is_file(), f"Missing required R-P1 file: {path.relative_to(ROOT)}")
        require(path.stat().st_size > 0, f"Empty required R-P1 file: {path.relative_to(ROOT)}")

    research = research_path.read_text(encoding="utf-8")
    require(len(research.split()) <= 1_100, "P1 research note exceeds the two-page working limit")
    for marker in (
        "F1 Water Access Atlas",
        "F2 Growth adjustment",
        "F3 Booking equity/map",
        "F4 Under-served detector",
        "**FACT:**",
        "**INFERENCE:**",
        "**PROPOSED:**",
        "GHMC_2016_150",
        "WorldPop",
        "GHS-POP",
        "Agostini",
        "Riebler",
    ):
        require(marker in research, f"Research note is missing required evidence marker: {marker}")
    require(research.count("https://") >= 9, "Research note must retain direct evidence links")

    with tracker_path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    require(len(rows) == 47, f"Expected 47 tracker rows including E1-FIX, found {len(rows)}")
    by_id = {row["id"]: row for row in rows}
    require(len(by_id) == len(rows), "Tracker contains duplicate task IDs")
    require(by_id["R-P1"]["status"] in {"IN_REVIEW", "DONE"}, "R-P1 must be IN_REVIEW or DONE")
    require(
        by_id["R-P1"]["pr"] == "https://github.com/Tabsirshaikh/jallekha/pull/2",
        "R-P1 PR link is missing or incorrect",
    )
    for task_id in ("D1", "E1", "E3", "E5"):
        require(task_id in by_id, f"Missing revised downstream task: {task_id}")
    require(
        "geography version" in by_id["D1"]["done_when"].lower(),
        "D1 must require geography versioning",
    )
    require(
        "current 300-ward" in by_id["E1"]["task"], "E1 must preserve the current-geography block"
    )
    require(
        "WorldPop" in by_id["E3"]["notes"] and "GHS-POP" in by_id["E3"]["notes"],
        "E3 must disclose deferred independent population sensitivity sources",
    )
    require(
        "field-check" in by_id["E5"]["task"],
        "E5 must describe field-check screening rather than proven under-service",
    )

    solution = solution_path.read_text(encoding="utf-8")
    for marker in (
        "partial historical geometry; not current boundaries",
        "GHMC_2016_150",
        "it must not scale Census households",
        "No flag can change allocation or entitlement",
    ):
        require(marker in solution, f"Solution specification lost the R-P1 correction: {marker}")
    source_row = "GHMC/Telangana 2025-26 ward and corporation reorganisation notices"
    require(solution.count(source_row) == 1, "Geography source row must appear exactly once")

    worklog = worklog_path.read_text(encoding="utf-8")
    require("## `research/p1` — `R-P1`" in worklog, "Branch worklog has no R-P1 entry")
    for heading in (
        "What we found",
        "What we changed",
        "Validation",
        "Known limitations",
        "Handoff / next step",
        "Pull request",
    ):
        require(heading in worklog, f"R-P1 worklog is missing: {heading}")

    print("P1:R-P1 verification passed")
    print(f"- tracker rows: {len(rows)}")
    print(f"- research words: {len(research.split())}")
    print(f"- evidence links: {research.count('https://')}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as exc:
        print(f"P1:R-P1 verification failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
