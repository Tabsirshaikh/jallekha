from dataclasses import dataclass

# All values ported from the v1 prototype's config (github.com/abhay-hanchate/jallekha,
# backend/app/config.py, "SPAM"). Basis: ASSUMED; to be tuned in T4 (intake) on real reports.


@dataclass(frozen=True)
class SpamConfig:
    # A report is spam when its score reaches this value (scores are 0-1).
    threshold: float = 0.7
    # More than burst_max_complaints from one phone within burst_window_minutes.
    burst_window_minutes: int = 60
    burst_max_complaints: int = 5
    burst_points: float = 0.5
    # Text shorter than this, with no category button, on a text channel.
    short_text_min_chars: int = 3
    short_text_points: float = 0.3
    # Reported location this far outside the claimed area.
    outside_area_km: float = 3.0
    outside_area_points: float = 0.3
    # Share of non-letter characters above which text counts as gibberish.
    gibberish_nonletter_ratio: float = 0.6
    # Neither letters nor gibberish: address punctuation (digits are skipped too), so an address
    # such as "H.No 12-3-456/7" is not flagged (S3 review D13). Basis: ASSUMED.
    address_punctuation: str = ".,-/#:()"
    gibberish_points: float = 0.2
    # Unregistered phone and no area given.
    unregistered_points: float = 0.2


SPAM_CONFIG = SpamConfig()
