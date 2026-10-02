from __future__ import annotations

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, IdTimestampMixin


class VoiceNote(IdTimestampMixin, Base):
    """A stored voice report (F14, T4). The audio is always kept, so no report is lost.

    `needs_human` is set when speech recognition was not available (fallback); a person then
    writes the transcript. `audio_ref` is the file name in INTAKE_AUDIO_DIR (sha256 + extension).
    """

    __tablename__ = "voice_note"

    complaint_id: Mapped[str] = mapped_column(ForeignKey("complaint.id"), index=True)
    audio_ref: Mapped[str] = mapped_column(String(80))
    content_type: Mapped[str] = mapped_column(String(40))
    size_bytes: Mapped[int] = mapped_column(Integer)
    transcriber: Mapped[str] = mapped_column(String(24))  # fallback | indicconformer | ...
    transcript: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[float | None] = mapped_column(Float)
    needs_human: Mapped[bool] = mapped_column(Boolean, default=False)
