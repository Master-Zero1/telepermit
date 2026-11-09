"""Simulated tools and their costs (CONTRACTS section 4).

This module holds the Tool type. The catalog factories come in a later task.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Tool:
    """A simulated capability with a cost in teleclicks."""

    name: str
    cost: int
    description: str
    args: dict[str, str]
    fn: Callable[[dict[str, str]], str]

    def __post_init__(self) -> None:
        if isinstance(self.cost, bool) or not isinstance(self.cost, int):
            raise TypeError(f"cost must be an int, got {type(self.cost).__name__}")
        if self.cost < 0:
            raise ValueError(f"cost must be >= 0, got {self.cost}")
