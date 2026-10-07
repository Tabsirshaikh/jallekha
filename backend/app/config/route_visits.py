from dataclasses import dataclass

# Driver route test (U4 driver screen, officer route sheet): after unloading at a stop of the
# approved plan, the driver takes a code from each of a few residents. This is a SIMULATION for a
# local demo: no SMS is sent and no OTP is made; every resident's code is the fixed one below.
# It runs only in local test mode (SMS_PROVIDER=outbox, sign-in off), like the SMS test mode.


@dataclass(frozen=True)
class RouteVisitConfig:
    # People asked for a code at each stop. Basis: SIMULATION (owner request 2026-10-07).
    residents_per_stop: int = 3
    # The code every simulated resident gives. Basis: SIMULATION (owner request 2026-10-07:
    # "keep everything 000000"). Never a real delivery code.
    code: str = "000000"


ROUTE_VISIT_CONFIG = RouteVisitConfig()
