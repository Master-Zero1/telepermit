"""Unit tests for the Gemini driver behind an injected fake client (CONTRACTS section 7).

Spec 6 (gemini-driver), task 1.1. Requirements tested here: 6.1.1, 6.1.4, 6.1.6, 6.1.9,
6.4.3, 6.5.1, 6.5.2, 6.9.1, 6.9.6 (Gemini half), 6.11.5, 6.12.1, 6.12.2, 6.12.6.
"""

from __future__ import annotations

import copy
import inspect
import socket
from collections.abc import Callable, Iterator, Mapping

import pytest

from telepermit.drivers.base import Observation
from telepermit.drivers.llm import SYSTEM_PROMPT, GeminiDriver

MODEL = "fake-model"
BODY_KEYS = {"contents", "systemInstruction", "tools", "toolConfig"}
FORBIDDEN_HOLDERS = {"Engine", "Place", "Tool", "Authority"}

REPLY_1: dict[str, object] = {
    "candidates": [
        {
            "content": {
                "role": "model",
                "parts": [
                    {
                        "functionCall": {
                            "name": "read_document",
                            "args": {"name": "briefing-q3"},
                            "id": "c1",
                        },
                        "thoughtSignature": "sig-A",
                    },
                    {"functionCall": {"name": "go", "args": {"place": "vault"}}},
                ],
            },
        },
    ],
}


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


class FakeGeminiClient:
    """Records `(model, deep copy of body)` per call and returns prepared replies in order."""

    def __init__(self, *replies: Mapping[str, object]) -> None:
        self._replies = list(replies)
        self.calls: list[tuple[str, dict[str, object]]] = []

    def generate_content(self, model: str, body: Mapping[str, object]) -> Mapping[str, object]:
        self.calls.append((model, copy.deepcopy(dict(body))))
        return self._replies.pop(0)


def observation(
    task: str = "T",
    place: str = "library",
    last_result: str | None = None,
    turn: int = 1,
) -> Observation:
    """The worked example's Observation: read_document, search_archive, go:vault, finish."""
    tools: list[dict[str, object]] = [
        {"name": "read_document", "description": "Read a document.", "args": {"name": "str"}},
        {"name": "search_archive", "description": "Search.", "args": {"query": "str"}},
        {"name": "go:vault", "description": "Move to vault.", "args": {}},
        {"name": "finish", "description": "End the run.", "args": {}},
    ]
    return Observation(task, turn, place, tools, last_result)


def test_network_guard_blocks_host_lookup(network_attempts: list[str]) -> None:
    """Requirement 6.12.6: a host name lookup is blocked and the blocker names it."""
    with pytest.raises(RuntimeError, match="network access blocked: getaddrinfo"):
        socket.getaddrinfo("example.invalid", 443)
    assert network_attempts == ["getaddrinfo"]
    network_attempts.clear()


def test_model_is_required() -> None:
    """Requirement 6.5.1: no model argument raises TypeError."""
    client = FakeGeminiClient()
    with pytest.raises(TypeError):
        GeminiDriver(client)  # type: ignore[call-arg]


def test_blank_model_is_rejected_without_a_call() -> None:
    """Requirement 6.5.2: a whitespace-only model raises ValueError and sends nothing."""
    client = FakeGeminiClient()
    with pytest.raises(ValueError):
        GeminiDriver(client, "  ")
    assert client.calls == []


def test_label_and_provider() -> None:
    """Requirements 6.9.1, 6.9.6: label is llm and provider is gemini."""
    assert GeminiDriver.label == "llm"
    assert GeminiDriver.provider == "gemini"


def test_constructor_takes_only_client_and_model() -> None:
    """Requirement 6.11.5: the constructor takes client and model, model has no default."""
    params = inspect.signature(GeminiDriver.__init__).parameters
    assert list(params) == ["self", "client", "model"]
    assert params["model"].default is inspect.Parameter.empty


def test_attributes_hold_no_engine_place_tool_or_authority() -> None:
    """Requirement 6.11.5: the driver keeps only its own state and no runtime objects."""
    driver = GeminiDriver(FakeGeminiClient(), MODEL)
    attributes = vars(driver)
    assert set(attributes) == {"_client", "_model", "_history", "_pending"}
    for name, value in attributes.items():
        held = {cls.__name__ for cls in type(value).__mro__}
        assert not held & FORBIDDEN_HOLDERS, f"{name} holds {held & FORBIDDEN_HOLDERS}"


def test_turn_one_request_matches_the_worked_example() -> None:
    """Requirements 6.1.1, 6.1.4, 6.1.6, 6.1.9, 6.4.3: turn 1 sends the designed body once."""
    client = FakeGeminiClient(REPLY_1)
    GeminiDriver(client, MODEL).propose(observation())

    assert len(client.calls) == 1
    model, body = client.calls[0]
    assert model == MODEL
    assert set(body) == BODY_KEYS
    assert body["contents"] == [
        {"role": "user", "parts": [{"text": "Task: T\nYou are in library."}]},
    ]
    assert body["systemInstruction"] == {"parts": [{"text": SYSTEM_PROMPT}]}
    assert body["tools"] == [
        {
            "functionDeclarations": [
                {
                    "name": "read_document",
                    "description": "Read a document.",
                    "parameters": {
                        "type": "OBJECT",
                        "properties": {"name": {"type": "STRING"}},
                        "required": ["name"],
                    },
                },
                {
                    "name": "search_archive",
                    "description": "Search.",
                    "parameters": {
                        "type": "OBJECT",
                        "properties": {"query": {"type": "STRING"}},
                        "required": ["query"],
                    },
                },
                {
                    "name": "go",
                    "description": "Move to another place.",
                    "parameters": {
                        "type": "OBJECT",
                        "properties": {
                            "place": {"type": "STRING", "format": "enum", "enum": ["vault"]},
                        },
                        "required": ["place"],
                    },
                },
                {
                    "name": "finish",
                    "description": "End the run.",
                    "parameters": {"type": "OBJECT", "properties": {}, "required": []},
                },
            ],
        },
    ]
    assert body["toolConfig"] == {"functionCallingConfig": {"mode": "AUTO"}}
