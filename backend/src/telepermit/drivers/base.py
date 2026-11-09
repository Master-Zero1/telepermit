"""Driver types: Proposal, Observation and the AgentDriver protocol (CONTRACTS section 7).

This module imports nothing from telepermit. A driver only ever sees an Observation and only
ever returns a Proposal, so it cannot reach the engine, a tool executor or a signing key.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class Proposal:
    """The action a driver wants to take next, with its arguments."""

    action: str
    args: dict[str, str]


@dataclass(frozen=True, slots=True)
class Observation:
    """What a driver is allowed to see. Exactly these five fields and nothing else."""

    task: str
    turn: int
    place: str
    tools: list[dict[str, object]]
    last_result: str | None


class AgentDriver(Protocol):
    """Anything that can turn an Observation into a Proposal."""

    def propose(self, observation: Observation) -> Proposal:
        """Return the next Proposal for this Observation."""
