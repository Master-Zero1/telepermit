"""Unit tests for the LLM driver behind an injected fake client (CONTRACTS section 7)."""

from __future__ import annotations

import ast
import copy
import socket
import sys
from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace

import pytest

from telepermit.drivers import FINISH_ACTION
from telepermit.drivers import llm as llm_module
from telepermit.drivers.base import Observation, Proposal
from telepermit.drivers.llm import (
    ENV_API_KEY,
    ENV_MODEL,
    GO_TOOL,
    MAX_TOKENS,
    SYSTEM_PROMPT,
    LLMDriver,
    LLMUnavailableError,
    build_client,
)

BANNED_WORDS = ("permit", "allowance", "teleclick")
NOT_EXECUTED = "Not executed: only one action is taken per turn."
TOOL_CHOICE = {"type": "auto", "disable_parallel_tool_use": True}


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
    """Records every request: deep copies in calls, the live objects in refs."""

    def __init__(self, *responses: SimpleNamespace) -> None:
        self.messages = self
        self._responses = list(responses)
        self.calls: list[dict[str, object]] = []
        self.refs: list[dict[str, object]] = []

    def create(self, **kwargs: object) -> SimpleNamespace:
        self.refs.append(kwargs)
        self.calls.append(copy.deepcopy(kwargs))
        return self._responses.pop(0)


def text(value: str) -> SimpleNamespace:
    return SimpleNamespace(type="text", text=value)


def tool_use(block_id: str, name: str, payload: object) -> SimpleNamespace:
    return SimpleNamespace(type="tool_use", id=block_id, name=name, input=payload)


def response(*blocks: SimpleNamespace) -> SimpleNamespace:
    return SimpleNamespace(content=list(blocks))


def observation(
    place: str = "library",
    others: tuple[str, ...] = ("vault",),
    last_result: str | None = None,
    turn: int = 1,
) -> Observation:
    tools: list[dict[str, object]] = [
        {"name": "read_document", "description": "Read a document.", "args": {"name": "str"}},
        {"name": "search_archive", "description": "Search.", "args": {"query": "str"}},
    ]
    tools += [{"name": f"go:{p}", "description": f"Move to {p}.", "args": {}} for p in others]
    tools.append({"name": "finish", "description": "End the run.", "args": {}})
    return Observation("a task", turn, place, tools, last_result)


def tools_of(call: dict[str, object]) -> dict[str, dict[str, object]]:
    tools = call["tools"]
    assert isinstance(tools, list)
    return {str(tool["name"]): tool for tool in tools}


def test_constants() -> None:
    assert ENV_MODEL == "AGENT_MODEL"
    assert ENV_API_KEY == "ANTHROPIC_API_KEY"
    assert MAX_TOKENS == 1024
    assert GO_TOOL == "go"


def test_request_shape() -> None:
    """Requirement 4.5: the request has the designed shape."""
    client = FakeClient(response(tool_use("t1", "finish", {})))
    LLMDriver(client, "some-model").propose(observation())
    (call,) = client.calls
    assert set(call) == {"model", "max_tokens", "system", "tools", "tool_choice", "messages"}
    assert call["model"] == "some-model"
    assert call["max_tokens"] == MAX_TOKENS
    assert call["system"] == SYSTEM_PROMPT
    assert call["tool_choice"] == TOOL_CHOICE
    tools = call["tools"]
    assert isinstance(tools, list)
    assert [tool["name"] for tool in tools] == ["read_document", "search_archive", "go", "finish"]
    by_name = tools_of(call)
    assert by_name["read_document"]["description"] == "Read a document."
    assert by_name["read_document"]["input_schema"] == {
        "type": "object",
        "properties": {"name": {"type": "string"}},
        "required": ["name"],
    }
    finish_schema = by_name["finish"]["input_schema"]
    assert isinstance(finish_schema, dict)
    assert finish_schema["properties"] == {}
    assert len(call["messages"]) == 1  # type: ignore[arg-type]


def test_max_tokens_is_configurable() -> None:
    client = FakeClient(response(tool_use("t1", "finish", {})))
    LLMDriver(client, "m", max_tokens=77).propose(observation())
    assert client.calls[0]["max_tokens"] == 77


def test_go_places_collapse_to_one_tool() -> None:
    client = FakeClient(response(tool_use("t1", "finish", {})))
    LLMDriver(client, "m").propose(observation(others=("vault", "archive")))
    by_name = tools_of(client.calls[0])
    assert [name for name in by_name if name.startswith("go")] == ["go"]
    assert not any(":" in name for name in by_name)
    assert by_name["go"]["input_schema"] == {
        "type": "object",
        "properties": {"place": {"type": "string", "enum": ["vault", "archive"]}},
        "required": ["place"],
    }


def test_no_go_tool_with_single_place() -> None:
    client = FakeClient(response(tool_use("t1", "finish", {})))
    LLMDriver(client, "m").propose(observation(others=()))
    assert list(tools_of(client.calls[0])) == ["read_document", "search_archive", "finish"]


def test_first_message_has_task_and_place() -> None:
    client = FakeClient(response(tool_use("t1", "finish", {})))
    LLMDriver(client, "m").propose(observation(place="library"))
    (message,) = client.calls[0]["messages"]  # type: ignore[misc]
    assert message["role"] == "user"
    (block,) = message["content"]
    assert block["type"] == "text"
    assert "a task" in block["text"]
    assert "library" in block["text"]


def test_tool_results_come_first() -> None:
    client = FakeClient(
        response(text("thinking"), tool_use("t1", "read_document", {"name": "briefing-q3"})),
        response(tool_use("t2", "finish", {})),
    )
    driver = LLMDriver(client, "m")
    driver.propose(observation())
    driver.propose(observation(place="vault", last_result="doc text", turn=2))
    first, assistant, user = client.calls[1]["messages"]  # type: ignore[misc]
    assert (first["role"], assistant["role"], user["role"]) == ("user", "assistant", "user")
    assert assistant["content"] == [
        {"type": "text", "text": "thinking"},
        {
            "type": "tool_use",
            "id": "t1",
            "name": "read_document",
            "input": {"name": "briefing-q3"},
        },
    ]
    assert user["content"][0] == {"type": "tool_result", "tool_use_id": "t1", "content": "doc text"}
    assert user["content"][1]["type"] == "text"
    assert "vault" in user["content"][1]["text"]


def test_missing_last_result_is_empty_string() -> None:
    client = FakeClient(
        response(tool_use("t1", "read_document", {"name": "x"})),
        response(tool_use("t2", "finish", {})),
    )
    driver = LLMDriver(client, "m")
    driver.propose(observation())
    driver.propose(observation(last_result=None, turn=2))
    user = client.calls[1]["messages"][2]  # type: ignore[index]
    assert user["content"][0]["content"] == ""


def test_extra_tool_use_ids_get_fixed_text() -> None:
    client = FakeClient(
        response(
            tool_use("a", "read_document", {"name": "x"}),
            tool_use("b", "search_archive", {"query": "y"}),
        ),
        response(tool_use("c", "finish", {})),
    )
    driver = LLMDriver(client, "m")
    proposal = driver.propose(observation())
    assert proposal == Proposal("read_document", {"name": "x"})
    driver.propose(observation(last_result="result a", turn=2))
    content = client.calls[1]["messages"][2]["content"]  # type: ignore[index]
    assert content[0] == {"type": "tool_result", "tool_use_id": "a", "content": "result a"}
    assert content[1] == {"type": "tool_result", "tool_use_id": "b", "content": NOT_EXECUTED}
    assert content[2]["type"] == "text"


def test_go_response_maps_to_prefixed_action() -> None:
    client = FakeClient(
        response(tool_use("t1", "go", {"place": "vault"})),
        response(tool_use("t2", "go", {})),
    )
    driver = LLMDriver(client, "m")
    assert driver.propose(observation()) == Proposal("go:vault", {})
    assert driver.propose(observation(turn=2)) == Proposal("go:", {})


def test_finish_response() -> None:
    client = FakeClient(response(tool_use("t1", "finish", {})))
    assert LLMDriver(client, "m").propose(observation()) == Proposal(FINISH_ACTION, {})


def test_unknown_tool_passes_through() -> None:
    client = FakeClient(
        response(tool_use("t1", "bogus", {"a": 1, "b": None})),
        response(tool_use("t2", "read_document", "not a dict")),
    )
    driver = LLMDriver(client, "m")
    assert driver.propose(observation()) == Proposal("bogus", {"a": "1", "b": "None"})
    assert driver.propose(observation(turn=2)) == Proposal("read_document", {})


def test_text_only_response_finishes() -> None:
    client = FakeClient(response(text("I am done.")))
    assert LLMDriver(client, "m").propose(observation()) == Proposal(FINISH_ACTION, {})


def test_empty_content_finishes() -> None:
    client = FakeClient(response(), response(tool_use("t1", "finish", {})))
    driver = LLMDriver(client, "m")
    assert driver.propose(observation()) == Proposal(FINISH_ACTION, {})
    driver.propose(observation(turn=2))
    messages = client.calls[1]["messages"]
    assert all(message["content"] for message in messages)  # type: ignore[attr-defined]
    assert all(message["role"] != "assistant" for message in messages)  # type: ignore[attr-defined]


def test_request_messages_are_snapshots() -> None:
    client = FakeClient(
        response(tool_use("t1", "read_document", {"name": "x"})),
        response(tool_use("t2", "finish", {})),
    )
    driver = LLMDriver(client, "m")
    driver.propose(observation())
    driver.propose(observation(turn=2, last_result="r"))
    assert len(client.refs[0]["messages"]) == 1  # type: ignore[arg-type]
    assert client.refs[0]["messages"] == client.calls[0]["messages"]
    assert len(client.refs[1]["messages"]) == 3  # type: ignore[arg-type]


def test_build_client_without_package(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "anthropic", None)
    with pytest.raises(LLMUnavailableError, match="uv sync --extra llm"):
        build_client("not-a-real-key")


def test_system_prompt_has_no_banned_words() -> None:
    lowered = SYSTEM_PROMPT.lower()
    assert SYSTEM_PROMPT.strip()
    assert not any(word in lowered for word in BANNED_WORDS)


def test_no_top_level_anthropic_import() -> None:
    tree = ast.parse(Path(llm_module.__file__).read_text(encoding="utf-8"))

    def imports_anthropic(node: ast.AST) -> bool:
        if isinstance(node, ast.Import):
            return any(alias.name.split(".")[0] == "anthropic" for alias in node.names)
        if isinstance(node, ast.ImportFrom):
            return (node.module or "").split(".")[0] == "anthropic"
        return False

    assert not [node for node in tree.body if imports_anthropic(node)]
    builders = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "build_client"
    ]
    assert len(builders) == 1
    assert any(imports_anthropic(node) for node in ast.walk(builders[0]))


def test_blank_model_rejected() -> None:
    for model in ("", "   "):
        with pytest.raises(ValueError):
            LLMDriver(FakeClient(), model)


def test_label_is_llm() -> None:
    assert LLMDriver.label == "llm"
    assert LLMDriver(FakeClient(), "m").label == "llm"


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
