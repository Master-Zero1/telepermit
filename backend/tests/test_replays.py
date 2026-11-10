"""Tests for the recorded replay files and the recorder script (CONTRACTS sections 9 and 10).

Every test starts by loading the recorder or reading a committed file, so none can pass on an
empty replay folder. The golden facts are written here independently of the scenario code.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
from types import ModuleType

from telepermit.audit import STATUSES, Event, reduce_events
from telepermit.scenarios.poisoned_briefing import DEMO_SEED

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "record_replays.py"
REPLAY_DIR = REPO_ROOT / "frontend" / "public" / "replays"
ENFORCED_ID = "poisoned-briefing-enforced"
UNENFORCED_ID = "poisoned-briefing-unenforced"
FORGED_ID = "forged-identity-refused"
FORGED_FILE = f"{FORGED_ID}.json"
GENERATED_BY = "scripts/record_replays.py"
KEY_HEX = hashlib.sha256(DEMO_SEED).digest().hex()
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
EVENT_KEYS = {"seq", "t", "type", "place", "step", "spent", "data"}
INDEX_KEYS = {"id", "title", "file", "driver", "enforce"}


def load_recorder() -> ModuleType:
    """Load scripts/record_replays.py at call time (the script is not a package module)."""
    spec = importlib.util.spec_from_file_location("record_replays", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read_index() -> dict[str, object]:
    return json.loads((REPLAY_DIR / "index.json").read_bytes())  # type: ignore[no-any-return]


def read_replay(file_name: str) -> dict[str, object]:
    return json.loads((REPLAY_DIR / file_name).read_bytes())  # type: ignore[no-any-return]


def index_entries() -> list[dict[str, object]]:
    return list(read_index()["replays"])  # type: ignore[call-overload]


def replay_by_id(replay_id: str) -> dict[str, object]:
    for entry in index_entries():
        if entry["id"] == replay_id:
            return read_replay(str(entry["file"]))
    raise AssertionError(f"replay {replay_id} is not in the index")


def events_of(document: dict[str, object]) -> list[dict[str, object]]:
    return list(document["events"])  # type: ignore[call-overload]


def tool_actions(events: list[dict[str, object]]) -> list[object]:
    calls = [event for event in events if event["type"] == "TOOL_CALL"]
    return [call["data"]["action"] for call in calls]  # type: ignore[index]


def test_m1_replays_present() -> None:
    """Milestone M1 is stated over the enforced and unenforced replays."""
    entries = index_entries()
    assert [entry["id"] for entry in entries][:2] == [ENFORCED_ID, UNENFORCED_ID]
    for entry in entries[:2]:
        assert (REPLAY_DIR / str(entry["file"])).read_bytes()


def test_committed_files_match_fresh_recording(tmp_path: Path) -> None:
    """Committed replays are stale (and this fails) if the code changes without re-recording."""
    recorder = load_recorder()
    written = recorder.record_all(tmp_path)
    assert written[-1].name == "index.json"
    for path in written:
        assert path.read_bytes() == (REPLAY_DIR / path.name).read_bytes(), path.name


def test_p4_4_recording_twice_is_byte_identical(tmp_path: Path) -> None:
    """Property P4.4: recording twice gives byte-identical files. Validates: Requirements 4.8"""
    recorder = load_recorder()
    first = recorder.record_all(tmp_path / "first")
    second = recorder.record_all(tmp_path / "second")
    assert [path.name for path in first] == [path.name for path in second]
    assert first[-1].name == "index.json"
    for one, two in zip(first, second, strict=True):
        raw = one.read_bytes()
        assert raw == two.read_bytes(), one.name
        assert b"\r" not in raw
        assert raw.endswith(b"\n")
        assert not raw.endswith(b"\n\n")
        raw.decode("ascii")


def test_every_replay_schema_and_contiguous_seq() -> None:
    index = read_index()
    assert index["schema_version"] == 1
    assert index_entries()
    for entry in index_entries():
        document = read_replay(str(entry["file"]))
        assert set(document) == {"schema_version", "meta", "events"}
        assert document["schema_version"] == 1
        meta = document["meta"]
        assert isinstance(meta, dict)
        assert set(meta) == META_KEYS
        assert meta["id"] == entry["id"]
        events = events_of(document)
        assert events
        assert [event["seq"] for event in events] == list(range(len(events)))
        assert all(set(event) == EVENT_KEYS for event in events)
        assert events[0]["type"] == "RUN_STARTED"
        assert events[-1]["type"] == "RUN_ENDED"
        steps = [event["step"] for event in events]
        spent = [event["spent"] for event in events]
        assert steps == sorted(steps)
        assert spent == sorted(spent)


def test_reduce_events_equals_last_snapshot() -> None:
    assert index_entries()
    for entry in index_entries():
        raw_events = events_of(read_replay(str(entry["file"])))
        events = [Event(**event) for event in raw_events]  # type: ignore[arg-type]
        reduced = reduce_events(events)
        last = events[-1]
        assert reduced["place"] == last.place
        assert reduced["step"] == last.step
        assert reduced["spent"] == last.spent
        assert reduced["status"] == last.data["status"]  # type: ignore[typeddict-item]
        assert reduced["status"] in STATUSES


def test_golden_facts_run_b() -> None:
    document = replay_by_id(ENFORCED_ID)
    events = events_of(document)
    meta = document["meta"]
    assert isinstance(meta, dict)
    assert (meta["enforce"], meta["driver"], meta["harness_cap"]) == (True, "scripted", 30)
    assert len(events) == 20
    killed, ended = events[-2], events[-1]
    assert (killed["type"], ended["type"]) == ("KILLED", "RUN_ENDED")
    assert killed["data"]["reason"] == "ALLOWANCE_EXCEEDED"  # type: ignore[index]
    assert (killed["data"]["limit"], killed["data"]["observed"]) == (40, 41)  # type: ignore[index]
    assert ended["data"] == {"status": "KILLED"}
    assert (ended["step"], ended["spent"]) == (17, 38)
    assert "export_records" not in tool_actions(events)
    assert len([event for event in events if event["type"] == "DENIED"]) == 2


def test_golden_facts_run_a() -> None:
    document = replay_by_id(UNENFORCED_ID)
    events = events_of(document)
    meta = document["meta"]
    assert isinstance(meta, dict)
    assert (meta["enforce"], meta["driver"], meta["harness_cap"]) == (False, "scripted", 30)
    assert len(events) == 32
    ended = events[-1]
    assert ended["data"] == {"status": "HARNESS_CAP"}
    assert (ended["step"], ended["spent"]) == (30, 120)
    assert tool_actions(events).count("export_records") == 2
    assert not [event for event in events if event["type"] in ("DENIED", "KILLED")]


def test_index_matches_files() -> None:
    entries = index_entries()
    ids = [entry["id"] for entry in entries]
    assert ids[:2] == [ENFORCED_ID, UNENFORCED_ID]
    assert len(set(ids)) == len(ids)
    for entry in entries:
        assert set(entry) == INDEX_KEYS
        assert entry["file"] == f"{entry['id']}.json"
        assert (REPLAY_DIR / str(entry["file"])).is_file()


def test_labels_match_driver_in_files_and_index() -> None:
    assert index_entries()
    for entry in index_entries():
        document = read_replay(str(entry["file"]))
        meta = document["meta"]
        assert isinstance(meta, dict)
        started = events_of(document)[0]["data"]
        assert entry["driver"] == meta["driver"] == started["driver"]  # type: ignore[index]
        assert entry["driver"] == "scripted"
        assert entry["enforce"] == meta["enforce"] == started["enforce"]  # type: ignore[index]
        assert str(entry["title"]).endswith("(scripted)")
        assert entry["title"] == meta["title"]


def test_generated_by_is_recorder_literal() -> None:
    assert index_entries()
    for entry in index_entries():
        meta = read_replay(str(entry["file"]))["meta"]
        assert isinstance(meta, dict)
        assert meta["generated_by"] == GENERATED_BY


def test_no_key_hex_in_any_file() -> None:
    """Security invariant 3: the demo private key never appears in a replay file."""
    index_bytes = (REPLAY_DIR / "index.json").read_bytes()
    entries = index_entries()
    assert [entry["id"] for entry in entries][:2] == [ENFORCED_ID, UNENFORCED_ID]
    assert KEY_HEX not in index_bytes.decode("ascii").lower()
    for entry in entries:
        text = (REPLAY_DIR / str(entry["file"])).read_bytes().decode("ascii")
        assert KEY_HEX not in text.lower(), entry["file"]


def test_forged_replay_golden() -> None:
    """Requirement 4.4: Run C has exactly three events and ends REFUSED with BAD_SIGNATURE."""
    document = read_replay(FORGED_FILE)
    events = events_of(document)
    meta = document["meta"]
    assert isinstance(meta, dict)
    assert (meta["id"], meta["enforce"], meta["driver"]) == (FORGED_ID, True, "scripted")
    assert [event["type"] for event in events] == ["RUN_STARTED", "BORDER_CHECK", "RUN_ENDED"]
    assert events[0]["data"]["identity"]["signature_hex"] == "0" * 128  # type: ignore[index]
    border = events[1]
    assert border["place"] == "library"
    assert border["data"]["decision"] == "REFUSE"  # type: ignore[index]
    assert border["data"]["reason"] == "BAD_SIGNATURE"  # type: ignore[index]
    assert events[2]["data"] == {"status": "REFUSED"}


def test_forged_replay_in_index_after_the_m1_replays() -> None:
    index = read_index()
    assert [entry["id"] for entry in index["replays"]] == [  # type: ignore[attr-defined]
        ENFORCED_ID,
        UNENFORCED_ID,
        FORGED_ID,
    ]


def test_forged_replay_is_written_before_the_index(tmp_path: Path) -> None:
    recorder = load_recorder()
    assert [path.name for path in recorder.record_all(tmp_path)] == [
        f"{ENFORCED_ID}.json",
        f"{UNENFORCED_ID}.json",
        FORGED_FILE,
        "index.json",
    ]


def test_forged_replay_labels() -> None:
    """Requirement 4.9: the labels of the forged replay name the scripted driver."""
    document = read_replay(FORGED_FILE)
    meta = document["meta"]
    assert isinstance(meta, dict)
    started = events_of(document)[0]["data"]
    assert meta["driver"] == started["driver"] == "scripted"  # type: ignore[index]
    assert meta["title"] == "Forged identity refused at the border (scripted)"
    assert meta["generated_by"] == GENERATED_BY
    entry = [e for e in index_entries() if e["id"] == FORGED_ID]
    assert [(e["driver"], e["enforce"], e["file"]) for e in entry] == [
        ("scripted", True, FORGED_FILE)
    ]
