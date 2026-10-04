"""Plans built and stored by the API (A7 planner on P2's replay, T9 gate). No secrets here."""

from dataclasses import dataclass


@dataclass(frozen=True)
class PlanStoreConfig:
    # P2's committed A7 replay builder (Mar-Jul 2025, SIMULATION); plans are built from it.
    replay_script: str = "scripts/sandbox/build_planner_replay.py"
    # Rebuilt plans a store keeps in memory. A replay day holds about 7,000 pending bookings
    # (measured on main_2025 tight, 2026-10-04), so the cache is kept small. ASSUMED, OPEN.
    built_cache_size: int = 8
    # Replay runs kept for officer-chosen need weights (the default run is one of them). Each holds
    # one day's pending bookings and queue states in memory. ASSUMED, OPEN.
    weighted_replays_kept: int = 3


PLAN_STORE_CONFIG = PlanStoreConfig()
