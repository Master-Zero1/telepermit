"""Property tests for the Gemini driver behind an injected fake client (CONTRACTS section 7).

Spec 6 (gemini-driver). Property P6.1 validates Requirements 6.1.1 to 6.1.10. Property P6.13
validates Requirement 6.5.2.

The network guard is module-scoped: it installs the socket blockers once for the whole module
through `pytest.MonkeyPatch.context()`, so Hypothesis never sees a function-scoped fixture and no
health check is suppressed. Teardown fails the module if any network attempt was recorded.
"""

from __future__ import annotations

import copy
import hashlib
import json
import socket
from collections.abc import Callable, Iterator, Mapping

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from telepermit.drivers import FINISH_ACTION, GO_PREFIX
from telepermit.drivers.base import Observation
from telepermit.drivers.llm import SYSTEM_PROMPT, GeminiDriver
from telepermit.scenarios.poisoned_briefing import (
    DEMO_SEED,
    EXPORT_DESTINATION,
    LIBRARY,
    TASK,
    VAULT,
    run_scenario,
)
from telepermit.tools import (
    BRIEFING_NAME,
    BRIEFING_Q3_TEXT,
    EXPORT_RECORDS,
    READ_DOCUMENT,
    READ_RECORDS,
    SEARCH_ARCHIVE,
)

MODEL = "fake-model"
BODY_KEYS = {"contents", "systemInstruction", "tools", "toolConfig"}
BANNED_WORDS = ("permit", "allowance", "teleclick")
DEFAULT_FINISH_TEXT = "End the run."
GO_TEXT = "Move to another place."
EMPTY_REPLY: dict[str, object] = {"candidates": []}


@pytest.fixture(autouse=True, scope="module")
def network_attempts() -> Iterator[list[str]]:
    """Block the socket entry points for this module and record every attempt."""
    attempts: list[str] = []

    def blocker(operation: str) -> Callable[..., None]:
        def blocked(*args: object, **kwargs: object) -> None:
            attempts.append(operation)
            raise RuntimeError(f"network access blocked: {operation}")

        return blocked

    with pytest.MonkeyPatch.context() as patcher:
        patcher.setattr(socket.socket, "connect", blocker("connect"))
        patcher.setattr(socket.socket, "connect_ex", blocker("connect_ex"))
        patcher.setattr(socket, "create_connection", blocker("create_connection"))
        patcher.setattr(socket, "getaddrinfo", blocker("getaddrinfo"))
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


short_text = st.text(max_size=12)
tool_names = st.text(alphabet="abcdefghijklmnopqrstuvwxyz_", min_size=1, max_size=10).filter(
    lambda name: name != FINISH_ACTION
)
place_names = st.text(alphabet="abcdefghijklmnopqrstuvwxyz", min_size=1, max_size=8)
descriptions = st.one_of(st.none(), short_text)
mapping_args = st.dictionaries(st.text(min_size=1, max_size=6), short_text, min_size=1, max_size=3)
non_mapping_args = st.one_of(
    st.none(),
    short_text,
    st.integers(),
    st.lists(st.text(max_size=4), max_size=3),
)
tool_args = st.one_of(mapping_args, st.just({}), non_mapping_args)


def with_description(entry: dict[str, object], description: str | None) -> dict[str, object]:
    """Add the description key only when one was generated."""
    if description is not None:
        entry["description"] = description
    return entry


@st.composite
def observations(draw: st.DrawFn) -> Observation:
    """0 to 6 Place_Tools, 0 to 3 go entries and one finish entry, in a random order."""
    entries: list[dict[str, object]] = [
        with_description({"name": name, "args": draw(tool_args)}, draw(descriptions))
        for name in draw(st.lists(tool_names, unique=True, max_size=6))
    ]
    entries += [
        {"name": GO_PREFIX + place, "description": f"Move to {place}.", "args": {}}
        for place in draw(st.lists(place_names, unique=True, max_size=3))
    ]
    entries.append(with_description({"name": FINISH_ACTION, "args": {}}, draw(descriptions)))
    ordered = draw(st.permutations(entries))
    last_result = draw(st.one_of(st.none(), short_text))
    return Observation(draw(short_text), 1, draw(short_text), list(ordered), last_result)


def expected_schema(args: object) -> dict[str, object]:
    """One required STRING property per arg name for a dict, else an empty object schema."""
    names = [str(name) for name in args] if isinstance(args, dict) else []
    return {
        "type": "OBJECT",
        "properties": {name: {"type": "STRING"} for name in names},
        "required": names,
    }


def expected_declarations(observation: Observation) -> list[dict[str, object]]:
    """Independent model: Place_Tools in order, then go over the places, then finish."""
    declared: list[dict[str, object]] = []
    places: list[str] = []
    finish_text = DEFAULT_FINISH_TEXT
    for entry in observation.tools:
        name = str(entry["name"])
        if name == FINISH_ACTION:
            finish_text = str(entry.get("description", DEFAULT_FINISH_TEXT))
        elif name.startswith(GO_PREFIX):
            places.append(name[len(GO_PREFIX) :])
        else:
            declared.append(
                {
                    "name": name,
                    "description": str(entry.get("description", "")),
                    "parameters": expected_schema(entry.get("args")),
                }
            )
    if places:
        place_schema = {"type": "STRING", "format": "enum", "enum": places}
        declared.append(
            {
                "name": "go",
                "description": GO_TEXT,
                "parameters": {
                    "type": "OBJECT",
                    "properties": {"place": place_schema},
                    "required": ["place"],
                },
            }
        )
    declared.append(
        {
            "name": FINISH_ACTION,
            "description": finish_text,
            "parameters": {"type": "OBJECT", "properties": {}, "required": []},
        }
    )
    return declared


# Feature: gemini-driver, Property P6.1: The request declares exactly the Observation's actions
@given(observation=observations())
def test_p6_1_request_declares_exactly_the_observation_actions(observation: Observation) -> None:
    """Property P6.1: one propose makes exactly one Fake_Client call with the model, and the body
    holds exactly contents, systemInstruction, tools and toolConfig, where the declarations are the
    Place_Tools in Observation order, then go with the place enum in Observation order only when a
    go entry exists, then finish with its description or the default, mode AUTO, and the system
    instruction is SYSTEM_PROMPT with no Banned_Word.
    Validates: 6.1.1, 6.1.2, 6.1.3, 6.1.4, 6.1.5, 6.1.6, 6.1.7, 6.1.8, 6.1.9, 6.1.10"""
    client = FakeGeminiClient(EMPTY_REPLY)
    GeminiDriver(client, MODEL).propose(observation)

    assert len(client.calls) == 1
    model, body = client.calls[0]
    assert model == MODEL
    assert set(body) == BODY_KEYS

    expected = expected_declarations(observation)
    tools = body["tools"]
    assert isinstance(tools, list)
    assert len(tools) == 1
    declarations = tools[0]["functionDeclarations"]
    assert [item["name"] for item in declarations] == [item["name"] for item in expected]
    assert declarations == expected
    assert declarations[-1]["name"] == FINISH_ACTION
    go_count = sum(1 for entry in observation.tools if str(entry["name"]).startswith(GO_PREFIX))
    place_tool_count = len(observation.tools) - go_count - 1
    assert len(declarations) == place_tool_count + (1 if go_count else 0) + 1

    assert body["toolConfig"] == {"functionCallingConfig": {"mode": "AUTO"}}
    assert body["systemInstruction"] == {"parts": [{"text": SYSTEM_PROMPT}]}
    lowered = json.dumps(body["systemInstruction"]).lower()
    assert not any(word in lowered for word in BANNED_WORDS)


# ASCII and Unicode characters that str.isspace() accepts, so str.strip() removes them.
WHITESPACE = (
    " \t\n\r\x0b\x0c\x1c\x1d\x1e\x1f\x85\xa0\u1680"
    "\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200a"
    "\u2028\u2029\u202f\u205f\u3000"
)
blank_models = st.one_of(st.just(""), st.text(alphabet=WHITESPACE, max_size=12))


# Feature: gemini-driver, Property P6.13: A blank model is rejected at construction
@given(model=blank_models)
def test_p6_13_blank_model_is_rejected_at_construction(model: str) -> None:
    """Property P6.13: for any string made only of whitespace characters, including the empty
    string, GeminiDriver(fake, model) raises ValueError and the Fake_Client records zero calls.
    Validates: 6.5.2"""
    assert model.strip() == ""
    client = FakeGeminiClient()

    with pytest.raises(ValueError):
        GeminiDriver(client, model)

    assert client.calls == []


KEY_HEX = hashlib.sha256(DEMO_SEED).digest().hex()
KEY_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-"
CALL_NAMES = (
    READ_DOCUMENT,
    SEARCH_ARCHIVE,
    READ_RECORDS,
    EXPORT_RECORDS,
    "go",
    FINISH_ACTION,
    "delete_all",
    "send_email",
    "",
)
ARG_NAMES = ("name", "query", "destination", "place", "extra")
ARG_VALUES = (BRIEFING_NAME, EXPORT_DESTINATION, LIBRARY, VAULT, "q3", "")
CALL_IDS = ("c1", "c2", "c3")
REPLY_TEXTS = ("", "Thinking.", "Done.", "Reading the briefing now.")
FIXED_TEXT = "\n".join(
    (SYSTEM_PROMPT, TASK, BRIEFING_Q3_TEXT, DEFAULT_FINISH_TEXT, GO_TEXT)
    + CALL_NAMES
    + ARG_NAMES
    + ARG_VALUES
    + CALL_IDS
    + REPLY_TEXTS
).lower()

api_keys = st.text(alphabet=KEY_ALPHABET, min_size=20, max_size=40).map(lambda tail: "AIza" + tail)


def reply_of(parts: list[dict[str, object]]) -> dict[str, object]:
    """A Gemini reply whose first candidate holds the given parts."""
    return {"candidates": [{"content": {"role": "model", "parts": parts}}]}


FINISH_REPLY = reply_of([{"functionCall": {"name": FINISH_ACTION, "args": {}}}])


@st.composite
def function_call_parts(draw: st.DrawFn) -> dict[str, object]:
    """A Function_Call part named after a scenario action, go, finish or an unknown name."""
    call: dict[str, object] = {
        "name": draw(st.sampled_from(CALL_NAMES)),
        "args": draw(
            st.dictionaries(st.sampled_from(ARG_NAMES), st.sampled_from(ARG_VALUES), max_size=2)
        ),
    }
    if draw(st.booleans()):
        call["id"] = draw(st.sampled_from(CALL_IDS))
    return {"functionCall": call}


text_parts = st.sampled_from(REPLY_TEXTS).map(lambda text: {"text": text})
gemini_replies = st.one_of(
    st.lists(st.one_of(function_call_parts(), text_parts), min_size=1, max_size=3).map(reply_of),
    st.lists(text_parts, min_size=1, max_size=2).map(reply_of),
    st.just(EMPTY_REPLY),
)


# Feature: gemini-driver, Property P6.6: Request bodies carry no key and no hidden run state
@given(replies=st.lists(gemini_replies, min_size=1, max_size=30), api_key=api_keys)
def test_p6_6_request_bodies_carry_no_key_and_no_hidden_run_state(
    replies: list[dict[str, object]], api_key: str
) -> None:
    """Property P6.6: for any sequence of 1 to 30 fake replies run through run_scenario with a
    GeminiDriver for both enforce values, and any generated API key the driver never receives, the
    lower-cased JSON of every request body contains no occurrence of the key, the identity
    signature_hex, sha256(DEMO_SEED).hex() or a Banned_Word.
    Validates: 6.7.3, 6.11.2, 6.11.3"""
    lowered_key = api_key.lower()
    assume(lowered_key not in FIXED_TEXT)

    for enforce in (True, False):
        client = FakeGeminiClient(*copy.deepcopy(replies), FINISH_REPLY)
        run = run_scenario(enforce=enforce, driver=GeminiDriver(client, MODEL))
        signature_hex = str(run.result.events[0].data["identity"]["signature_hex"]).lower()
        assert len(signature_hex) == 128

        assert client.calls
        for model, body in client.calls:
            assert model == MODEL
            text = json.dumps(body).lower()
            assert lowered_key not in text
            assert signature_hex not in text
            assert KEY_HEX not in text
            assert not any(word in text for word in BANNED_WORDS)
