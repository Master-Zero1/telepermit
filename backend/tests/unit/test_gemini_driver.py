"""Unit tests for the Gemini driver behind an injected fake client (CONTRACTS section 7).

Spec 6 (gemini-driver), task 1.1. Requirements tested here: 6.1.1, 6.1.4, 6.1.6, 6.1.9,
6.4.3, 6.5.1, 6.5.2, 6.9.1, 6.9.6 (Gemini half), 6.11.5, 6.12.1, 6.12.2, 6.12.6.
Task 3.1 adds response mapping: 6.2.1 to 6.2.5 and 6.3.1 to 6.3.5.
Task 4.1 adds the History examples: 6.4.1, 6.4.2, 6.4.4, 6.4.5, 6.4.6, 6.4.8, 6.4.10.
"""

from __future__ import annotations

import copy
import inspect
import socket
from collections.abc import Callable, Iterator, Mapping

import pytest

from telepermit.drivers.base import Observation, Proposal
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


FINISH = Proposal("finish", {})
REPLY_2_BLOCKED: dict[str, object] = {"promptFeedback": {"blockReason": "SAFETY"}}
REPLY_3: dict[str, object] = {
    "candidates": [
        {"content": {"parts": [{"text": "Done."}, {"functionCall": {"name": "finish"}}]}},
    ],
}


def reply_of(*parts: object) -> dict[str, object]:
    """A reply whose first and only candidate holds the given parts."""
    return {"candidates": [{"content": {"role": "model", "parts": list(parts)}}]}


def call_part(function_call: Mapping[str, object]) -> dict[str, object]:
    """A Function_Call part wrapping the given `functionCall` value."""
    return {"functionCall": dict(function_call)}


def test_worked_example_proposals() -> None:
    """Requirements 6.2.1, 6.3.1, 6.3.2: the worked example's three replies map as designed."""
    client = FakeGeminiClient(REPLY_1, REPLY_2_BLOCKED, REPLY_3)
    driver = GeminiDriver(client, MODEL)
    proposals = [
        driver.propose(observation()),
        driver.propose(observation(last_result="Q3 BRIEFING. ...", turn=2)),
        driver.propose(observation(turn=3)),
    ]
    assert proposals == [
        Proposal("read_document", {"name": "briefing-q3"}),
        FINISH,
        FINISH,
    ]
    assert len(client.calls) == 3


@pytest.mark.parametrize(
    ("reply", "expected"),
    [
        pytest.param(
            reply_of(call_part({"name": "go", "args": {}})),
            Proposal("go:", {}),
            id="go-without-place",
        ),
        pytest.param(
            reply_of(call_part({"name": "go", "args": {"place": "vault", "extra": "x"}})),
            Proposal("go:vault", {}),
            id="go-drops-extra-args",
        ),
        pytest.param(
            reply_of(call_part({"name": "finish", "args": {"reason": "done"}})),
            FINISH,
            id="finish-drops-args",
        ),
        pytest.param(
            reply_of(
                call_part(
                    {
                        "name": "mystery",
                        "args": {"n": 3, "b": True, "l": [1, 2], "d": {"k": "v"}},
                    },
                ),
            ),
            Proposal("mystery", {"n": "3", "b": "True", "l": "[1, 2]", "d": "{'k': 'v'}"}),
            id="unknown-name-str-forms",
        ),
        pytest.param(
            reply_of(call_part({"args": {"x": "y"}})),
            Proposal("", {"x": "y"}),
            id="missing-name",
        ),
        pytest.param(
            reply_of(call_part({"name": 7, "args": {"x": "y"}})),
            Proposal("", {"x": "y"}),
            id="non-string-name",
        ),
        pytest.param(
            reply_of(call_part({"name": "read_document", "args": "briefing-q3"})),
            Proposal("read_document", {}),
            id="args-not-object",
        ),
        pytest.param(
            {
                "candidates": [
                    {"content": {"parts": [{"text": "thinking"}]}},
                    {"content": {"parts": [call_part({"name": "read_document", "args": {}})]}},
                ],
            },
            FINISH,
            id="calls-only-in-second-candidate",
        ),
        pytest.param(
            {"candidates": {"0": {"content": {"parts": [call_part({"name": "go"})]}}}},
            FINISH,
            id="candidates-not-list",
        ),
        pytest.param(
            {"candidates": [["not", "a", "dict"]]},
            FINISH,
            id="first-candidate-not-dict",
        ),
        pytest.param(
            {"candidates": [{"content": [call_part({"name": "go"})]}]},
            FINISH,
            id="content-not-dict",
        ),
        pytest.param(
            {"candidates": [{"content": {"parts": {"functionCall": {"name": "go"}}}}]},
            FINISH,
            id="parts-not-list",
        ),
    ],
)
def test_response_mapping(reply: Mapping[str, object], expected: Proposal) -> None:
    """Requirements 6.2.2 to 6.2.5, 6.3.4, 6.3.5: each reply maps to its Proposal."""
    client = FakeGeminiClient(reply)
    proposal = GeminiDriver(client, MODEL).propose(observation())
    assert proposal == expected
    assert len(client.calls) == 1


BRIEFING = "Q3 BRIEFING. ..."
FIRST_USER_TURN: dict[str, object] = {
    "role": "user",
    "parts": [{"text": "Task: T\nYou are in library."}],
}
MODEL_TURN_1: dict[str, object] = {
    "role": "model",
    "parts": [
        {
            "functionCall": {"name": "read_document", "args": {"name": "briefing-q3"}, "id": "c1"},
            "thoughtSignature": "sig-A",
        },
        {"functionCall": {"name": "go", "args": {"place": "vault"}}},
    ],
}


def turn_two_contents(result: str) -> list[dict[str, object]]:
    """The worked example's turn 2 `contents`, with `result` in the first Function_Response."""
    return [
        copy.deepcopy(FIRST_USER_TURN),
        copy.deepcopy(MODEL_TURN_1),
        {
            "role": "user",
            "parts": [
                {
                    "functionResponse": {
                        "name": "read_document",
                        "id": "c1",
                        "response": {"result": result},
                    },
                },
                {
                    "functionResponse": {
                        "name": "go",
                        "response": {
                            "result": "Not executed: only one action is taken per turn.",
                        },
                    },
                },
                {"text": "You are now in library."},
            ],
        },
    ]


def test_turn_two_request_matches_the_worked_example() -> None:
    """Requirements 6.4.1, 6.4.4, 6.4.6: turn 2 echoes the Model_Turn and answers both calls."""
    client = FakeGeminiClient(copy.deepcopy(REPLY_1), copy.deepcopy(REPLY_2_BLOCKED))
    driver = GeminiDriver(client, MODEL)
    driver.propose(observation())
    driver.propose(observation(last_result=BRIEFING, turn=2))

    assert len(client.calls) == 2
    assert client.calls[1][1]["contents"] == turn_two_contents(BRIEFING)


def test_turn_three_merges_into_the_last_user_turn_after_an_empty_reply() -> None:
    """Requirements 6.4.2, 6.4.5, 6.4.10: after a blocked reply, merge into the User_Turn."""
    client = FakeGeminiClient(
        copy.deepcopy(REPLY_1),
        copy.deepcopy(REPLY_2_BLOCKED),
        copy.deepcopy(REPLY_3),
    )
    driver = GeminiDriver(client, MODEL)
    driver.propose(observation())
    driver.propose(observation(last_result=BRIEFING, turn=2))
    driver.propose(observation(turn=3))

    assert len(client.calls) == 3
    contents = client.calls[2][1]["contents"]
    expected = turn_two_contents(BRIEFING)
    last_parts = expected[-1]["parts"]
    assert isinstance(last_parts, list)
    last_parts.append({"text": "You are now in library."})
    assert contents == expected
    assert isinstance(contents, list)
    assert [entry["role"] for entry in contents] == ["user", "model", "user"]
    assert contents[-1]["parts"][-2:] == [
        {"text": "You are now in library."},
        {"text": "You are now in library."},
    ]


def test_none_last_result_gives_empty_first_response() -> None:
    """Requirement 6.4.6: a null `last_result` is sent as `""` in the first Function_Response."""
    client = FakeGeminiClient(copy.deepcopy(REPLY_1), copy.deepcopy(REPLY_2_BLOCKED))
    driver = GeminiDriver(client, MODEL)
    driver.propose(observation())
    driver.propose(observation(last_result=None, turn=2))

    assert client.calls[1][1]["contents"] == turn_two_contents("")


class MutatingFakeGeminiClient(FakeGeminiClient):
    """Records like FakeGeminiClient, then mutates the body object it received."""

    def generate_content(self, model: str, body: Mapping[str, object]) -> Mapping[str, object]:
        reply = super().generate_content(model, body)
        contents = body["contents"]
        assert isinstance(contents, list)
        first_parts = contents[0]["parts"]
        assert isinstance(first_parts, list)
        first_parts.append({"text": "INJECTED"})
        contents.append({"role": "user", "parts": [{"text": "EXTRA"}]})
        tools = body["tools"]
        assert isinstance(tools, list)
        tools.clear()
        return reply


def test_client_mutating_its_request_does_not_change_the_next_request() -> None:
    """Requirement 6.4.8: client changes to a received body never reach the History."""
    client = MutatingFakeGeminiClient(copy.deepcopy(REPLY_1), copy.deepcopy(REPLY_2_BLOCKED))
    driver = GeminiDriver(client, MODEL)
    driver.propose(observation())
    driver.propose(observation(last_result=BRIEFING, turn=2))

    assert len(client.calls) == 2
    assert client.calls[0][1]["contents"] == [FIRST_USER_TURN]
    assert client.calls[1][1]["contents"] == turn_two_contents(BRIEFING)
