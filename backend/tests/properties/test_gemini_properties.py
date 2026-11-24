"""Property tests for the Gemini driver behind an injected fake client (CONTRACTS section 7).

Spec 6 (gemini-driver). Property P6.1 validates Requirements 6.1.1 to 6.1.10. Property P6.2
validates Requirements 6.2.1 to 6.2.5, 6.3.1 to 6.3.5, 6.11.4 and 6.12.4. Property P6.3 validates
Requirements 6.4.1 to 6.4.6, 6.4.9, 6.4.10, 6.1.10 and 6.12.5. Property P6.4 validates
Requirements 6.4.7 and 6.4.11. Property P6.5 validates Requirement 6.4.8. Property P6.6
validates Requirements 6.7.3, 6.11.2 and 6.11.3. Property P6.13 validates Requirement 6.5.2.

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
from telepermit.drivers.base import Observation, Proposal
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


FINISH_PROPOSAL = Proposal(FINISH_ACTION, {})
SCENARIO_TOOL_NAMES = (READ_DOCUMENT, SEARCH_ARCHIVE, READ_RECORDS, EXPORT_RECORDS)
UNKNOWN_NAMES = ("delete_all", "send_email", "mystery")
FORBIDDEN_TARGETS = (
    "telepermit.engine.Engine.step",
    "telepermit.engine.Engine.run",
    "telepermit.place.Place.execute",
)

non_string_names = st.one_of(
    st.none(), st.integers(), st.booleans(), st.lists(st.integers(), max_size=2)
)
arg_values = st.one_of(
    short_text,
    st.integers(),
    st.floats(allow_nan=False, allow_infinity=False),
    st.booleans(),
    st.lists(st.one_of(st.integers(), short_text), max_size=3),
    st.dictionaries(st.text(max_size=4), st.one_of(st.integers(), short_text), max_size=2),
)
call_args = st.dictionaries(
    st.one_of(st.sampled_from(ARG_NAMES), st.text(max_size=6)), arg_values, max_size=3
)
mapping_text_parts = st.one_of(text_parts, short_text.map(lambda text: {"text": text}))
not_call_parts = st.one_of(
    mapping_text_parts,
    short_text,
    st.integers(),
    st.none(),
    st.sampled_from(({"functionCall": "go"}, {"functionCall": None}, {"functionCall": ["go"]})),
)


@st.composite
def mapping_function_calls(draw: st.DrawFn, place_tools: tuple[str, ...]) -> dict[str, object]:
    """A Function_Call part whose name, args and id are each present, missing or malformed."""
    name_choices = [
        st.sampled_from(("go", FINISH_ACTION, *SCENARIO_TOOL_NAMES, *UNKNOWN_NAMES)),
        tool_names,
        non_string_names,
    ]
    if place_tools:
        name_choices.append(st.sampled_from(place_tools))
    call: dict[str, object] = {}
    if draw(st.integers(min_value=0, max_value=5)):
        call["name"] = draw(st.one_of(*name_choices))
    args_shape = draw(st.integers(min_value=0, max_value=3))
    if args_shape < 2:
        call["args"] = draw(call_args)
    elif args_shape == 2:
        call["args"] = draw(non_mapping_args)
    if draw(st.booleans()):
        call["id"] = draw(st.one_of(st.sampled_from(CALL_IDS), st.integers()))
    return {"functionCall": call}


@st.composite
def one_call_replies(draw: st.DrawFn, place_tools: tuple[str, ...]) -> dict[str, object]:
    """Exactly one Function_Call among parts that are not Function_Calls."""
    before = draw(st.lists(not_call_parts, max_size=2))
    after = draw(st.lists(not_call_parts, max_size=2))
    return reply_of([*before, draw(mapping_function_calls(place_tools)), *after])


@st.composite
def many_call_replies(draw: st.DrawFn, place_tools: tuple[str, ...]) -> dict[str, object]:
    """2 to 4 Function_Calls mixed in any order with parts that are not Function_Calls."""
    calls = draw(st.lists(mapping_function_calls(place_tools), min_size=2, max_size=4))
    others = draw(st.lists(not_call_parts, max_size=3))
    return reply_of(list(draw(st.permutations(calls + others))))


@st.composite
def later_candidate_replies(draw: st.DrawFn, place_tools: tuple[str, ...]) -> dict[str, object]:
    """A first candidate without a Function_Call, then 1 or 2 candidates that hold calls."""
    first_parts = draw(st.lists(not_call_parts, max_size=2))
    firsts: tuple[dict[str, object], ...] = (
        {"content": {"role": "model", "parts": first_parts}},
        {},
        {"content": {"role": "model"}},
    )
    first = draw(st.sampled_from(firsts))
    later_parts = st.lists(mapping_function_calls(place_tools), min_size=1, max_size=2)
    later = [
        {"content": {"role": "model", "parts": draw(later_parts)}}
        for _ in range(draw(st.integers(min_value=1, max_value=2)))
    ]
    return {"candidates": [first, *later]}


@st.composite
def malformed_replies(draw: st.DrawFn, place_tools: tuple[str, ...]) -> dict[str, object]:
    """No candidates, or a malformed step on the path to the parts, with a call placed nearby."""
    call = draw(mapping_function_calls(place_tools))
    content = {"role": "model", "parts": [call]}
    shapes: tuple[dict[str, object], ...] = (
        {},
        {"promptFeedback": {"blockReason": "SAFETY"}},
        {"candidates": []},
        {"candidates": None},
        {"candidates": "candidates"},
        {"candidates": {"0": {"content": content}}},
        {"candidates": [[call], {"content": content}]},
        {"candidates": ["candidate"]},
        {"candidates": [None]},
        {"candidates": [{}]},
        {"candidates": [{"content": None}]},
        {"candidates": [{"content": [call]}]},
        {"candidates": [{"content": "content"}]},
        {"candidates": [{"content": {"role": "model"}}]},
        {"candidates": [{"content": {"parts": None}}]},
        {"candidates": [{"content": {"parts": call}}]},
        {"candidates": [{"content": {"parts": "parts"}}]},
        {"candidates": [{"content": {"parts": []}}]},
    )
    return draw(st.sampled_from(shapes))


@st.composite
def mapping_turns(draw: st.DrawFn) -> tuple[Observation, dict[str, object]]:
    """One Observation and one Fake_Client reply that may name the Observation's Place_Tools."""
    observation = draw(observations())
    place_tools = tuple(
        str(entry["name"])
        for entry in observation.tools
        if str(entry["name"]) != FINISH_ACTION and not str(entry["name"]).startswith(GO_PREFIX)
    )
    reply = draw(
        st.one_of(
            malformed_replies(place_tools),
            st.lists(mapping_text_parts, min_size=1, max_size=3).map(reply_of),
            st.lists(not_call_parts, min_size=1, max_size=3).map(reply_of),
            one_call_replies(place_tools),
            many_call_replies(place_tools),
            later_candidate_replies(place_tools),
        )
    )
    return observation, reply


def expected_proposal(reply: Mapping[str, object]) -> Proposal:
    """Independent model of 6.2 and 6.3: the first Function_Call of candidate 0, else finish."""
    candidates = reply.get("candidates")
    if not isinstance(candidates, list) or not candidates or not isinstance(candidates[0], dict):
        return FINISH_PROPOSAL
    content = candidates[0].get("content")
    parts = content.get("parts") if isinstance(content, dict) else None
    if not isinstance(parts, list):
        return FINISH_PROPOSAL
    calls = [
        part["functionCall"]
        for part in parts
        if isinstance(part, dict) and isinstance(part.get("functionCall"), dict)
    ]
    if not calls:
        return FINISH_PROPOSAL
    raw_name = calls[0].get("name")
    name = raw_name if isinstance(raw_name, str) else ""
    raw_args = calls[0].get("args")
    args = raw_args if isinstance(raw_args, dict) else {}
    if name == "go":
        return Proposal(GO_PREFIX + (str(args["place"]) if "place" in args else ""), {})
    if name == FINISH_ACTION:
        return FINISH_PROPOSAL
    return Proposal(name, {str(key): str(value) for key, value in args.items()})


# Feature: gemini-driver, Property P6.2: Each turn proposes the first Function_Call, else finish
@given(turns=st.lists(mapping_turns(), min_size=1, max_size=6))
def test_p6_2_each_turn_proposes_the_first_function_call_else_finish(
    turns: list[tuple[Observation, dict[str, object]]],
) -> None:
    """Property P6.2: for any run of 1 to 6 turns with generated Observations and Fake_Client
    replies, each propose returns exactly one Proposal equal to an independent model (the first
    Function_Call of the first candidate maps to go, finish or the named action with string args;
    no Function_Call or a malformed reply gives finish), the Fake_Client is called exactly once per
    propose, no exception is raised, and stand-ins for Engine.step, Engine.run and Place.execute
    record zero calls.
    Validates: 6.2.1, 6.2.2, 6.2.3, 6.2.4, 6.2.5, 6.3.1, 6.3.2, 6.3.3, 6.3.4, 6.3.5, 6.11.4,
    6.12.4"""
    expected = [expected_proposal(reply) for _, reply in turns]
    client = FakeGeminiClient(*(copy.deepcopy(reply) for _, reply in turns))
    driver = GeminiDriver(client, MODEL)
    forbidden_calls: list[str] = []

    def stand_in(target: str) -> Callable[..., None]:
        def record(*args: object, **kwargs: object) -> None:
            forbidden_calls.append(target)

        return record

    with pytest.MonkeyPatch.context() as patcher:
        for target in FORBIDDEN_TARGETS:
            patcher.setattr(target, stand_in(target))
        for count, ((observation, _), want) in enumerate(zip(turns, expected, strict=True), 1):
            proposal = driver.propose(observation)
            assert isinstance(proposal, Proposal)
            assert proposal == want
            assert len(client.calls) == count

    assert forbidden_calls == []


NOT_EXECUTED_TEXT = "Not executed: only one action is taken per turn."
TURN_KEYS = {"role", "parts"}


def expected_reply_parts(reply: Mapping[str, object]) -> list[object]:
    """Independent model of Reply_Parts: the parts list of the first candidate, else empty."""
    candidates = reply.get("candidates")
    if not isinstance(candidates, list) or not candidates or not isinstance(candidates[0], dict):
        return []
    content = candidates[0].get("content")
    parts = content.get("parts") if isinstance(content, dict) else None
    return parts if isinstance(parts, list) else []


def expected_responses(parts: list[object], last_result: str | None) -> list[dict[str, object]]:
    """One Function_Response per Function_Call in order: last_result first, then Not executed."""
    responses: list[dict[str, object]] = []
    for part in parts:
        if not isinstance(part, dict) or not isinstance(part.get("functionCall"), dict):
            continue
        call = part["functionCall"]
        name = call.get("name")
        first_text = "" if last_result is None else last_result
        response: dict[str, object] = {
            "name": name if isinstance(name, str) else "",
            "response": {"result": NOT_EXECUTED_TEXT if responses else first_text},
        }
        if isinstance(call.get("id"), str):
            response["id"] = call["id"]
        responses.append({"functionResponse": response})
    return responses


# Feature: gemini-driver, Property P6.3: The History stays well-formed and free of Banned_Words
@given(turns=st.lists(mapping_turns(), min_size=1, max_size=6))
def test_p6_3_history_stays_well_formed_and_free_of_banned_words(
    turns: list[tuple[Observation, dict[str, object]]],
) -> None:
    """Property P6.3: for any run of 1 to 6 turns with the P6.2 generators, every request's
    contents starts with a User_Turn and alternates user and model with no two adjacent User_Turns;
    it grows by one User_Turn and one Model_Turn after a non-empty reply and by no turn after an
    empty one, whose next place text is merged into the last User_Turn; the first User_Turn is one
    text part with the task and the place; each later User_Turn holds one Function_Response per
    Function_Call of the previous Reply_Parts, in order with matching names and ids, the first
    carrying last_result or "" and later ones the Not executed text, then one place text part; and
    when the Observations and replies hold no Banned_Word, no request body holds one.
    Validates: 6.4.1, 6.4.2, 6.4.3, 6.4.4, 6.4.5, 6.4.6, 6.4.9, 6.4.10, 6.1.10, 6.12.5"""
    inputs = [[obs.task, obs.place, obs.last_result, obs.tools, reply] for obs, reply in turns]
    lowered_inputs = json.dumps(inputs).lower()
    assume(not any(word in lowered_inputs for word in BANNED_WORDS))

    client = FakeGeminiClient(*(copy.deepcopy(reply) for _, reply in turns))
    driver = GeminiDriver(client, MODEL)
    first = turns[0][0]
    first_text = {"text": f"Task: {first.task}\nYou are in {first.place}."}
    previous: list[dict[str, object]] = []
    previous_parts: list[object] = []

    for index, (observation, reply) in enumerate(turns):
        driver.propose(observation)
        assert len(client.calls) == index + 1
        body = client.calls[index][1]
        contents = body["contents"]
        assert isinstance(contents, list)
        assert all(isinstance(entry, dict) and set(entry) == TURN_KEYS for entry in contents)
        roles = [entry["role"] for entry in contents]
        assert roles == ["user" if position % 2 == 0 else "model" for position in range(len(roles))]
        assert all(not (a == b == "user") for a, b in zip(roles, roles[1:], strict=False))
        assert contents[0]["parts"][0] == first_text

        if index == 0:
            assert contents == [{"role": "user", "parts": [first_text]}]
        else:
            place_part = {"text": f"You are now in {observation.place}."}
            new_parts = [*expected_responses(previous_parts, observation.last_result), place_part]
            if previous_parts:
                assert len(contents) == len(previous) + 2
                assert contents[: len(previous)] == previous
                assert contents[-1]["parts"] == new_parts
            else:
                assert len(contents) == len(previous)
                assert contents[:-1] == previous[:-1]
                assert contents[-1]["parts"] == [*previous[-1]["parts"], *new_parts]

        lowered_body = json.dumps(body).lower()
        assert not any(word in lowered_body for word in BANNED_WORDS)
        previous, previous_parts = contents, expected_reply_parts(reply)


KNOWN_PART_KEYS = ("text", "functionCall", "thought", "thoughtSignature")

json_values = st.recursive(
    st.one_of(
        st.none(),
        st.booleans(),
        st.integers(),
        st.floats(allow_nan=False, allow_infinity=False),
        short_text,
    ),
    lambda children: st.one_of(
        st.lists(children, max_size=3),
        st.dictionaries(st.text(max_size=6), children, max_size=3),
    ),
    max_leaves=8,
)
well_formed_calls = st.fixed_dictionaries(
    {"name": short_text, "args": st.dictionaries(st.text(max_size=6), json_values, max_size=3)},
    optional={"id": short_text},
)
unknown_part_fields = st.dictionaries(
    st.text(max_size=8).filter(lambda key: key not in KNOWN_PART_KEYS), json_values, max_size=3
)


@st.composite
def echo_dict_parts(draw: st.DrawFn) -> dict[str, object]:
    """A dict part with any of text, functionCall, thought, thoughtSignature and unknown keys."""
    part: dict[str, object] = draw(unknown_part_fields)
    known = draw(
        st.fixed_dictionaries(
            {},
            optional={
                "text": st.one_of(short_text, json_values),
                "functionCall": st.one_of(well_formed_calls, json_values),
                "thought": st.one_of(st.booleans(), json_values),
                "thoughtSignature": st.one_of(st.text(max_size=24), json_values),
            },
        )
    )
    part.update(known)
    return part


echo_parts = st.lists(
    st.one_of(
        echo_dict_parts(),
        short_text,
        st.integers(),
        st.none(),
        st.lists(json_values, max_size=3),
    ),
    min_size=1,
    max_size=5,
)


def parts_reply(parts: list[object]) -> dict[str, object]:
    """A Gemini reply whose first candidate holds the given arbitrary JSON parts."""
    return {"candidates": [{"content": {"role": "model", "parts": parts}}]}


# Feature: gemini-driver, Property P6.4: Reply parts are echoed back verbatim
@given(
    first=observations(),
    second=observations(),
    parts=echo_parts,
    second_reply=st.one_of(gemini_replies, echo_parts.map(parts_reply)),
)
def test_p6_4_reply_parts_are_echoed_back_verbatim(
    first: Observation,
    second: Observation,
    parts: list[object],
    second_reply: dict[str, object],
) -> None:
    """Property P6.4: for any non-empty Reply_Parts list of arbitrary JSON values (dict parts with
    text, functionCall, thought, thoughtSignature and unknown keys holding nested JSON, plus
    non-dict entries), the Model_Turn in the next request equals {"role": "model", "parts": <the
    received list>} with every entry in the received order and every field value equal, and the
    list the Fake_Client returned is not mutated. This checks only the offline half of 6.4.11; the
    live half (the provider accepting the echoed parts, e.g. thoughtSignature) is UNVERIFIED until
    the first live run.
    Validates: 6.4.7, 6.4.11"""
    snapshot = copy.deepcopy(parts)
    client = FakeGeminiClient(parts_reply(parts), second_reply)
    driver = GeminiDriver(client, MODEL)

    driver.propose(first)
    driver.propose(second)

    assert len(client.calls) == 2
    model, body = client.calls[1]
    assert model == MODEL
    contents = body["contents"]
    assert isinstance(contents, list)
    assert len(contents) > 1, "no Model_Turn in the next request"
    assert contents[1] == {"role": "model", "parts": snapshot}
    assert parts == snapshot


SENTINEL = "\u2603SENTINEL\u2603"


def sentinel_json(value: object) -> str:
    """JSON text that keeps non-ASCII characters, so the SENTINEL stays searchable."""
    return json.dumps(value, ensure_ascii=False)


def mutate_body(body: object) -> None:
    """Add a SENTINEL part to every turn and a SENTINEL turn, and change the instruction."""
    if not isinstance(body, dict):
        return
    contents = body.get("contents")
    if isinstance(contents, list):
        for turn in contents:
            parts = turn.get("parts") if isinstance(turn, dict) else None
            if isinstance(parts, list):
                parts.append({"text": SENTINEL})
        contents.append({"role": "user", "parts": [{"text": SENTINEL}]})
    instruction = body.get("systemInstruction")
    if isinstance(instruction, dict):
        parts = instruction.get("parts")
        if isinstance(parts, list):
            for part in parts:
                if isinstance(part, dict):
                    part["text"] = SENTINEL
            parts.append({"text": SENTINEL})
        instruction[SENTINEL] = SENTINEL


def mutate_reply(reply: object) -> None:
    """Add a SENTINEL part to the parts list of every candidate that has one."""
    candidates = reply.get("candidates") if isinstance(reply, dict) else None
    if not isinstance(candidates, list):
        return
    for candidate in candidates:
        content = candidate.get("content") if isinstance(candidate, dict) else None
        parts = content.get("parts") if isinstance(content, dict) else None
        if isinstance(parts, list):
            parts.append({"text": SENTINEL})


class MutatingGeminiClient:
    """Snapshots each body, mutates the received body, and later mutates the reply it returned."""

    def __init__(self, *replies: Mapping[str, object]) -> None:
        self._replies = list(replies)
        self._returned: Mapping[str, object] | None = None
        self.calls: list[tuple[str, dict[str, object]]] = []
        self.snapshot_texts: list[str] = []
        self.kept: list[tuple[Mapping[str, object], dict[str, object]]] = []

    def generate_content(self, model: str, body: Mapping[str, object]) -> Mapping[str, object]:
        snapshot = copy.deepcopy(dict(body))
        self.calls.append((model, snapshot))
        self.snapshot_texts.append(sentinel_json(snapshot))
        mutate_body(body)
        self.kept.append((body, copy.deepcopy(dict(body))))
        self._returned = self._replies.pop(0)
        return self._returned

    def mutate_returned_reply(self) -> None:
        """Called once the driver's propose has returned, so the driver has read the reply."""
        mutate_reply(self._returned)


# Feature: gemini-driver, Property P6.5: Requests and History are isolated copies
@given(turns=st.lists(mapping_turns(), min_size=1, max_size=6))
def test_p6_5_requests_and_history_are_isolated_copies(
    turns: list[tuple[Observation, dict[str, object]]],
) -> None:
    """Property P6.5: for any run of 1 to 6 turns with the P6.2 generators and a Fake_Client that
    snapshots each body, then mutates the received body (a SENTINEL part in every turn, a SENTINEL
    turn in contents, a changed systemInstruction) and, after propose returns, the reply it returned
    (a SENTINEL part in its parts), no later request contains any of the client's mutations, every
    snapshot still serialises to the same SENTINEL-free text it had at call time, and the driver's
    later turns never change a body the client already received beyond the client's own mutations.
    Validates: 6.4.8"""
    inputs = [[obs.task, obs.place, obs.last_result, obs.tools, reply] for obs, reply in turns]
    assume(SENTINEL not in sentinel_json(inputs))

    client = MutatingGeminiClient(*(copy.deepcopy(reply) for _, reply in turns))
    driver = GeminiDriver(client, MODEL)

    for index, (observation, _) in enumerate(turns):
        driver.propose(observation)
        client.mutate_returned_reply()
        assert len(client.calls) == index + 1
        model, snapshot = client.calls[index]
        assert model == MODEL
        assert SENTINEL not in sentinel_json(snapshot), (
            f"request {index + 1} contains the client's mutation"
        )

    for (_, snapshot), text in zip(client.calls, client.snapshot_texts, strict=True):
        assert sentinel_json(snapshot) == text
        assert SENTINEL not in text
    for body, mutated in client.kept:
        assert body == mutated
