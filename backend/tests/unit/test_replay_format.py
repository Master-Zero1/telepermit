"""Unit tests for the replay JSON helpers in audit.py (CONTRACTS sections 6 and 9, task 6)."""

from __future__ import annotations

import json
import re
from pathlib import Path

import telepermit
from telepermit.audit import (
    SCHEMA_VERSION,
    dumps_json,
    index_document,
    replay_document,
    to_jsonl,
    write_json,
)
from telepermit.clock import TickClock
from telepermit.drivers.base import Proposal
from telepermit.drivers.scripted import ScriptedDriver
from telepermit.engine import Engine
from telepermit.identity import Authority
from telepermit.permit import Permit
from telepermit.place import Place
from telepermit.scenarios.poisoned_briefing import run_scenario
from telepermit.tools import Tool

META_KEYS = {
    "id",
    "title",
    "scenario",
    "driver",
    "enforce",
    "harness_cap",
    "task",
    "home_permit",
    "ceilings",
    "tool_costs",
    "document_text",
    "generated_by",
}
HOSTILE = 'line1\nline2\r\n"quoted" back\\slash {"type":"KILLED"}\u2028 \u00e9 end'
DOCUMENT = {"b": 1, "a": {"z": [1, 2], "y": "caf\u00e9 \u2028"}, "c": [{"k": "v"}]}


def make_meta() -> dict[str, object]:
    permit = {"allowance": 60, "allowed_actions": ["a"], "lifetime_s": 60.0, "max_steps": 30}
    return {
        "id": "x",
        "title": "t",
        "scenario": "poisoned_briefing",
        "driver": "scripted",
        "enforce": True,
        "harness_cap": 30,
        "task": "a task",
        "home_permit": permit,
        "ceilings": {"library": permit},
        "tool_costs": {"read_document": 1},
        "document_text": "text",
        "generated_by": "scripts/record_replays.py",
    }


def test_schema_version_is_one() -> None:
    assert SCHEMA_VERSION == 1


def test_schema_version_is_defined_once() -> None:
    package = Path(telepermit.__file__).parent
    pattern = re.compile(r"^SCHEMA_VERSION\b.*=", re.MULTILINE)
    hits = [
        path.name
        for path in package.rglob("*.py")
        if pattern.search(path.read_text(encoding="utf-8"))
    ]
    assert hits == ["audit.py"]


def test_dumps_json_is_sorted_indented_ascii() -> None:
    text = dumps_json(DOCUMENT)
    assert text == json.dumps(DOCUMENT, sort_keys=True, indent=2) + "\n"
    assert text.isascii()
    assert text.endswith("}\n")
    assert not text.endswith("\n\n")
    assert "\r" not in text
    assert text.index('"a"') < text.index('"b"') < text.index('"c"')
    assert '\n  "a": {' in text


def test_write_json_uses_lf(tmp_path: Path) -> None:
    path = tmp_path / "doc.json"
    write_json(path, DOCUMENT)
    raw = path.read_bytes()
    assert b"\r" not in raw
    assert raw.endswith(b"\n")
    assert not raw.endswith(b"\n\n")
    assert raw.decode("ascii") == dumps_json(DOCUMENT)
    other = tmp_path / "other.json"
    write_json(str(other), DOCUMENT)
    assert other.read_bytes() == raw


def test_replay_json_round_trip() -> None:
    meta = make_meta()
    events = run_scenario(enforce=True).result.events
    document = replay_document(meta, events)  # type: ignore[arg-type]
    assert json.loads(dumps_json(document)) == document


def test_replay_document_keys() -> None:
    events = run_scenario(enforce=True).result.events
    meta = make_meta()
    document = replay_document(meta, events)  # type: ignore[arg-type]
    assert set(document) == {"schema_version", "meta", "events"}
    assert document["schema_version"] == SCHEMA_VERSION
    assert document["meta"] == meta
    assert document["meta"] is not meta
    assert set(document["meta"]) == META_KEYS  # type: ignore[call-overload]
    assert document["events"] == [event.to_dict() for event in events]


def test_index_document_keys() -> None:
    entry = {
        "id": "x",
        "title": "t",
        "file": "x.json",
        "driver": "scripted",
        "enforce": True,
    }
    document = index_document([entry])  # type: ignore[list-item]
    assert set(document) == {"schema_version", "replays"}
    assert document["schema_version"] == SCHEMA_VERSION
    assert document["replays"] == [entry]
    assert document["replays"][0] is not entry  # type: ignore[index]
    assert index_document([])["replays"] == []


def test_hostile_tool_result_stays_one_line_per_event() -> None:
    """A tool result with newlines, quotes and a fake event stays inside one JSONL line."""
    authority = Authority.from_seed("home-authority", b"test-only-seed")
    identity = authority.issue("agent-1", "tester", 0.0)
    tool = Tool("hostile", 1, "returns hostile text", {}, lambda args: HOSTILE)
    permit = Permit(60.0, 30, 60, frozenset({"hostile"}))
    place = Place(
        "lab",
        {"hostile": tool},
        permit,
        {"home-authority": authority.public_key},
        frozenset({"tester"}),
    )
    engine = Engine(
        {"lab": place},
        identity,
        permit,
        "lab",
        TickClock(0.0),
        True,
        scenario="test",
        driver="scripted",
        task="a task",
    )
    driver = ScriptedDriver([Proposal("hostile", {})], repeat_last=False)
    events = engine.run(driver, "a task", 5).events
    assert events[2].data["result"] == HOSTILE
    text = to_jsonl(events)
    assert text.endswith("\n")
    lines = text[:-1].split("\n")
    assert len(lines) == len(events)
    assert [json.loads(line) for line in lines] == [event.to_dict() for event in events]
