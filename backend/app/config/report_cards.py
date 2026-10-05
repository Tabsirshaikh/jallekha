"""Ward report cards (F20) and closing a day's water debt (A6 on stored plans). No secrets here."""

from dataclasses import dataclass
from datetime import timedelta, timezone


@dataclass(frozen=True)
class ReportCardConfig:
    # 2016 GHMC ward polygons (D2, datameet / OSM, 145 wards), the same ids as the ward table.
    # A delivery stop without an officer-given ward is placed on them (DERIVED).
    ward_polygons: str = "data/raw/geography/datameet/ghmc-wards.geojson"
    # Days of deliveries a card counts. Basis: ASSUMED, OPEN (a month is what a resident can
    # remember and check; P4 research, docs/research/P4.md).
    delivery_window_days: int = 30
    # A plan's day and a delivery's day are Hyderabad days: India Standard Time has no daylight
    # saving, so a fixed UTC+05:30 offset is exact.
    service_timezone: timezone = timezone(timedelta(hours=5, minutes=30), "IST")


REPORT_CARD_CONFIG = ReportCardConfig()
