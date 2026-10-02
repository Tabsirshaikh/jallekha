from dataclasses import dataclass


@dataclass(frozen=True)
class EquityConfig:
    # Solution F3 and E4: top 10%, rounded UP to include 21 of 201 sections.
    top_fraction: float = 0.1
    # Solution headline: bottom half, rounded DOWN; always report included count.
    bottom_fraction: float = 0.5


EQUITY_CONFIG = EquityConfig()
