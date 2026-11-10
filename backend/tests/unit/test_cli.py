"""Unit tests for the command line interface (CONTRACTS section 10, task 5)."""

from __future__ import annotations

import hashlib
import io
import json
import socket
from collections.abc import Iterator, Mapping
from pathlib import Path
from types import SimpleNamespace

import pytest

import telepermit.cli as cli
from telepermit.audit import TOOL_CALL, Event
from telepermit.drivers.llm import LLMUnavailableError
from telepermit.scenarios.poisoned_briefing import DEMO_SEED, run_scenario

REPLAY_DIR = Path(__file__).resolve().parents[3] / "frontend" / "public" / "replays"
HEADER = f"{'seq':>3}  {'type':<12}  {'place':<8}  {'step':>4}  {'spent':>5}  summary"
PREFIX_WIDTH = len(HEADER) - len("summary")
KEY_HEX = hashlib.sha256(DEMO_SEED).digest().hex()
API_KEY = "sk-test-0123456789-not-real"
MISSING_BOTH = (
    "error: missing environment variable(s) for --driver llm: AGENT_MODEL, ANTHROPIC_API_KEY"
)
FINISH_REPLY = SimpleNamespace(
    content=[SimpleNamespace(type="tool_use", id="t1", name="finish", input={})]
)


class NetworkBlockedError(AssertionError):
    """Raised by the guard when a test tries to reach the network."""


@pytest.fixture(autouse=True)
def network_calls(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[str]]:
    """Block the socket entry points and record every attempt. Teardown fails if any occurred."""
    attempts: list[str] = []

    def blocker(name: str):  # type: ignore[no-untyped-def]
        def blocked(*args: object, **kwargs: object) -> None:
            attempts.append(name)
            raise NetworkBlockedError(name)

        return blocked

    monkeypatch.setattr(socket.socket, "connect", blocker("connect"))
    monkeypatch.setattr(socket.socket, "connect_ex", blocker("connect_ex"))
    monkeypatch.setattr(socket, "getaddrinfo", blocker("getaddrinfo"))
    monkeypatch.setattr(socket, "create_connection", blocker("create_connection"))
    yield attempts
    assert attempts == [], f"network access attempted: {attempts}"


class FakeClient:
    """A stand-in for the provider client: records requests, returns a reply or raises."""

    def __init__(self, reply: SimpleNamespace | None = None, error: Exception | None = None):
        self.messages = self
        self.calls: list[dict[str, object]] = []
        self._reply = reply
        self._error = error

    def create(self, **kwargs: object) -> SimpleNamespace:
        self.calls.append(kwargs)
        if self._error is not None:
            raise self._error
        assert self._reply is not None
        return self._reply


class ExplodingEnv(Mapping[str, str]):
    """An environment that fails the test on any access."""

    def __getitem__(self, key: str) -> str:
        raise AssertionError(f"the environment was read: {key}")

    def __iter__(self) -> Iterator[str]:
        raise AssertionError("the environment was read")

    def __len__(self) -> int:
        raise AssertionError("the environment was read")


def run_cli(argv: list[str], env: Mapping[str, str] | None = None) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    code = cli.main(argv, env={} if env is None else env, out=out, err=err)
    return code, out.getvalue(), err.getvalue()


def llm_argv() -> list[str]:
    return ["run", "poisoned_briefing", "--enforce", "on", "--driver", "llm"]


def llm_env(model: str = "env-model-x") -> dict[str, str]:
    return {"AGENT_MODEL": model, "ANTHROPIC_API_KEY": API_KEY}


def hostile_event(result: str) -> Event:
    data = {"action": "read_document", "args": {}, "cost": 1, "result": result}
    return Event(1, 1.0, TOOL_CALL, "library", 1, 1, data)  # type: ignore[arg-type]


def test_enforce_on_ends_killed() -> None:
    """Requirement 4.7: with enforcement on the scripted run ends KILLED with an empty outbox."""
    code, out, err = run_cli(["run", "poisoned_briefing", "--enforce", "on"])
    lines = out.splitlines()
    assert (code, err) == (0, "")
    assert lines[-2:] == ["status: KILLED", "outbox: 0"]
    assert len(lines) == 1 + 20 + 2


def test_enforce_off_ends_harness_cap() -> None:
    """Requirement 4.7: with enforcement off the run ends HARNESS_CAP with two exports."""
    code, out, err = run_cli(["run", "poisoned_briefing", "--enforce", "off"])
    lines = out.splitlines()
    assert (code, err) == (0, "")
    assert lines[-2:] == ["status: HARNESS_CAP", "outbox: 2"]
    assert len(lines) == 1 + 32 + 2


def test_timeline_header_and_columns() -> None:
    events = run_scenario(enforce=True).result.events
    lines = cli.format_timeline(events)
    assert lines[0] == HEADER
    assert len(lines) == 1 + len(events)
    first = f"{0:>3}  {'RUN_STARTED':<12}  {'library':<8}  {0:>4}  {0:>5}  "
    assert lines[1] == first + "enforce on, driver scripted"
    summaries = [line[PREFIX_WIDTH:] for line in lines[1:]]
    assert summaries[1] == "ADMIT OK -> library"
    assert summaries[2].startswith("read_document cost 1: Q3 BRIEFING")
    assert summaries[3].startswith("ADMIT_IMPOSED OK -> vault via go:vault narrowed: allowance")
    assert summaries[4] == "export_records NOT_IN_PERMIT"
    assert summaries[-2] == "ALLOWANCE_EXCEEDED limit 40 observed 41"
    assert summaries[-1] == "KILLED"
    assert lines[-1].startswith(f"{19:>3}  {'RUN_ENDED':<12}  {'vault':<8}  {17:>4}  {38:>5}  ")


def test_summary_is_one_line() -> None:
    """A hostile tool result cannot forge timeline lines or inject control characters."""
    hostile = 'a\nb\r\n 99  KILLED  fake\u2028\u00e9 "q"\x1b[31m\ttab'
    lines = cli.format_timeline([hostile_event(hostile)])
    assert len(lines) == 2
    line = lines[1]
    assert line.isascii()
    assert not any(char in line for char in ("\n", "\r", "\x1b", "\t"))
    assert "\\xe9" in line
    assert "  " not in line[PREFIX_WIDTH:]


def test_summary_truncated() -> None:
    prefix = "read_document cost 1: "
    exact = cli.format_timeline([hostile_event("y" * (72 - len(prefix)))])[1][PREFIX_WIDTH:]
    over = cli.format_timeline([hostile_event("y" * (73 - len(prefix)))])[1][PREFIX_WIDTH:]
    long = cli.format_timeline([hostile_event("x" * 500)])[1][PREFIX_WIDTH:]
    assert len(exact) == 72
    assert not exact.endswith("...")
    assert over.endswith("...")
    assert len(over) == len(long) == 72
    assert long.endswith("...")


@pytest.mark.parametrize(
    "argv",
    [
        [],
        ["run"],
        ["run", "poisoned_briefing"],
        ["run", "poisoned_briefing", "--enforce", "maybe"],
        ["run", "unknown_scenario", "--enforce", "on"],
        ["run", "poisoned_briefing", "--enforce", "on", "--driver", "human"],
    ],
)
def test_usage_errors_return_2(argv: list[str]) -> None:
    code, out, err = run_cli(argv)
    assert code == 2
    assert out == ""
    assert "usage" in err.lower()


def test_scripted_run_exception_is_not_caught(monkeypatch: pytest.MonkeyPatch) -> None:
    def broken(**kwargs: object) -> None:
        raise RuntimeError("defect")

    monkeypatch.setattr(cli, "run_scenario", broken)
    with pytest.raises(RuntimeError, match="defect"):
        run_cli(["run", "poisoned_briefing", "--enforce", "on"])


def test_llm_missing_env_names_only() -> None:
    """Requirement 4.6: the message lists the missing names and never a value."""
    code, out, err = run_cli(llm_argv())
    assert (code, out) == (1, "")
    assert err.strip() == MISSING_BOTH
    code, out, err = run_cli(llm_argv(), {"ANTHROPIC_API_KEY": API_KEY})
    assert code == 1
    assert err.strip() == "error: missing environment variable(s) for --driver llm: AGENT_MODEL"
    assert API_KEY not in err
    code, _, err = run_cli(llm_argv(), {"AGENT_MODEL": "env-model-x"})
    assert code == 1
    assert err.strip().endswith(": ANTHROPIC_API_KEY")


def test_llm_blank_env_counts_as_missing() -> None:
    code, _, err = run_cli(llm_argv(), {"AGENT_MODEL": "   ", "ANTHROPIC_API_KEY": API_KEY})
    assert code == 1
    assert err.strip() == "error: missing environment variable(s) for --driver llm: AGENT_MODEL"
    code, _, err = run_cli(llm_argv(), {"AGENT_MODEL": "m", "ANTHROPIC_API_KEY": ""})
    assert code == 1
    assert err.strip().endswith(": ANTHROPIC_API_KEY")


def test_llm_missing_env_builds_no_client(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(api_key: str) -> None:
        raise AssertionError("a client was built although the environment is incomplete")

    monkeypatch.setattr(cli, "build_client", forbidden)
    for env in ({}, {"AGENT_MODEL": "m"}, {"ANTHROPIC_API_KEY": API_KEY}):
        code, _, _ = run_cli(llm_argv(), env)
        assert code == 1


def test_llm_extra_missing_returns_1(monkeypatch: pytest.MonkeyPatch) -> None:
    def unavailable(api_key: str) -> None:
        raise LLMUnavailableError("the llm extra is not installed: run uv sync --extra llm")

    monkeypatch.setattr(cli, "build_client", unavailable)
    code, out, err = run_cli(llm_argv(), llm_env())
    assert (code, out) == (1, "")
    assert "uv sync --extra llm" in err
    assert API_KEY not in err


def test_model_comes_from_env_only(monkeypatch: pytest.MonkeyPatch) -> None:
    client = FakeClient(FINISH_REPLY)
    monkeypatch.setattr(cli, "build_client", lambda api_key: client)
    code, _, _ = run_cli(llm_argv(), llm_env("env-model-x"))
    assert code == 0
    assert [call["model"] for call in client.calls] == ["env-model-x"]


def test_scripted_driver_ignores_env() -> None:
    code, out, _ = run_cli(["run", "poisoned_briefing", "--enforce", "on"], ExplodingEnv())
    assert code == 0
    assert out.splitlines()[-2] == "status: KILLED"


def test_llm_run_with_fake_client_is_labelled_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    """Requirement 4.9: the timeline shows the driver actually used."""
    client = FakeClient(FINISH_REPLY)
    monkeypatch.setattr(cli, "build_client", lambda api_key: client)
    code, out, err = run_cli(llm_argv(), llm_env())
    lines = out.splitlines()
    assert (code, err) == (0, "")
    assert lines[1][PREFIX_WIDTH:] == "enforce on, driver llm"
    assert lines[-2:] == ["status: FINISHED", "outbox: 0"]


def test_llm_abort_prints_type_only(monkeypatch: pytest.MonkeyPatch) -> None:
    client = FakeClient(error=RuntimeError(f"request failed for key {API_KEY}"))
    monkeypatch.setattr(cli, "build_client", lambda api_key: client)
    code, out, err = run_cli(llm_argv(), llm_env())
    assert code == 1
    assert err.strip() == "error: run aborted: RuntimeError (details withheld; see docs)"
    assert API_KEY not in out + err


def test_output_has_no_key_material(monkeypatch: pytest.MonkeyPatch) -> None:
    client = FakeClient(FINISH_REPLY)
    monkeypatch.setattr(cli, "build_client", lambda api_key: client)
    runs = [
        run_cli(["run", "poisoned_briefing", "--enforce", "on"]),
        run_cli(["run", "poisoned_briefing", "--enforce", "off"]),
        run_cli(llm_argv(), llm_env()),
    ]
    for _, out, err in runs:
        assert KEY_HEX not in out + err
        assert API_KEY not in out + err


def test_network_guard_blocks_connections(network_calls: list[str]) -> None:
    """The guard raises for connect, connect_ex, a name lookup and create_connection."""
    try:
        with socket.socket() as sock:
            with pytest.raises(NetworkBlockedError):
                sock.connect(("127.0.0.1", 9))
            with pytest.raises(NetworkBlockedError):
                sock.connect_ex(("127.0.0.1", 9))
        with pytest.raises(NetworkBlockedError):
            socket.getaddrinfo("example.invalid", 80)
        with pytest.raises(NetworkBlockedError):
            socket.create_connection(("example.invalid", 80))
        assert network_calls == ["connect", "connect_ex", "getaddrinfo", "create_connection"]
    finally:
        network_calls.clear()


def out_argv(path: Path, enforce: str = "on") -> list[str]:
    return ["run", "poisoned_briefing", "--enforce", enforce, "--out", str(path)]


def read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_bytes())  # type: ignore[no-any-return]


def test_out_writes_replay(tmp_path: Path) -> None:
    """Requirement 4.7: --out writes a replay after the timeline and says so on the last line."""
    path = tmp_path / "run.json"
    code, out, err = run_cli(out_argv(path))
    assert (code, err) == (0, "")
    assert path.is_file()
    assert out.splitlines()[-3:] == ["status: KILLED", "outbox: 0", f"replay written: {path}"]
    assert set(read_json(path)) == {"schema_version", "meta", "events"}


def test_out_replay_generated_by_cli(tmp_path: Path) -> None:
    path = tmp_path / "run.json"
    code, _, _ = run_cli(out_argv(path))
    assert code == 0
    meta = read_json(path)["meta"]
    assert isinstance(meta, dict)
    assert meta["generated_by"] == "telepermit.cli"
    assert meta["id"] == "poisoned-briefing-enforced"


def test_out_unwritable_returns_1(tmp_path: Path) -> None:
    path = tmp_path / "missing-directory" / "run.json"
    code, out, err = run_cli(out_argv(path))
    assert code == 1
    assert err.startswith("error:")
    assert "status: KILLED" in out
    assert not path.exists()


def test_cli_does_not_write_index(tmp_path: Path) -> None:
    path = tmp_path / "run.json"
    code, _, _ = run_cli(out_argv(path))
    assert code == 0
    assert sorted(item.name for item in tmp_path.iterdir()) == ["run.json"]


def test_llm_out_replay_is_labelled_llm(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Requirement 4.9: a live-model replay says llm in its id, title and driver."""
    client = FakeClient(FINISH_REPLY)
    monkeypatch.setattr(cli, "build_client", lambda api_key: client)
    path = tmp_path / "run.json"
    code, _, _ = run_cli([*llm_argv(), "--out", str(path)], llm_env())
    assert code == 0
    document = read_json(path)
    meta = document["meta"]
    assert isinstance(meta, dict)
    assert meta["id"] == "poisoned-briefing-enforced-llm"
    assert str(meta["title"]).endswith("(live LLM)")
    assert meta["driver"] == "llm"
    assert meta["generated_by"] == "telepermit.cli"
    assert document["events"][0]["data"]["driver"] == "llm"  # type: ignore[index]


@pytest.mark.parametrize(
    ("flag", "replay_id"),
    [("on", "poisoned-briefing-enforced"), ("off", "poisoned-briefing-unenforced")],
)
def test_out_replay_matches_recorder_apart_from_generated_by(
    tmp_path: Path, flag: str, replay_id: str
) -> None:
    path = tmp_path / "run.json"
    code, _, _ = run_cli(out_argv(path, flag))
    assert code == 0
    written = read_json(path)
    recorded = read_json(REPLAY_DIR / f"{replay_id}.json")
    pairs = ((written, "telepermit.cli"), (recorded, "scripts/record_replays.py"))
    for document, expected in pairs:
        meta = document["meta"]
        assert isinstance(meta, dict)
        assert meta.pop("generated_by") == expected
    assert written == recorded


@pytest.mark.parametrize("flag", ["on", "off"])
def test_out_replay_has_schema_and_contiguous_seq(tmp_path: Path, flag: str) -> None:
    path = tmp_path / "run.json"
    code, _, _ = run_cli(out_argv(path, flag))
    assert code == 0
    document = read_json(path)
    assert document["schema_version"] == 1
    meta = document["meta"]
    assert isinstance(meta, dict)
    assert len(meta) == 12
    events = document["events"]
    assert isinstance(events, list)
    assert [event["seq"] for event in events] == list(range(len(events)))
    assert events[0]["type"] == "RUN_STARTED"
    assert events[-1]["type"] == "RUN_ENDED"
