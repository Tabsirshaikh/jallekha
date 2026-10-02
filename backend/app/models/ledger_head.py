from __future__ import annotations

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, IdTimestampMixin


class LedgerHead(IdTimestampMixin, Base):
    """The ledger head published for one day (F18, T6): the last entry's seq and hash.

    Once published it is not changed. It is also sent outside the system (ward report card /
    SMS, P4 / T5), so a key holder who rewrites or truncates the chain cannot match it.
    `created_at` (UTC) is the publish time; `day` is the local day (config offset).
    """

    __tablename__ = "ledger_head"

    day: Mapped[str] = mapped_column(String(10), unique=True)  # YYYY-MM-DD
    seq: Mapped[int] = mapped_column(Integer)
    head_hash: Mapped[str] = mapped_column(String(64))
    key_id: Mapped[str] = mapped_column(String(32))
