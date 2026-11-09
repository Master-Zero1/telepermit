"""The Engine: the only executor of tools (CONTRACTS section 5).

It meters every action, applies the step algorithm in the order of CONTRACTS section 5, destroys
the agent on a breach and emits one audit event per state transition. The run loop arrives in a
later task.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final

from telepermit.audit import (
    ALLOWANCE_EXCEEDED,
    BORDER_CHECK,
    DENIED,
    FINISHED,
    KILLED,
    LIFETIME_EXCEEDED,
    NOT_IN_PERMIT,
    NOT_IN_PLACE,
    RUN_ENDED,
    RUN_STARTED,
    STATUS_ALIVE,
    STATUS_FINISHED,
    STATUS_KILLED,
    STATUS_REFUSED,
    STEPS_EXCEEDED,
    TOOL_CALL,
    UNENFORCED,
    BorderCheckData,
    DeniedData,
    Event,
    EventData,
    FinishedData,
    KilledData,
    RunEndedData,
    RunStartedData,
    ToolCallData,
    narrowed_fields,
    permit_json,
)
from telepermit.clock import TickClock
from telepermit.drivers.base import Proposal
from telepermit.identity import Identity
from telepermit.permit import Permit
from telepermit.place import ADMIT, REFUSE, Place

GO_COST: Final = 1
HARNESS_CAP: Final = 30
FINISH_ACTION: Final = "finish"
GO_PREFIX: Final = "go:"


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
        """Apply one proposal and return the events this call emitted.

        The rows of the algorithm run strictly in order and the first one that matches decides
        the call. With enforcement off the lifetime, step, permit and allowance checks are skipped
        and a go moves at once.
        """
        if self._status != STATUS_ALIVE:
            raise AgentNotAlive(f"agent is {self._status}")
        first = len(self._events)
        self._apply(proposal)
        return self._events[first:]

    def _apply(self, proposal: Proposal) -> None:
        action = proposal.action
        permit = self._permit
        enforce = self._enforce
        elapsed = self._clock.now() - self._born
        if enforce and elapsed > permit.lifetime_s:
            self._kill(LIFETIME_EXCEEDED, action, permit.lifetime_s, elapsed)
            return
        if action == FINISH_ACTION:
            self._status = STATUS_FINISHED
            finished: FinishedData = {}
            self._emit(FINISHED, finished)
            self._emit_run_ended(STATUS_FINISHED)
            return
        if enforce and self._steps + 1 > permit.max_steps:
            self._kill(STEPS_EXCEEDED, action, permit.max_steps, self._steps + 1)
            return
        self._steps += 1
        if enforce and action not in permit.allowed_actions:
            self._deny(action, NOT_IN_PERMIT)
            return
        place = self._places[self._place]
        is_go = action.startswith(GO_PREFIX)
        destination = action[len(GO_PREFIX) :]
        if is_go:
            available = destination in self._places and destination != self._place
        else:
            available = place.has_tool(action)
        if not available:
            self._deny(action, NOT_IN_PLACE)
            return
        cost = GO_COST if is_go else place.tool_cost(action)
        if enforce and self._spent + cost > permit.allowance:
            self._kill(ALLOWANCE_EXCEEDED, action, permit.allowance, self._spent + cost)
            return
        self._spent += cost
        if not is_go:
            self._call_tool(place, proposal, cost)
        elif enforce:
            self._cross(action, destination, elapsed)
        else:
            self._move_unenforced(action, destination)

    def _call_tool(self, place: Place, proposal: Proposal, cost: int) -> None:
        result = place.execute(proposal.action, dict(proposal.args))
        call: ToolCallData = {
            "action": proposal.action,
            "args": dict(proposal.args),
            "cost": cost,
            "result": result,
        }
        self._emit(TOOL_CALL, call)

    def _cross(self, action: str, destination: str, elapsed: float) -> None:
        before = self._permit
        admission = self._places[destination].admit(
            self._identity, before, self._steps, self._spent, elapsed
        )
        after = before
        if admission.decision != REFUSE and admission.permit_after is not None:
            after = admission.permit_after
            self._place = destination
            self._permit = after
        border: BorderCheckData = {
            "place": destination,
            "via_action": action,
            "decision": admission.decision,
            "reason": admission.reason,
            "permit_after": permit_json(after),
            "narrowed_fields": narrowed_fields(before, after),
            "cost": GO_COST,
            "explain": f"{destination}: {admission.decision} ({admission.reason})",
        }
        self._emit(BORDER_CHECK, border)

    def _move_unenforced(self, action: str, destination: str) -> None:
        """With enforcement off the agent moves at once, with no identity or class check."""
        self._place = destination
        border: BorderCheckData = {
            "place": destination,
            "via_action": action,
            "decision": ADMIT,
            "reason": UNENFORCED,
            "permit_after": permit_json(self._permit),
            "narrowed_fields": [],
            "cost": GO_COST,
            "explain": f"{destination}: {ADMIT} ({UNENFORCED})",
        }
        self._emit(BORDER_CHECK, border)

    def _deny(self, action: str, reason: str) -> None:
        denied: DeniedData = {
            "action": action,
            "reason": reason,
            "explain": f"action {action!r} was denied: {reason}",
        }
        self._emit(DENIED, denied)

    def _kill(self, reason: str, action: str, limit: float, observed: float) -> None:
        """Set the status first, then emit KILLED and RUN_ENDED with the same snapshot."""
        self._status = STATUS_KILLED
        killed: KilledData = {
            "reason": reason,
            "action": action,
            "limit": limit,
            "observed": observed,
            "explain": f"{reason}: limit {limit}, observed {observed}",
        }
        self._emit(KILLED, killed)
        self._emit_run_ended(STATUS_KILLED)

    def _emit_run_ended(self, status: str) -> None:
        ended: RunEndedData = {"status": status}
        self._emit(RUN_ENDED, ended)

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
            self._emit_run_ended(STATUS_REFUSED)
        else:
            self._permit = after
