"""Clock protocol and the deterministic TickClock (CONTRACTS section 5)."""

from __future__ import annotations

import math
from typing import Final, Protocol

TICK_S: Final = 1.0


class Clock(Protocol):
    """Anything that can report the current time in seconds."""

    def now(self) -> float:
        """Return the current time in seconds."""


class TickClock:
    """A simulated clock that moves only when told to. Time never goes backwards."""

    def __init__(self, start: float = 0.0) -> None:
        if not math.isfinite(start):
            raise ValueError("start must be finite")
        self._now = float(start)

    def now(self) -> float:
        """Return the current simulated time in seconds."""
        return self._now

    def advance(self, dt: float) -> None:
        """Move the clock forward by dt seconds. Zero is allowed, negative or non-finite is not."""
        if not math.isfinite(dt) or dt < 0:
            raise ValueError(f"dt must be finite and >= 0, got {dt}")
        self._now += dt
