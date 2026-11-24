"""Unit tests for the `--driver gemini` CLI path (CONTRACTS section 10).

Spec 6 (gemini-driver), task 9.1. Requirements tested here: 6.5.3, 6.5.4, 6.5.5, 6.8.1, 6.8.2,
6.8.3, 6.8.4, 6.8.5, 6.8.6, 6.9.4, 6.10.1, 6.10.2, 6.10.3, 6.10.4, 6.12.1, 6.12.2, 6.12.7.
The client factory is always replaced and a socket guard blocks the network.
"""

from __future__ import annotations

import copy
import io
import json
import socket
from collections.abc import Callable, Iterator, Mapping
from pathlib import Path
from types import SimpleNamespace

import pytest

import telepermit.cli as cli

API_KEY = "AIza" + "QwErTyUiOpAsDfGhJkLzXcVbNm"
MODEL = "fake-model"
HEADER = f"{'seq':>3}  {'type':<12}  {'place':<8}  {'step':>4}  {'spent':>5}  summary"
PREFIX_WIDTH = len(HEADER) - len("summary")
MISSING_PREFIX = "error: missing environment variable(s) for --driver gemini: "
ABORTED = "error: run aborted: {} (details withheld; see docs)\n"
PREVIOUS_BYTES = b"previous replay, must stay\n"
OWN_GEMINI_VARS = {"AGENT_MODEL", "GEMINI_API_KEY"}
OWN_LLM_VARS = {"AGENT_MODEL", "ANTHROPIC_API_KEY"}
FINISH_REPLY: dict[str, object] = {
    "candidates": [
        {
            "content": {
                "role": "model",
                "parts": [{"functionCall": {"name": "finish", "args": {}}}],
            },
            "finishReason": "STOP",
        },
    ],
}
ANTHROPIC_FINISH = SimpleNamespace(
    content=[SimpleNamespace(type="tool_use", id="t1", name="finish", input={})]
)


@pytest.fixture(autouse=True)
def network_attempts(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[str]]:
    """Block the socket entry points and record every attempt. Teardown fails if any occurred."""
    attempts: list[str] = []

    def blocker(operation: str) -> Callable[..., None]:
        def blocked(*args: object, **kwargs: object) -> None:
            attempts.append(operation)
            raise RuntimeError(f"network access blocked: {operation}")

        return blocked

    monkeypatch.setattr(socket.socket, "connect", blocker("connect"))
    monkeypatch.setattr(socket.socket, "connect_ex", blocker("connect_ex"))
    monkeypatch.setattr(socket, "create_connection", blocker("create_connection"))
    monkeypatch.setattr(socket, "getaddrinfo", blocker("getaddrinfo"))
    yield attempts
    if attempts:
        pytest.fail(f"network access attempted: {attempts}")


class KeyLeakError(Exception):
    """A provider-style error whose message holds the API key."""


class FakeGeminiClient:
    """Records `(model, body)` per call; returns Gemini-shaped replies or raises."""

    def __init__(self, reply: Mapping[str, object] | None = None, error: Exception | None = None):
        self.calls: list[tuple[str, dict[str, object]]] = []
        self._reply = reply
        self._error = error

    def generate_content(self, model: str, body: Mapping[str, object]) -> Mapping[str, object]:
        self.calls.append((model, copy.deepcopy(dict(body))))
        if self._error is not None:
            raise self._error
        assert self._reply is not None
        return copy.deepcopy(dict(self._reply))


class FakeFactory:
    """Stands in for `build_gemini_client`: records each key, returns the client or raises."""

    def __init__(self, client: FakeGeminiClient | None = None, error: Exception | None = None):
        self.keys: list[str] = []
        self._client = client
        self._error = error

    def __call__(self, api_key: str) -> FakeGeminiClient:
        self.keys.append(api_key)
        if self._error is not None:
            raise self._error
        assert self._client is not None
        return self._client


class FakeAnthropicClient:
    """A stand-in for the Anthropic client that always answers with `finish`."""

    def __init__(self) -> None:
        self.messages = self

    def create(self, **kwargs: object) -> SimpleNamespace:
        return ANTHROPIC_FINISH


class RecordingEnv(Mapping[str, str]):
    """An environment that records every key looked up through `[]`, `get` or `in`."""

    def __init__(self, values: Mapping[str, str]) -> None:
        self._values = dict(values)
        self.reads: list[str] = []

    def __getitem__(self, key: str) -> str:
        self.reads.append(key)
        return self._values[key]

    def get(self, key: str, default: object = None) -> object:  # type: ignore[override]
        self.reads.append(key)
        return self._values.get(key, default)

    def __contains__(self, key: object) -> bool:
        self.reads.append(str(key))
        return key in self._values

    def __iter__(self) -> Iterator[str]:
        return iter(self._values)

    def __len__(self) -> int:
        return len(self._values)


def run_cli(argv: list[str], env: Mapping[str, str]) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    code = cli.main(argv, env=env, out=out, err=err)
    return code, out.getvalue(), err.getvalue()


def gemini_argv(enforce: str = "on") -> list[str]:
    return ["run", "poisoned_briefing", "--enforce", enforce, "--driver", "gemini"]


def gemini_env() -> dict[str, str]:
    return {"AGENT_MODEL": MODEL, "GEMINI_API_KEY": API_KEY}


def install(monkeypatch: pytest.MonkeyPatch, factory: FakeFactory) -> FakeFactory:
    monkeypatch.setattr(cli, "build_gemini_client", factory)
    return factory


def assert_no_key(*texts: str) -> None:
    for text in texts:
        assert API_KEY not in text


def read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_bytes())  # type: ignore[no-any-return]


# Backend mirror of META_SPECS in frontend/src/validate.ts (required keys and types only).
DRIVERS = ("scripted", "llm")
PERMIT_NUMBERS = ("lifetime_s", "max_steps", "allowance")


def is_string(value: object) -> bool:
    return isinstance(value, str)


def is_number(value: object) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool)


def is_driver(value: object) -> bool:
    return isinstance(value, str) and value in DRIVERS


def is_permit(value: object) -> bool:
    if not isinstance(value, dict):
        return False
    if any(key not in value for key in (*PERMIT_NUMBERS, "allowed_actions")):
        return False
    actions = value["allowed_actions"]
    numbers_ok = all(is_number(value[key]) for key in PERMIT_NUMBERS)
    return numbers_ok and isinstance(actions, list) and all(is_string(a) for a in actions)


def record_of(check: Callable[[object], bool]) -> Callable[[object], bool]:
    def checker(value: object) -> bool:
        return isinstance(value, dict) and all(check(item) for item in value.values())

    return checker


META_SPECS: tuple[tuple[str, Callable[[object], bool]], ...] = (
    ("id", is_string),
    ("title", is_string),
    ("scenario", is_string),
    ("driver", is_driver),
    ("enforce", lambda value: isinstance(value, bool)),
    ("harness_cap", is_number),
    ("task", is_string),
    ("home_permit", is_permit),
    ("ceilings", record_of(is_permit)),
    ("tool_costs", record_of(is_number)),
    ("document_text", is_string),
    ("generated_by", is_string),
)


def meta_errors(meta: object) -> list[str]:
    """The META_SPECS keys that are missing or mistyped. Extra keys are allowed."""
    if not isinstance(meta, dict):
        return ["<not an object>"]
    missing = [key for key, _ in META_SPECS if key not in meta]
    if missing:
        return missing
    return [key for key, check in META_SPECS if not check(meta[key])]


def test_parser_accepts_gemini() -> None:
    """Requirement 6.8.1: `gemini` is a valid --driver value."""
    args = cli._build_parser().parse_args(gemini_argv())
    assert args.driver == "gemini"


def test_parser_default_is_still_scripted() -> None:
    """Requirement 6.8.1: the default driver stays `scripted`."""
    args = cli._build_parser().parse_args(["run", "poisoned_briefing", "--enforce", "on"])
    assert args.driver == "scripted"


@pytest.mark.parametrize(
    ("env", "names"),
    [
        ({}, "AGENT_MODEL, GEMINI_API_KEY"),
        ({"AGENT_MODEL": "", "GEMINI_API_KEY": ""}, "AGENT_MODEL, GEMINI_API_KEY"),
        ({"AGENT_MODEL": " \t", "GEMINI_API_KEY": "\n "}, "AGENT_MODEL, GEMINI_API_KEY"),
        ({"GEMINI_API_KEY": API_KEY}, "AGENT_MODEL"),
        ({"AGENT_MODEL": "   ", "GEMINI_API_KEY": API_KEY}, "AGENT_MODEL"),
        ({"AGENT_MODEL": MODEL}, "GEMINI_API_KEY"),
        ({"AGENT_MODEL": MODEL, "GEMINI_API_KEY": " \t\n"}, "GEMINI_API_KEY"),
        ({"AGENT_MODEL": MODEL, "ANTHROPIC_API_KEY": API_KEY}, "GEMINI_API_KEY"),
    ],
)
def test_missing_variables_stop_before_factory(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, env: dict[str, str], names: str
) -> None:
    """Requirements 6.8.3, 6.5.3: one stderr line naming the missing variables, nothing else."""
    factory = install(monkeypatch, FakeFactory(FakeGeminiClient(FINISH_REPLY)))
    path = tmp_path / "run.json"
    code, out, err = run_cli([*gemini_argv(), "--out", str(path)], env)
    assert (code, out) == (1, "")
    assert err == MISSING_PREFIX + names + "\n"
    assert factory.keys == []
    assert not path.exists()
    assert_no_key(out, err)


def test_factory_error_prints_type_only(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Requirement 6.8.5: a failing factory gives one line with the type name, exit 1."""
    factory = install(monkeypatch, FakeFactory(error=KeyLeakError(f"bad key {API_KEY}")))
    path = tmp_path / "run.json"
    code, out, err = run_cli([*gemini_argv(), "--out", str(path)], gemini_env())
    assert (code, out) == (1, "")
    assert err == "error: KeyLeakError while building the Gemini client\n"
    assert factory.keys == [API_KEY]
    assert not path.exists()
    assert_no_key(out, err)


def test_run_exception_withholds_details(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Requirements 6.8.6, 6.10.1 to 6.10.4: type name only, no stdout, --out file untouched."""
    client = FakeGeminiClient(error=KeyLeakError(f"request failed for key {API_KEY}"))
    install(monkeypatch, FakeFactory(client))
    path = tmp_path / "run.json"
    path.write_bytes(PREVIOUS_BYTES)
    code, out, err = run_cli([*gemini_argv(), "--out", str(path)], gemini_env())
    assert (code, out) == (1, "")
    assert err == ABORTED.format("KeyLeakError")
    assert len(client.calls) == 1
    assert path.read_bytes() == PREVIOUS_BYTES
    assert_no_key(out, err)


def test_full_run_writes_gemini_replay(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Requirements 6.8.2, 6.8.4, 6.5.4: timeline, status, outbox, exit 0, labelled replay."""
    client = FakeGeminiClient(FINISH_REPLY)
    factory = install(monkeypatch, FakeFactory(client))
    path = tmp_path / "run.json"
    code, out, err = run_cli([*gemini_argv(), "--out", str(path)], gemini_env())
    lines = out.splitlines()
    assert (code, err) == (0, "")
    assert lines[0] == HEADER
    assert lines[1][PREFIX_WIDTH:] == "enforce on, driver llm"
    assert lines[-3:] == ["status: FINISHED", "outbox: 0", f"replay written: {path}"]
    assert factory.keys == [API_KEY]
    assert [model for model, _ in client.calls] == [MODEL]
    document = read_json(path)
    meta = document["meta"]
    assert isinstance(meta, dict)
    assert meta["id"] == "poisoned-briefing-enforced-gemini"
    assert str(meta["title"]).endswith("(Gemini live LLM)")
    assert meta["driver"] == "llm"
    assert meta["provider"] == "gemini"
    assert meta["generated_by"] == "telepermit.cli"
    assert document["events"][0]["data"]["driver"] == "llm"  # type: ignore[index]
    assert_no_key(out, err, path.read_text(encoding="utf-8"))


def test_gemini_replay_passes_frontend_meta_specs(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Requirement 6.9.4: the frontend meta rules accept the replay unchanged."""
    install(monkeypatch, FakeFactory(FakeGeminiClient(FINISH_REPLY)))
    path = tmp_path / "run.json"
    code, _, _ = run_cli([*gemini_argv(), "--out", str(path)], gemini_env())
    assert code == 0
    document = read_json(path)
    assert meta_errors(document["meta"]) == []
    assert is_driver(document["events"][0]["data"]["driver"])  # type: ignore[index]


@pytest.mark.parametrize(
    ("change", "expected"),
    [({"driver": "gemini"}, ["driver"]), ({"harness_cap": True}, ["harness_cap"])],
)
def test_meta_mirror_rejects_bad_meta(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, change: dict[str, object], expected: list[str]
) -> None:
    """The mirror is not vacuous: a wrong driver or type and a missing key are reported."""
    install(monkeypatch, FakeFactory(FakeGeminiClient(FINISH_REPLY)))
    path = tmp_path / "run.json"
    assert run_cli([*gemini_argv(), "--out", str(path)], gemini_env())[0] == 0
    meta = read_json(path)["meta"]
    assert isinstance(meta, dict)
    assert meta_errors({**meta, **change}) == expected
    assert meta_errors({key: value for key, value in meta.items() if key != "task"}) == ["task"]


def test_unwritable_out_returns_1(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Requirement 6.8.4: a failed replay write keeps the other drivers' exit code 1."""
    install(monkeypatch, FakeFactory(FakeGeminiClient(FINISH_REPLY)))
    path = tmp_path / "missing-directory" / "run.json"
    code, out, err = run_cli([*gemini_argv(), "--out", str(path)], gemini_env())
    assert code == 1
    assert err.startswith("error:")
    assert "status: FINISHED" in out
    assert not path.exists()
    assert_no_key(out, err)


def test_gemini_reads_from_process_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Requirements 6.12.7, 6.5.3: fake values set for this test only, stripped before use."""
    monkeypatch.setenv("AGENT_MODEL", f"  {MODEL}\t")
    monkeypatch.setenv("GEMINI_API_KEY", f"\n{API_KEY}  ")
    client = FakeGeminiClient(FINISH_REPLY)
    factory = install(monkeypatch, FakeFactory(client))
    out, err = io.StringIO(), io.StringIO()
    code = cli.main(gemini_argv(), out=out, err=err)
    assert (code, err.getvalue()) == (0, "")
    assert factory.keys == [API_KEY]
    assert [model for model, _ in client.calls] == [MODEL]
    assert_no_key(out.getvalue(), err.getvalue())


def test_gemini_never_reads_anthropic_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Requirement 6.5.4: the gemini path reads only AGENT_MODEL and GEMINI_API_KEY."""
    install(monkeypatch, FakeFactory(FakeGeminiClient(FINISH_REPLY)))
    env = RecordingEnv({**gemini_env(), "ANTHROPIC_API_KEY": "sk-not-for-gemini"})
    code, out, err = run_cli(gemini_argv(), env)
    assert code == 0
    assert "ANTHROPIC_API_KEY" not in env.reads
    assert set(env.reads) <= OWN_GEMINI_VARS
    assert_no_key(out, err)


def test_llm_never_reads_gemini_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Requirement 6.5.5: the Anthropic path leaves GEMINI_API_KEY unread."""
    monkeypatch.setattr(cli, "build_client", lambda api_key: FakeAnthropicClient())
    env = RecordingEnv(
        {"AGENT_MODEL": MODEL, "ANTHROPIC_API_KEY": "sk-test-not-real", "GEMINI_API_KEY": API_KEY}
    )
    argv = ["run", "poisoned_briefing", "--enforce", "on", "--driver", "llm"]
    code, out, err = run_cli(argv, env)
    assert code == 0
    assert "GEMINI_API_KEY" not in env.reads
    assert set(env.reads) <= OWN_LLM_VARS
    assert_no_key(out, err)
