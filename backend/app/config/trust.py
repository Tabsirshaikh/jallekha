from dataclasses import dataclass


@dataclass(frozen=True)
class TrustConfig:
    geofence_radius_metres: int = 150
    unresolved_delivery_changes_shortfall: bool = False


TRUST_CONFIG = TrustConfig()
