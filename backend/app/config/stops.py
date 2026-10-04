"""Stop registration (F12): what an officer may register for the delivery-proof flow.

The 2-3 representatives and the 3-5 residents sampled per delivery come from TRUST_CONFIG
(config/trust.py). Every value here has a source or is marked ASSUMED.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class StopConfig:
    # Source: ITU-T E.164 (international number: "+", country code, at most 15 digits). The lower
    # bound of 8 digits is ASSUMED. No spaces or dashes: the number is stored as sent.
    phone_pattern: str = r"^\+[1-9][0-9]{7,14}$"
    # Ids: letters, digits and . _ : - so they read safely in URLs and ledger entries.
    # Technical, ASSUMED.
    id_pattern: str = r"^[A-Za-z0-9._:-]+$"
    # Column widths (app/models): stop_id String(64), representative.id String(36),
    # resident_id String(64).
    stop_id_max: int = 64
    representative_id_max: int = 36
    resident_id_max: int = 64
    # Largest resident list in one registration request (bounds the request size).
    # Technical, ASSUMED.
    residents_max: int = 500


STOP_CONFIG = StopConfig()
