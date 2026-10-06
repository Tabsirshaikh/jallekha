"""ASSUMED minimum sample and input bounds for field-check observations."""

from dataclasses import dataclass


@dataclass(frozen=True)
class SectionOutcomeConfig:
    minimum_decisive_sections: int = 30
    maximum_note_chars: int = 2000
    timezone: str = "Asia/Calcutta"
    basis: str = "ASSUMED"


SECTION_OUTCOME_CONFIG = SectionOutcomeConfig()
