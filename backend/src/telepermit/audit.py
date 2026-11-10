"""Audit events, statuses, reduce_events and the JSONL writer (CONTRACTS section 6)."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final, TypedDict

from telepermit.permit import Permit

SCHEMA_VERSION: Final = 1

RUN_STARTED: Final = "RUN_STARTED"
BORDER_CHECK: Final = "BORDER_CHECK"
TOOL_CALL: Final = "TOOL_CALL"
DENIED: Final = "DENIED"
KILLED: Final = "KILLED"
FINISHED: Final = "FINISHED"
RUN_ENDED: Final = "RUN_ENDED"
EVENT_TYPES: Final = frozenset(
    {RUN_STARTED, BORDER_CHECK, TOOL_CALL, DENIED, KILLED, FINISHED, RUN_ENDED}
)

STATUS_ALIVE: Final = "ALIVE"
STATUS_KILLED: Final = "KILLED"
STATUS_FINISHED: Final = "FINISHED"
STATUS_REFUSED: Final = "REFUSED"
STATUS_HARNESS_CAP: Final = "HARNESS_CAP"
STATUS_ERROR: Final = "ERROR"
STATUSES: Final = frozenset(
    {STATUS_ALIVE, STATUS_KILLED, STATUS_FINISHED, STATUS_REFUSED, STATUS_HARNESS_CAP, STATUS_ERROR}
)

NOT_IN_PERMIT: Final = "NOT_IN_PERMIT"
NOT_IN_PLACE: Final = "NOT_IN_PLACE"
LIFETIME_EXCEEDED: Final = "LIFETIME_EXCEEDED"
STEPS_EXCEEDED: Final = "STEPS_EXCEEDED"
ALLOWANCE_EXCEEDED: Final = "ALLOWANCE_EXCEEDED"
UNENFORCED: Final = "UNENFORCED"

PERMIT_FIELD_ORDER: Final = ("lifetime_s", "max_steps", "allowance", "allowed_actions")


class PermitJSON(TypedDict):
    lifetime_s: float
    max_steps: int
    allowance: int
    allowed_actions: list[str]


class IdentityJSON(TypedDict):
    agent_id: str
    agent_class: str
    authority: str
    issued_at: float
    signature_hex: str


class RunStartedData(TypedDict):
    scenario: str
    driver: str
    enforce: bool
    task: str
    identity: IdentityJSON
    permit: PermitJSON


class BorderCheckData(TypedDict):
    place: str
    via_action: str | None
    decision: str
    reason: str
    permit_after: PermitJSON
    narrowed_fields: list[str]
    cost: int
    explain: str


class ToolCallData(TypedDict):
    action: str
    args: dict[str, str]
    cost: int
    result: str


class DeniedData(TypedDict):
    action: str
    reason: str
    explain: str


class KilledData(TypedDict):
    reason: str
    action: str
    limit: int | float
    observed: int | float
    explain: str


class FinishedData(TypedDict):
    """The FINISHED event carries no data."""


class RunEndedData(TypedDict):
    status: str


EventData = (
    RunStartedData
    | BorderCheckData
    | ToolCallData
    | DeniedData
    | KilledData
    | FinishedData
    | RunEndedData
)


@dataclass(frozen=True, slots=True)
class Event:
    """One audit record. place, step and spent are the snapshot AFTER the transition."""

    seq: int
    t: float
    type: str
    place: str
    step: int
    spent: int
    data: EventData

    def __post_init__(self) -> None:
        if self.type not in EVENT_TYPES:
            raise ValueError(f"unknown event type {self.type!r}")

    def to_dict(self) -> dict[str, object]:
        """The event as a plain dict. data is a shallow copy."""
        return {
            "seq": self.seq,
            "t": self.t,
            "type": self.type,
            "place": self.place,
            "step": self.step,
            "spent": self.spent,
            "data": dict(self.data),
        }


def permit_json(permit: Permit) -> PermitJSON:
    """The PermitJSON shape of a permit, with allowed_actions as a sorted list."""
    return {
        "lifetime_s": permit.lifetime_s,
        "max_steps": permit.max_steps,
        "allowance": permit.allowance,
        "allowed_actions": sorted(permit.allowed_actions),
    }


def narrowed_fields(before: Permit, after: Permit) -> list[str]:
    """Names of the permit fields that differ, in the fixed order of PERMIT_FIELD_ORDER."""
    return [name for name in PERMIT_FIELD_ORDER if getattr(before, name) != getattr(after, name)]


class ReducedState(TypedDict):
    place: str
    step: int
    spent: int
    permit: PermitJSON
    status: str


def _copy_permit(data: PermitJSON) -> PermitJSON:
    return {
        "lifetime_s": data["lifetime_s"],
        "max_steps": data["max_steps"],
        "allowance": data["allowance"],
        "allowed_actions": list(data["allowed_actions"]),
    }


def reduce_events(events: Sequence[Event]) -> ReducedState:
    """Rebuild place, step, spent, permit and status from an event list.

    The snapshot comes from the last event, the permit from the last RUN_STARTED or BORDER_CHECK,
    and the status from the last RUN_ENDED (ALIVE if there is none). A list that is empty or has no
    RUN_STARTED has no defined permit, so it raises ValueError. The result shares no data with the
    events.
    """
    if not events:
        raise ValueError("cannot reduce an empty event list")
    permit: PermitJSON | None = None
    status = STATUS_ALIVE
    for event in events:
        if event.type == RUN_STARTED:
            permit = event.data["permit"]
        elif event.type == BORDER_CHECK and permit is not None:
            permit = event.data["permit_after"]
        elif event.type == RUN_ENDED:
            status = event.data["status"]
    if permit is None:
        raise ValueError("the event list has no RUN_STARTED event")
    last = events[-1]
    return {
        "place": last.place,
        "step": last.step,
        "spent": last.spent,
        "permit": _copy_permit(permit),
        "status": status,
    }


def to_jsonl(events: Sequence[Event]) -> str:
    """One json.dumps(event, sort_keys=True) per line, every line ended by an LF."""
    return "".join(json.dumps(event.to_dict(), sort_keys=True) + "\n" for event in events)


def write_jsonl(path: str | Path, events: Sequence[Event]) -> None:
    """Write the events as JSONL. newline="\\n" keeps Windows from writing CRLF."""
    with Path(path).open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(to_jsonl(events))


class ReplayMeta(TypedDict):
    """The meta block of a replay file (CONTRACTS section 9)."""

    id: str
    title: str
    scenario: str
    driver: str
    enforce: bool
    harness_cap: int
    task: str
    home_permit: PermitJSON
    ceilings: dict[str, PermitJSON]
    tool_costs: dict[str, int]
    document_text: str
    generated_by: str


class IndexEntry(TypedDict):
    """One entry of index.json."""

    id: str
    title: str
    file: str
    driver: str
    enforce: bool


def replay_document(meta: ReplayMeta, events: Sequence[Event]) -> dict[str, object]:
    """The replay file content: schema version, meta and every event as a plain dict."""
    return {
        "schema_version": SCHEMA_VERSION,
        "meta": dict(meta),
        "events": [event.to_dict() for event in events],
    }


def index_document(entries: Sequence[IndexEntry]) -> dict[str, object]:
    """The index.json content."""
    return {"schema_version": SCHEMA_VERSION, "replays": [dict(entry) for entry in entries]}


def dumps_json(document: Mapping[str, object]) -> str:
    """Sorted keys, indent 2, pure ASCII, exactly one trailing LF."""
    return json.dumps(document, sort_keys=True, indent=2) + "\n"


def write_json(path: str | Path, document: Mapping[str, object]) -> None:
    """Write dumps_json(document). newline="\\n" keeps Windows from writing CRLF."""
    with Path(path).open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(dumps_json(document))
