"""Immutable Permit with validation (CONTRACTS section 2).

Task 1.1 covers construction and validation only. Narrowing and JSON come later.
"""

from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass


def _require_int(name: str, value: object) -> int:
    """Return value if it is a real int (not bool, not float), else raise TypeError."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an int, got {type(value).__name__}")
    return value


def _require_lifetime(value: object) -> float:
    """Coerce an int or float lifetime to a finite float, else raise."""
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise TypeError(f"lifetime_s must be a number, got {type(value).__name__}")
    seconds = float(value)
    if not math.isfinite(seconds):
        raise ValueError("lifetime_s must be finite")
    return seconds


def _require_actions(value: object) -> frozenset[str]:
    """Coerce an iterable of str to a frozenset; a bare str is rejected."""
    if isinstance(value, str) or not isinstance(value, Iterable):
        raise TypeError("allowed_actions must be an iterable of str, not a bare str")
    actions = frozenset(value)
    if not all(isinstance(action, str) for action in actions):
        raise TypeError("allowed_actions must contain only str")
    return actions


@dataclass(frozen=True, slots=True)
class Permit:
    """Limits on an agent: lifetime, step limit, allowance (teleclicks) and allowed actions."""

    lifetime_s: float
    max_steps: int
    allowance: int
    allowed_actions: frozenset[str]

    def __post_init__(self) -> None:
        lifetime_s = _require_lifetime(self.lifetime_s)
        max_steps = _require_int("max_steps", self.max_steps)
        allowance = _require_int("allowance", self.allowance)
        actions = _require_actions(self.allowed_actions)
        for name, value in (
            ("lifetime_s", lifetime_s),
            ("max_steps", max_steps),
            ("allowance", allowance),
        ):
            if value < 0:
                raise ValueError(f"{name} must be >= 0, got {value}")
        object.__setattr__(self, "lifetime_s", lifetime_s)
        object.__setattr__(self, "max_steps", max_steps)
        object.__setattr__(self, "allowance", allowance)
        object.__setattr__(self, "allowed_actions", actions)
