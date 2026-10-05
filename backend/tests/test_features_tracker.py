"""The tracker (docs/features.csv) says how far each task meets the solution doc (item 22).

A task is DONE when its own done-when test passed, which is often narrower than the doc's
promise. `doc_promise_met` (yes / partly / no) and `gap` make that visible on every row.
"""

import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TRACKER = ROOT / "docs" / "features.csv"
PROMISE_VALUES = {"yes", "partly", "no"}


def _rows() -> list[dict[str, str]]:
    with TRACKER.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def test_tracker_has_promise_columns() -> None:
    with TRACKER.open(encoding="utf-8-sig", newline="") as handle:
        header = next(csv.reader(handle))
    assert header[-2:] == ["doc_promise_met", "gap"]


def test_every_row_says_whether_the_doc_promise_is_met() -> None:
    for row in _rows():
        assert row["doc_promise_met"] in PROMISE_VALUES, row["id"]


def test_partly_or_unmet_promises_name_the_gap() -> None:
    for row in _rows():
        if row["doc_promise_met"] != "yes":
            assert row["gap"].strip(), f"{row['id']} needs a gap note"


def test_done_when_narrower_than_promise_is_not_marked_met() -> None:
    # The examples in docs/REMAINING_WORK.md item 22: DONE, but the doc's promise is not met.
    by_id = {row["id"]: row for row in _rows()}
    for task_id in ("T2", "T9"):
        assert by_id[task_id]["status"] == "DONE"
        assert by_id[task_id]["doc_promise_met"] != "yes", task_id


def test_stale_rows_are_fixed() -> None:
    # docs/LIMITATIONS.md section 6: T7 is merged (PR #46). Screens wired to the live API in
    # PR #65 must not say the API integration is still missing.
    by_id = {row["id"]: row for row in _rows()}
    assert by_id["T7"]["status"] == "DONE"
    for task_id in ("U4", "U5", "U6", "U7", "U8"):
        notes = by_id[task_id]["notes"].lower()
        for stale in ("remains pending", "unavailable", "no live t10 api", "until t10"):
            assert stale not in notes, f"{task_id}: {stale}"
