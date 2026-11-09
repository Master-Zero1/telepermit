"""The Engine: the only executor of tools (CONTRACTS section 5).

This first part builds construction, the spawn border check, state and events. The step
algorithm and the run loop arrive in later tasks.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final

from telepermit.audit import (
    BORDER_CHECK,
    RUN_ENDED,
    RUN_STARTED,
    STATUS_ALIVE,
    STATUS_REFUSED,
    BorderCheckData,
    Event,
    EventData,
    RunEndedData,
    RunStartedData,
    narrowed_fields,
    permit_json,
)
from telepermit.clock import TickClock
from telepermit.drivers.base import Proposal
from telepermit.identity import Identity
from telepermit.permit import Permit
from telepermit.place import REFUSE, Place

GO_COST: Final = 1
HARNESS_CAP: Final = 30


class AgentNotAlive(RuntimeError):
    """Raised by step when the agent has already ended."""


@dataclass(frozen=True, slots=True)
class EngineState:
    """A snapshot of the Engine. Changing it does not change the Engine."""

    status: str
    place: str
    steps: int
    spent: int
    permit: Permit


@dataclass(frozen=True, slots=True)
class RunResult:
    """What run returns: the final status, a copy of the event log and the final state."""

    status: str
    events: list[Event]
    state: EngineState


class Engine:
    """Owns every tool call: meters it, checks it and logs one event per state transition."""

    def __init__(
        self,
        places: Mapping[str, Place],
        identity: Identity,
        permit: Permit,
        start_place: str,
        clock: TickClock,
        enforce: bool = True,
        *,
        scenario: str = "",
        driver: str = "scripted",
        task: str = "",
    ) -> None:
        if start_place not in places:
            raise ValueError(f"unknown start place {start_place!r}")
        self._places = dict(places)
        self._identity = identity
        self._clock = clock
        self._enforce = enforce
        self._born = clock.now()
        self._status = STATUS_ALIVE
        self._place = start_place
        self._steps = 0
        self._spent = 0
        self._permit = permit
        self._events: list[Event] = []
        started: RunStartedData = {
            "scenario": scenario,
            "driver": driver,
            "enforce": enforce,
            "task": task,
            "identity": {
                "agent_id": identity.agent_id,
                "agent_class": identity.agent_class,
                "authority": identity.authority,
                "issued_at": identity.issued_at,
                "signature_hex": identity.signature_hex,
            },
            "permit": permit_json(permit),
        }
        self._emit(RUN_STARTED, started)
        if enforce:
            self._spawn_border_check(permit)

    @property
    def state(self) -> EngineState:
        """A fresh snapshot of the current state."""
        return EngineState(self._status, self._place, self._steps, self._spent, self._permit)

    @property
    def events(self) -> list[Event]:
        """A copy of the event log."""
        return list(self._events)

    def step(self, proposal: Proposal) -> list[Event]:
        """Apply one proposal. Row 1 is done here; rows 2 to 11 arrive in task 5."""
        if self._status != STATUS_ALIVE:
            raise AgentNotAlive(f"agent is {self._status}")
        raise NotImplementedError("rows 2 to 11: task 5")

    def _emit(self, event_type: str, data: EventData) -> Event:
        """The only writer of the log. It reads the state AFTER the transition."""
        event = Event(
            len(self._events),
            self._clock.now(),
            event_type,
            self._place,
            self._steps,
            self._spent,
            data,
        )
        self._events.append(event)
        return event

    def _spawn_border_check(self, requested: Permit) -> None:
        admission = self._places[self._place].admit(self._identity, requested, 0, 0, 0.0)
        after = requested if admission.permit_after is None else admission.permit_after
        border: BorderCheckData = {
            "place": self._place,
            "via_action": None,
            "decision": admission.decision,
            "reason": admission.reason,
            "permit_after": permit_json(after),
            "narrowed_fields": narrowed_fields(requested, after),
            "cost": 0,
            "explain": f"{self._place}: {admission.decision} ({admission.reason})",
        }
        self._emit(BORDER_CHECK, border)
        if admission.decision == REFUSE:
            self._status = STATUS_REFUSED
            ended: RunEndedData = {"status": STATUS_REFUSED}
            self._emit(RUN_ENDED, ended)
        else:
            self._permit = after
