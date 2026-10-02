from dataclasses import dataclass


@dataclass(frozen=True)
class TrustConfig:
    # Source: docs/JALLEKHA_FINAL_SOLUTION.md F12 ("server-side geofence (150 m)").
    geofence_radius_metres: int = 150
    # No source in docs/JALLEKHA_FINAL_SOLUTION.md. Related rule, F11: only Confirmed
    # deliveries (F12) count. Meaning and value to be decided in T3 / A6.
    unresolved_delivery_changes_shortfall: bool = False


TRUST_CONFIG = TrustConfig()
