"""Unit tests for audit events, reduce_events and JSONL (CONTRACTS section 6, tasks 1.1, 2.1)."""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path

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
    reduce_events,
    to_jsonl,
    write_jsonl,
)
from telepermit.permit import Permit
from telepermit.place import ADMIT, ADMIT_IMPOSED, EXCEEDS_CEILING, OK, REFUSE

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


def border_check(
    place: str,
    via_action: str | None,
    decision: str,
    reason: str,
    after: Permit,
    narrowed: list[str],
    cost: int,
) -> dict[str, object]:
    return {
        "place": place,
        "via_action": via_action,
        "decision": decision,
        "reason": reason,
        "permit_after": permit_json(after),
        "narrowed_fields": narrowed,
        "cost": cost,
        "explain": "informative",
    }


def run_b_events() -> list[Event]:
    """The 20 events of the golden Run B (CONTRACTS section 8), built by hand."""
    events: list[Event] = []

    def add(event_type: str, place: str, step: int, spent: int, data: dict[str, object]) -> None:
        events.append(Event(len(events), float(len(events)), event_type, place, step, spent, data))

    denied = {"action": "export_records", "reason": NOT_IN_PERMIT, "explain": "informative"}
    add(RUN_STARTED, "library", 0, 0, dict(DATA_BY_TYPE[RUN_STARTED]))
    add(BORDER_CHECK, "library", 0, 0, border_check("library", None, ADMIT, OK, HOME, [], 0))
    read = {"action": "read_document", "args": {"name": "briefing-q3"}, "cost": 1, "result": "t"}
    add(TOOL_CALL, "library", 1, 1, read)
    crossing = border_check(
        "vault",
        "go:vault",
        ADMIT_IMPOSED,
        OK,
        VAULT_NARROWED,
        ["allowance", "allowed_actions"],
        1,
    )
    add(BORDER_CHECK, "vault", 2, 2, crossing)
    add(DENIED, "vault", 3, 2, dict(denied))
    add(DENIED, "vault", 4, 2, dict(denied))
    for page in range(1, 13):
        call = {
            "action": "read_records",
            "args": {},
            "cost": 3,
            "result": f"records page {page}",
        }
        add(TOOL_CALL, "vault", 4 + page, 2 + 3 * page, call)
    killed = {
        "reason": ALLOWANCE_EXCEEDED,
        "action": "read_records",
        "limit": 40,
        "observed": 41,
        "explain": "informative",
    }
    add(KILLED, "vault", 17, 38, killed)
    add(RUN_ENDED, "vault", 17, 38, {"status": STATUS_KILLED})
    return events


def test_reduce_events_golden_run_b() -> None:
    """Reducing the golden Run B gives its final snapshot (CONTRACTS section 8)."""
    events = run_b_events()
    assert len(events) == 20
    assert [event.seq for event in events] == list(range(20))
    reduced = reduce_events(events)
    assert reduced == {
        "place": "vault",
        "step": 17,
        "spent": 38,
        "permit": permit_json(VAULT_NARROWED),
        "status": STATUS_KILLED,
    }
    assert reduced["permit"]["allowance"] == 40
    assert reduced["permit"]["allowed_actions"] == ["go:library", "read_records"]


def test_reduce_empty_raises() -> None:
    with pytest.raises(ValueError):
        reduce_events([])


def test_reduce_without_run_started_raises() -> None:
    events = run_b_events()
    with pytest.raises(ValueError):
        reduce_events(events[1:])
    with pytest.raises(ValueError):
        reduce_events([events[-1]])


def test_reduce_no_run_ended_is_alive() -> None:
    reduced = reduce_events(run_b_events()[:6])
    assert reduced["status"] == STATUS_ALIVE
    assert (reduced["place"], reduced["step"], reduced["spent"]) == ("vault", 4, 2)


def test_reduce_permit_sources() -> None:
    events = run_b_events()
    assert reduce_events(events[:1])["permit"] == permit_json(HOME)
    assert reduce_events(events[:2])["permit"] == permit_json(HOME)
    assert reduce_events(events[:4])["permit"] == permit_json(VAULT_NARROWED)
    assert reduce_events(events[:6])["permit"] == permit_json(VAULT_NARROWED)

    refused = border_check("library", "go:library", REFUSE, EXCEEDS_CEILING, VAULT_NARROWED, [], 1)
    after_refusal = [*events[:6], Event(6, 6.0, BORDER_CHECK, "vault", 5, 3, refused)]
    assert reduce_events(after_refusal)["permit"] == permit_json(VAULT_NARROWED)

    narrower = Permit(30.0, 10, 5, frozenset({"read_records"}))
    imposed = border_check("library", "go:library", ADMIT_IMPOSED, OK, narrower, ["lifetime_s"], 1)
    last_wins = [*after_refusal, Event(7, 7.0, BORDER_CHECK, "library", 6, 6, imposed)]
    assert reduce_events(last_wins)["permit"] == permit_json(narrower)
    assert reduce_events(last_wins)["place"] == "library"


def test_reduce_does_not_alias_event_data() -> None:
    events = run_b_events()
    reduced = reduce_events(events)
    reduced["permit"]["allowed_actions"].append("tampered")
    reduced["permit"]["allowance"] = 0
    assert events[3].data["permit_after"]["allowed_actions"] == ["go:library", "read_records"]
    assert events[3].data["permit_after"]["allowance"] == 40


def test_to_jsonl_format() -> None:
    events = run_b_events()[:3]
    events.append(
        Event(
            3,
            3.0,
            DENIED,
            "library",
            2,
            1,
            {"action": "caf\u00e9", "reason": NOT_IN_PERMIT, "explain": "informative"},
        )
    )
    text = to_jsonl(events)
    assert text.endswith("\n")
    assert "\r" not in text
    lines = text.split("\n")
    assert lines[-1] == ""
    assert len(lines) - 1 == len(events)
    for line, event in zip(lines, events, strict=False):
        assert line == json.dumps(event.to_dict(), sort_keys=True)
        assert json.loads(line) == event.to_dict()
    assert text.isascii()
    assert "\\u00e9" in text


def test_to_jsonl_empty() -> None:
    assert to_jsonl([]) == ""


def test_write_jsonl_lf_only(tmp_path: Path) -> None:
    events = run_b_events()
    target = tmp_path / "events.jsonl"
    write_jsonl(target, events)
    raw = target.read_bytes()
    assert b"\r" not in raw
    assert raw.endswith(b"\n")
    assert raw.decode("utf-8") == to_jsonl(events)
