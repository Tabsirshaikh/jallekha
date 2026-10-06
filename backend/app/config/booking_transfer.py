"""ASSUMED geometry for a research transfer; official section boundaries are unavailable."""

from dataclasses import dataclass


@dataclass(frozen=True)
class BookingTransferConfig:
    division_buffer_metres: float = 1000.0
    building_year: int = 2023
    projected_crs: str = "EPSG:32644"
    minimum_valid_coverage: float = 0.95
    method: str = "VORONOI_DIVISION_HULL_1KM_OPEN_BUILDINGS_2023_32M_COUNT_SHARE"
    basis: str = "ASSUMED"


BOOKING_TRANSFER_CONFIG = BookingTransferConfig()
