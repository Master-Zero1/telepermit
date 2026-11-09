"""Unit tests for the audit Event model and its helpers (CONTRACTS section 6, task 1.1)."""

from __future__ import annotations

import dataclasses

import pytest

from telepermit.audit import (
    ALLOWANCE_EXCEEDED,
    BORDER_CHECK,
    DENIED,
    EVENT_TYPES,
    FINISHED,
    KILLED,
    NOT_IN_PERMIT,
    PERMIT_FIELD_ORDER,
    RUN_ENDED,
    RUN_STARTED,
    STATUS_ALIVE,
    STATUS_FINISHED,
    STATUS_HARNESS_CAP,
    STATUS_KILLED,
    STATUS_REFUSED,
    STATUSES,
    TOOL_CALL,
    Event,
    narrowed_fields,
    permit_json,
)
from telepermit.permit import Permit
from telepermit.place import ADMIT, OK

SIX_ACTIONS = frozenset(
    {
        "read_document",
        "search_archive",
        "read_records",
        "export_records",
        "go:vault",
        "go:library",
    }
)
HOME = Permit(60.0, 30, 60, SIX_ACTIONS)
VAULT_NARROWED = Permit(60.0, 30, 40, frozenset({"read_records", "go:library"}))

DATA_BY_TYPE: dict[str, dict[str, object]] = {
    RUN_STARTED: {
        "scenario": "test",
        "driver": "scripted",
        "enforce": True,
        "task": "",
        "identity": {
            "agent_id": "a",
            "agent_class": "c",
            "authority": "home",
            "issued_at": 0.0,
            "signature_hex": "00" * 64,
        },
        "permit": permit_json(HOME),
    },
    BORDER_CHECK: {
        "place": "library",
        "via_action": None,
        "decision": ADMIT,
        "reason": OK,
        "permit_after": permit_json(HOME),
        "narrowed_fields": [],
        "cost": 0,
        "explain": "informative",
    },
    TOOL_CALL: {
        "action": "read_document",
        "args": {"name": "briefing-q3"},
        "cost": 1,
        "result": "text",
    },
    DENIED: {"action": "bogus", "reason": NOT_IN_PERMIT, "explain": "informative"},
    KILLED: {
        "reason": ALLOWANCE_EXCEEDED,
        "action": "read_records",
        "limit": 40,
        "observed": 41,
        "explain": "informative",
    },
    FINISHED: {},
    RUN_ENDED: {"status": STATUS_KILLED},
}


def make_event(event_type: str, data: dict[str, object]) -> Event:
    return Event(seq=0, t=0.0, type=event_type, place="library", step=0, spent=0, data=data)


def test_seven_event_types() -> None:
    assert EVENT_TYPES == frozenset(
        {"RUN_STARTED", "BORDER_CHECK", "TOOL_CALL", "DENIED", "KILLED", "FINISHED", "RUN_ENDED"}
    )
    assert set(DATA_BY_TYPE) == set(EVENT_TYPES)
    for event_type, data in DATA_BY_TYPE.items():
        event = make_event(event_type, data)
        assert event.type == event_type
        with pytest.raises(dataclasses.FrozenInstanceError):
            event.seq = 1  # type: ignore[misc]


@pytest.mark.parametrize("bad_type", ["NOPE", "run_started", "", "RUN_STARTED "])
def test_unknown_event_type_raises(bad_type: str) -> None:
    with pytest.raises(ValueError):
        make_event(bad_type, {})


def test_event_to_dict_fields() -> None:
    event = Event(7, 2.5, TOOL_CALL, "vault", 4, 9, dict(DATA_BY_TYPE[TOOL_CALL]))
    as_dict = event.to_dict()
    assert set(as_dict) == {"seq", "t", "type", "place", "step", "spent", "data"}
    assert as_dict["seq"] == 7
    assert as_dict["t"] == 2.5
    assert as_dict["type"] == TOOL_CALL
    assert as_dict["place"] == "vault"
    assert as_dict["step"] == 4
    assert as_dict["spent"] == 9
    assert as_dict["data"] == event.data
    assert as_dict["data"] is not event.data


@pytest.mark.parametrize(
    "permit",
    [
        HOME,
        VAULT_NARROWED,
        Permit(0.0, 0, 0, frozenset()),
        Permit(1.5, 2, 3, frozenset({"b", "a", "c"})),
    ],
)
def test_permit_json_equals_permit_to_json(permit: Permit) -> None:
    assert permit_json(permit) == permit.to_json()
    assert permit_json(permit)["allowed_actions"] == sorted(permit.allowed_actions)


def test_narrowed_fields_order() -> None:
    assert PERMIT_FIELD_ORDER == ("lifetime_s", "max_steps", "allowance", "allowed_actions")
    assert narrowed_fields(HOME, HOME) == []
    assert narrowed_fields(HOME, VAULT_NARROWED) == ["allowance", "allowed_actions"]
    everything = Permit(10.0, 5, 5, frozenset({"read_records"}))
    assert narrowed_fields(HOME, everything) == [
        "lifetime_s",
        "max_steps",
        "allowance",
        "allowed_actions",
    ]
    assert narrowed_fields(HOME, Permit(59.0, 30, 60, HOME.allowed_actions)) == ["lifetime_s"]
    assert narrowed_fields(HOME, Permit(60.0, 29, 60, HOME.allowed_actions)) == ["max_steps"]


def test_statuses_are_the_five() -> None:
    assert (STATUS_ALIVE, STATUS_KILLED, STATUS_FINISHED, STATUS_REFUSED, STATUS_HARNESS_CAP) == (
        "ALIVE",
        "KILLED",
        "FINISHED",
        "REFUSED",
        "HARNESS_CAP",
    )
    assert STATUSES == frozenset({"ALIVE", "KILLED", "FINISHED", "REFUSED", "HARNESS_CAP"})
