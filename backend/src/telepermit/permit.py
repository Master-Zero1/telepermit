"""Immutable Permit with validation (CONTRACTS section 2).

Construction, validation, narrowing and JSON serialisation.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
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

    def narrowed_by(self, ceiling: Permit) -> Permit:
        """Return a new Permit no wider than self or ceiling on any field."""
        return Permit(
            lifetime_s=min(self.lifetime_s, ceiling.lifetime_s),
            max_steps=min(self.max_steps, ceiling.max_steps),
            allowance=min(self.allowance, ceiling.allowance),
            allowed_actions=self.allowed_actions & ceiling.allowed_actions,
        )

    def to_json(self) -> dict[str, object]:
        """Return a JSON-ready dict with allowed_actions as a sorted list."""
        return {
            "lifetime_s": self.lifetime_s,
            "max_steps": self.max_steps,
            "allowance": self.allowance,
            "allowed_actions": sorted(self.allowed_actions),
        }

    @classmethod
    def from_json(cls, data: Mapping[str, object]) -> Permit:
        """Inverse of to_json. Goes through the constructor, so it validates."""
        return cls(
            lifetime_s=data["lifetime_s"],  # type: ignore[arg-type]
            max_steps=data["max_steps"],  # type: ignore[arg-type]
            allowance=data["allowance"],  # type: ignore[arg-type]
            allowed_actions=data["allowed_actions"],  # type: ignore[arg-type]
        )
