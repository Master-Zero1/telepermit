"""Place, Admission, tool access and the border check (CONTRACTS section 4)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from telepermit.identity import Identity, verify_identity
from telepermit.permit import Permit
from telepermit.tools import Tool

ADMIT: Final = "ADMIT"
ADMIT_IMPOSED: Final = "ADMIT_IMPOSED"
REFUSE: Final = "REFUSE"
OK: Final = "OK"
CLASS_NOT_ALLOWED: Final = "CLASS_NOT_ALLOWED"
EXCEEDS_CEILING: Final = "EXCEEDS_CEILING"

_DECISIONS: Final = frozenset({ADMIT, ADMIT_IMPOSED, REFUSE})


class UnknownToolError(LookupError):
    """Raised when a tool name is not held by a Place."""


@dataclass(frozen=True, slots=True)
class Admission:
    """The result of a border check. permit_after is None exactly when the decision is REFUSE."""

    decision: str
    permit_after: Permit | None
    reason: str

    def __post_init__(self) -> None:
        if self.decision not in _DECISIONS:
            raise ValueError(f"unknown decision {self.decision!r}")
        if (self.decision == REFUSE) != (self.permit_after is None):
            raise ValueError("permit_after must be None exactly when the decision is REFUSE")


@dataclass(frozen=True, slots=True)
class Place:
    """A named location with tools, a ceiling, trusted authorities and allowed agent classes."""

    name: str
    tools: dict[str, Tool]
    ceiling: Permit
    trusted: Mapping[str, Ed25519PublicKey]
    allowed_classes: frozenset[str]

    def has_tool(self, name: str) -> bool:
        """True if this Place holds a tool with that name. Never raises."""
        return name in self.tools

    def tool_cost(self, name: str) -> int:
        """The cost of the named tool in teleclicks."""
        return self._tool(name).cost

    def execute(self, name: str, args: dict[str, str]) -> str:
        """Run the named tool. Only the engine may call this (security invariant 1)."""
        return self._tool(name).fn(args)

    def admit(
        self,
        identity: Identity,
        permit: Permit,
        steps: int,
        spent: int,
        elapsed: float,
    ) -> Admission:
        """The border check, in CONTRACTS section 4 order: identity, class, counters, narrowing.

        The first check that fails decides the result. A counter equal to its narrowed limit is
        admitted. ADMIT means narrowing the permit by the ceiling changed nothing.
        """
        code = verify_identity(identity, self.trusted)
        if code is not None:
            return Admission(REFUSE, None, code)
        if identity.agent_class not in self.allowed_classes:
            return Admission(REFUSE, None, CLASS_NOT_ALLOWED)
        narrowed = permit.narrowed_by(self.ceiling)
        if (
            spent > narrowed.allowance
            or steps > narrowed.max_steps
            or elapsed > narrowed.lifetime_s
        ):
            return Admission(REFUSE, None, EXCEEDS_CEILING)
        if narrowed == permit:
            return Admission(ADMIT, permit, OK)
        return Admission(ADMIT_IMPOSED, narrowed, OK)

    def _tool(self, name: str) -> Tool:
        tool = self.tools.get(name)
        if tool is None:
            raise UnknownToolError(f"unknown tool {name!r} in place {self.name!r}")
        return tool
