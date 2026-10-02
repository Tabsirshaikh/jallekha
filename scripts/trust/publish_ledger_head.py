"""Publish today's ledger head hash (F18, T6) and verify the chain first.

Run once a day (time and day boundary are OPEN, owner to confirm: config/trust.py
`ledger_head_publish_time_local`, `ledger_head_utc_offset_minutes`). Publishing twice on the
same local day returns the head already published. The printed line is what goes out on the
ward report card / SMS (P4 / T5), outside the key holder's control.

Usage (DATABASE_URL and LEDGER_HMAC_KEY from the environment, see .env.example):
    python scripts/trust/publish_ledger_head.py

Exit codes: 0 published (or already published today); 1 the chain does not verify (nothing
published); 2 the ledger is empty.
"""

from __future__ import annotations

from app.services.ledger_store import StoredLedger, get_ledger


def main(store: StoredLedger | None = None) -> int:
    store = store or get_ledger()
    check = store.verify()
    if not check.valid:
        print(f"Ledger does not verify: {check.reason} at seq {check.broken_at}. Not published.")
        return 1
    if check.head_seq is None:
        print("Ledger is empty; nothing to publish.")
        return 2
    head = store.publish_head()
    print(
        f"JalLekha ledger head {head.day}: seq {head.seq} hash {head.head_hash} key {head.key_id}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
