"""Read-only ledger endpoints (F18, T6): list entries and verify the chain.

There are deliberately no create, update or delete endpoints: modules write through
`services.ledger_store.record`, and nothing may change an entry afterwards.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query

from app.config.trust import TRUST_CONFIG
from app.services.ledger_store import StoredLedger, get_ledger

router = APIRouter(prefix="/ledger", tags=["ledger"])


def get_ledger_dependency() -> StoredLedger:
    return get_ledger()


Ledger = Annotated[StoredLedger, Depends(get_ledger_dependency)]


@router.get("/entries")
def list_entries(
    ledger: Ledger,
    after_seq: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=TRUST_CONFIG.ledger_list_max_limit)] = 100,
) -> dict[str, Any]:
    """Entries after `after_seq`, oldest first. Payloads hold ids and numbers only."""
    entries = [
        {**asdict(entry), "key_id": key_id} for entry, key_id in ledger.page(after_seq, limit)
    ]
    return {"entries": entries}


@router.get("/verify")
def verify(ledger: Ledger) -> dict[str, Any]:
    """Verify the stored chain and the published heads; report the first broken entry."""
    return asdict(ledger.verify())
