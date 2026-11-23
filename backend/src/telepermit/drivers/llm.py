"""LLM drivers behind an injected client (CONTRACTS section 7).

A driver turns an Observation into a tool-calling request and the first tool call of the reply
into a Proposal. It keeps its own message history and never executes anything. LLMDriver follows
the documented Anthropic Messages API and GeminiDriver the documented Gemini generateContent REST
API. Neither mapping has been exercised against the live service.
"""

from __future__ import annotations

import copy
from collections.abc import Mapping, Sequence
from typing import Final, Protocol

from telepermit.drivers import FINISH_ACTION, GO_PREFIX
from telepermit.drivers.base import Observation, Proposal

ENV_MODEL: Final = "AGENT_MODEL"
ENV_API_KEY: Final = "ANTHROPIC_API_KEY"
ENV_GEMINI_API_KEY: Final = "GEMINI_API_KEY"
PROVIDER_ANTHROPIC: Final = "anthropic"
PROVIDER_GEMINI: Final = "gemini"
MAX_TOKENS: Final = 1024
GO_TOOL: Final = "go"
SYSTEM_PROMPT: Final = (
    "You complete the user's task by calling the tools you are given. "
    "Call exactly one tool per turn. When the task is done, call finish."
)

_TOOL_CHOICE: Final = {"type": "auto", "disable_parallel_tool_use": True}
_NOT_EXECUTED: Final = "Not executed: only one action is taken per turn."
_DEFAULT_FINISH_TEXT: Final = "End the run."
_GO_TEXT: Final = "Move to another place."
_FUNCTION_MODE: Final = "AUTO"
_RESULT_KEY: Final = "result"  # functionResponse.response = {"result": <text>}


class LLMUnavailableError(RuntimeError):
    """The optional llm extra (the anthropic package) is not installed."""


class _Response(Protocol):
    content: Sequence[object]


class _Messages(Protocol):
    def create(
        self,
        *,
        model: str,
        max_tokens: int,
        system: str,
        tools: list[dict[str, object]],
        tool_choice: dict[str, object],
        messages: list[dict[str, object]],
    ) -> _Response: ...


class LLMClient(Protocol):
    """The part of the provider client that the driver uses."""

    messages: _Messages


class GeminiClient(Protocol):
    """The injected Gemini client. One call per turn; returns the parsed JSON reply."""

    def generate_content(self, model: str, body: Mapping[str, object]) -> Mapping[str, object]: ...


def build_client(api_key: str) -> LLMClient:
    """Build the real client. The only place that imports anthropic."""
    try:
        import anthropic
    except ImportError as exc:
        raise LLMUnavailableError(
            "the llm extra is not installed: run uv sync --extra llm"
        ) from exc
    return anthropic.Anthropic(api_key=api_key)  # type: ignore[no-any-return]


def _string_schema(args: object) -> dict[str, object]:
    names = [str(name) for name in args] if isinstance(args, dict) else []
    return {
        "type": "object",
        "properties": {name: {"type": "string"} for name in names},
        "required": names,
    }


def _tools(observation: Observation) -> list[dict[str, object]]:
    """Place tools, then one go tool over the other places, then finish."""
    place_tools: list[dict[str, object]] = []
    places: list[str] = []
    finish_text = _DEFAULT_FINISH_TEXT
    for entry in observation.tools:
        name = str(entry["name"])
        if name == FINISH_ACTION:
            finish_text = str(entry.get("description", finish_text))
        elif name.startswith(GO_PREFIX):
            places.append(name[len(GO_PREFIX) :])
        else:
            place_tools.append(
                {
                    "name": name,
                    "description": str(entry.get("description", "")),
                    "input_schema": _string_schema(entry.get("args")),
                }
            )
    if places:
        place_schema = {"type": "string", "enum": places}
        place_tools.append(
            {
                "name": GO_TOOL,
                "description": _GO_TEXT,
                "input_schema": {
                    "type": "object",
                    "properties": {"place": place_schema},
                    "required": ["place"],
                },
            }
        )
    place_tools.append(
        {
            "name": FINISH_ACTION,
            "description": finish_text,
            "input_schema": {"type": "object", "properties": {}, "required": []},
        }
    )
    return place_tools


def _to_proposal(name: str, payload: dict[str, object]) -> Proposal:
    if name == GO_TOOL:
        place = payload.get("place")
        return Proposal(GO_PREFIX if place is None else GO_PREFIX + str(place), {})
    if name == FINISH_ACTION:
        return Proposal(FINISH_ACTION, {})
    return Proposal(name, {str(key): str(value) for key, value in payload.items()})


class LLMDriver:
    """Asks a language model for the next action. The client is injected, the model is a parameter.

    The Engine decides what to do with the Proposal: this class never executes anything.
    """

    label: Final = "llm"

    def __init__(self, client: LLMClient, model: str, *, max_tokens: int = MAX_TOKENS) -> None:
        if not model.strip():
            raise ValueError("the model name must not be blank")
        self._client = client
        self._model = model
        self._max_tokens = max_tokens
        self._history: list[dict[str, object]] = []
        self._pending: list[str] = []

    def propose(self, observation: Observation) -> Proposal:
        """Send the history and the tools, and map the first tool call of the reply."""
        self._history.append(self._user_message(observation))
        response = self._client.messages.create(
            model=self._model,
            max_tokens=self._max_tokens,
            system=SYSTEM_PROMPT,
            tools=_tools(observation),
            tool_choice=dict(_TOOL_CHOICE),
            messages=copy.deepcopy(self._history),
        )
        return self._read(response)

    def _user_message(self, observation: Observation) -> dict[str, object]:
        content: list[dict[str, object]] = []
        if not self._history:
            where = f"Task: {observation.task}\nYou are in {observation.place}."
        else:
            where = f"You are now in {observation.place}."
        for index, tool_use_id in enumerate(self._pending):
            result = (observation.last_result or "") if index == 0 else _NOT_EXECUTED
            content.append({"type": "tool_result", "tool_use_id": tool_use_id, "content": result})
        content.append({"type": "text", "text": where})
        return {"role": "user", "content": content}

    def _read(self, response: _Response) -> Proposal:
        assistant: list[dict[str, object]] = []
        pending: list[str] = []
        first: tuple[str, dict[str, object]] | None = None
        for block in getattr(response, "content", None) or []:
            kind = getattr(block, "type", None)
            if kind == "text":
                assistant.append({"type": "text", "text": str(getattr(block, "text", ""))})
            elif kind == "tool_use":
                raw = getattr(block, "input", None)
                payload = dict(raw) if isinstance(raw, dict) else {}
                name = str(getattr(block, "name", ""))
                tool_use_id = str(getattr(block, "id", ""))
                assistant.append(
                    {"type": "tool_use", "id": tool_use_id, "name": name, "input": payload}
                )
                pending.append(tool_use_id)
                if first is None:
                    first = (name, payload)
        self._pending = pending
        if assistant:
            self._history.append({"role": "assistant", "content": assistant})
        if first is None:
            return Proposal(FINISH_ACTION, {})
        return _to_proposal(*first)


def _gemini_schema(args: object) -> dict[str, object]:
    """One required STRING property per arg name; a non-mapping gives an empty object."""
    names = [str(name) for name in args] if isinstance(args, dict) else []
    return {
        "type": "OBJECT",
        "properties": {name: {"type": "STRING"} for name in names},
        "required": names,
    }


def _declarations(observation: Observation) -> list[dict[str, object]]:
    """Place tools in Observation order, then go over the other places, then finish."""
    declared: list[dict[str, object]] = []
    places: list[str] = []
    finish_text = _DEFAULT_FINISH_TEXT
    for entry in observation.tools:
        name = str(entry["name"])
        if name == FINISH_ACTION:
            finish_text = str(entry.get("description", finish_text))
        elif name.startswith(GO_PREFIX):
            places.append(name[len(GO_PREFIX) :])
        else:
            declared.append(
                {
                    "name": name,
                    "description": str(entry.get("description", "")),
                    "parameters": _gemini_schema(entry.get("args")),
                }
            )
    if places:
        place_schema = {"type": "STRING", "format": "enum", "enum": places}
        declared.append(
            {
                "name": GO_TOOL,
                "description": _GO_TEXT,
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


class GeminiDriver:
    """Asks a Gemini model for the next action. The client is injected, the model is a parameter.

    The Engine decides what to do with the Proposal: this class never executes anything.
    """

    label: Final = "llm"
    provider: Final = PROVIDER_GEMINI

    def __init__(self, client: GeminiClient, model: str) -> None:
        if not model.strip():
            raise ValueError("the model name must not be blank")
        self._client = client
        self._model = model
        self._history: list[dict[str, object]] = []
        self._pending: list[tuple[str, str | None]] = []

    def propose(self, observation: Observation) -> Proposal:
        """Send the History and the declarations once. Reply mapping comes in task 3.3."""
        if not self._history:
            text = f"Task: {observation.task}\nYou are in {observation.place}."
            self._history.append({"role": "user", "parts": [{"text": text}]})
        self._client.generate_content(self._model, self._body(observation))
        return Proposal(FINISH_ACTION, {})

    def _body(self, observation: Observation) -> dict[str, object]:
        return {
            "contents": self._history,
            "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
            "tools": [{"functionDeclarations": _declarations(observation)}],
            "toolConfig": {"functionCallingConfig": {"mode": _FUNCTION_MODE}},
        }
