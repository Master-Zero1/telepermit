"""Property tests for the LLM driver (CONTRACTS section 7)."""

from __future__ import annotations

import copy
import hashlib
import json
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

from hypothesis import given
from hypothesis import strategies as st

from telepermit.drivers import FINISH_ACTION, GO_PREFIX
from telepermit.drivers.base import Observation, Proposal
from telepermit.drivers.llm import MAX_TOKENS, LLMDriver
from telepermit.engine import Engine
from telepermit.place import Place
from telepermit.scenarios.poisoned_briefing import DEMO_SEED

KEY_HEX = hashlib.sha256(DEMO_SEED).digest().hex()
BANNED_WORDS = ("permit", "allowance", "teleclick")
TOOL_CHOICE = {"type": "auto", "disable_parallel_tool_use": True}
NOT_EXECUTED = "Not executed: only one action is taken per turn."
MODEL = "some-model"

safe_text = st.text(alphabet="abcxyz 0123", max_size=6)
place_tools = st.dictionaries(
    st.sampled_from(["read_document", "search_archive", "read_records"]),
    st.lists(st.text(alphabet="abcxyz", min_size=1, max_size=5), unique=True, max_size=3),
    max_size=3,
)
other_places = st.lists(st.sampled_from(["vault", "archive", "annex"]), unique=True, max_size=3)
text_block = st.tuples(st.just("text"), safe_text)
tool_block = st.tuples(
    st.just("tool_use"),
    st.sampled_from(["read_document", "search_archive", "go", "finish", "bogus"]),
    st.one_of(
        st.dictionaries(safe_text, st.one_of(safe_text, st.integers(0, 99)), max_size=3),
        st.just("not a dict"),
    ),
)
responses = st.lists(st.one_of(text_block, tool_block), min_size=1, max_size=3)
turns = st.lists(st.tuples(responses, st.one_of(st.none(), safe_text)), min_size=1, max_size=6)


class FakeClient:
    def __init__(self, replies: list[SimpleNamespace]) -> None:
        self.messages = self
        self._replies = list(replies)
        self.calls: list[dict[str, object]] = []

    def create(self, **kwargs: object) -> SimpleNamespace:
        self.calls.append(copy.deepcopy(kwargs))
        return self._replies.pop(0)


def build_reply(blocks: list[tuple[object, ...]], turn: int) -> SimpleNamespace:
    content = []
    for index, block in enumerate(blocks):
        if block[0] == "text":
            content.append(SimpleNamespace(type="text", text=block[1]))
        else:
            ident = f"tu{turn}_{index}"
            content.append(
                SimpleNamespace(type="tool_use", id=ident, name=block[1], input=block[2])
            )
    return SimpleNamespace(content=content)


def expected_proposal(blocks: list[tuple[object, ...]]) -> Proposal:
    for block in blocks:
        if block[0] != "tool_use":
            continue
        name, payload = block[1], block[2]
        args = payload if isinstance(payload, dict) else {}
        if name == "go":
            return Proposal(GO_PREFIX + str(args["place"]) if "place" in args else GO_PREFIX, {})
        if name == "finish":
            return Proposal(FINISH_ACTION, {})
        return Proposal(str(name), {str(k): str(v) for k, v in args.items()})
    return Proposal(FINISH_ACTION, {})


def make_observation(
    tools: dict[str, list[str]], others: list[str], last_result: str | None, turn: int
) -> Observation:
    entries: list[dict[str, object]] = [
        {"name": name, "description": "d", "args": {arg: "str" for arg in args}}
        for name, args in tools.items()
    ]
    entries += [{"name": f"go:{p}", "description": f"Move to {p}.", "args": {}} for p in others]
    entries.append({"name": FINISH_ACTION, "description": "End the run.", "args": {}})
    return Observation("a task", turn, "library", entries, last_result)


def check_request(call: dict[str, object], tools: dict[str, list[str]], others: list[str]) -> None:
    assert call["model"] == MODEL
    assert call["max_tokens"] == MAX_TOKENS
    assert call["tool_choice"] == TOOL_CHOICE
    sent = call["tools"]
    assert isinstance(sent, list)
    names = [tool["name"] for tool in sent]
    assert names == [*tools, *(["go"] if others else []), FINISH_ACTION]
    for tool in sent:
        if tool["name"] == "go":
            assert tool["input_schema"]["properties"]["place"]["enum"] == others
    lowered = json.dumps(call, sort_keys=True).lower()
    assert not any(word in lowered for word in BANNED_WORDS)
    assert KEY_HEX not in lowered


def check_history(messages: list[dict[str, Any]]) -> None:
    roles = [message["role"] for message in messages]
    assert roles == ["user", "assistant"] * (len(roles) // 2) + ["user"] * (len(roles) % 2)
    for before, after in zip(messages, messages[1:], strict=False):
        if after["role"] != "user":
            continue
        ids = [block["id"] for block in before["content"] if block["type"] == "tool_use"]
        content = after["content"]
        results = [block for block in content if block["type"] == "tool_result"]
        assert [block["tool_use_id"] for block in content[: len(ids)]] == ids
        assert [block["tool_use_id"] for block in results] == ids
        for block in results[1:]:
            assert block["content"] == NOT_EXECUTED


# Feature: scenario-drivers-replays, Property 6
@given(tools=place_tools, others=other_places, script=turns)
def test_p4_6_mapping_history_and_no_engine_calls(
    tools: dict[str, list[str]],
    others: list[str],
    script: list[tuple[list[tuple[object, ...]], str | None]],
) -> None:
    """Property P4.6: the LLM driver maps responses to proposals, keeps a well-formed history and
    never touches the engine. Validates: Requirements 4.5"""
    replies = [build_reply(blocks, turn) for turn, (blocks, _) in enumerate(script, start=1)]
    client = FakeClient(replies)
    driver = LLMDriver(client, MODEL)
    fail = AssertionError("the LLM driver must never touch the engine or a tool")
    with (
        patch.object(Engine, "step", side_effect=fail),
        patch.object(Engine, "run", side_effect=fail),
        patch.object(Place, "execute", side_effect=fail),
    ):
        for turn, (blocks, last_result) in enumerate(script, start=1):
            observation = make_observation(tools, others, last_result, turn)
            assert driver.propose(observation) == expected_proposal(blocks)
    assert len(client.calls) == len(script)
    for call in client.calls:
        check_request(call, tools, others)
    for call in client.calls:
        check_history(call["messages"])  # type: ignore[arg-type]
