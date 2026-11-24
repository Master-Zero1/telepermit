"""LLM drivers behind an injected client (CONTRACTS section 7).

A driver turns an Observation into a tool-calling request and the first tool call of the reply
into a Proposal. It keeps its own message history and never executes anything. LLMDriver follows
the documented Anthropic Messages API and GeminiDriver the documented Gemini generateContent REST
API. Neither mapping has been exercised against the live service.
"""

from __future__ import annotations

import copy
import json
import threading
from collections.abc import Callable, Mapping, Sequence
from typing import Final, Protocol

from telepermit.drivers import FINISH_ACTION, GO_PREFIX
from telepermit.drivers.base import Observation, Proposal

ENV_MODEL: Final = "AGENT_MODEL"
ENV_API_KEY: Final = "ANTHROPIC_API_KEY"
ENV_GEMINI_API_KEY: Final = "GEMINI_API_KEY"
PROVIDER_ANTHROPIC: Final = "anthropic"
PROVIDER_GEMINI: Final = "gemini"
GEMINI_BASE_URL: Final = "https://generativelanguage.googleapis.com/v1beta/models/"
GEMINI_METHOD: Final = ":generateContent"
GEMINI_KEY_HEADER: Final = "x-goog-api-key"
REQUEST_TIMEOUT_S: Final = 60.0
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


class GeminiRequestError(RuntimeError):
    """A failed Gemini HTTP call. Messages never hold the API key, URL, headers or body."""


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


class _HTTPReply(Protocol):
    """The part of an opened HTTP response that the Gemini client reads."""

    status: int

    def read(self) -> bytes: ...

    def __enter__(self) -> _HTTPReply: ...

    def __exit__(self, *exc_info: object) -> object: ...


class _Opener(Protocol):
    """The part of a urllib opener that the Gemini client uses."""

    def open(self, request: object, timeout: float) -> _HTTPReply: ...


class _Outcome:
    """What one worker thread saw: a status and body, or a key-free failure message."""

    __slots__ = ("failure", "payload", "status")

    def __init__(self) -> None:
        self.status: object = None
        self.payload: bytes = b""
        self.failure: str | None = None


def _status_message(status: object) -> str:
    return f"Gemini request failed with HTTP status {status}"


def _failure_message(exc: Exception) -> str:
    """The code for an HTTP error, else the type name. Never the original message."""
    code = getattr(exc, "code", None)
    if isinstance(code, int) and not isinstance(code, bool):
        return _status_message(code)
    return f"Gemini request failed: {type(exc).__name__}"


def _close_quietly(exc: Exception) -> None:
    """Close an HTTP error (it holds an open response) before it is dropped."""
    close = getattr(exc, "close", None)
    if callable(close):
        try:
            close()
        except Exception:  # a failed close must not replace the recorded failure
            return


def _parse_reply(payload: bytes) -> dict[str, object]:
    """The reply as a dict. Raises after the try statement, so no exception chain is kept."""
    valid = True
    reply: object = None
    try:
        reply = json.loads(payload.decode("utf-8"))
    except (ValueError, RecursionError):
        valid = False
    if not valid:
        raise GeminiRequestError("Gemini reply is not valid JSON")
    if not isinstance(reply, dict):
        raise GeminiRequestError("Gemini reply is not a JSON object")
    return reply


class _UrllibGeminiClient:
    """One keyed POST per call to generateContent, bounded by timeout_s. Imports nothing."""

    __slots__ = ("_key", "_opener", "_quote", "_request_cls", "_timeout_s")

    def __init__(
        self,
        key: str,
        opener: _Opener,
        request_cls: Callable[..., object],
        quote: Callable[..., str],
        timeout_s: float,
    ) -> None:
        self._key = key
        self._opener = opener
        self._request_cls = request_cls
        self._quote = quote
        self._timeout_s = timeout_s

    def __repr__(self) -> str:
        return "GeminiClient(api_key=<redacted>)"

    def __str__(self) -> str:
        return self.__repr__()

    def generate_content(self, model: str, body: Mapping[str, object]) -> dict[str, object]:
        """POST the body once and return the JSON object reply, or raise GeminiRequestError."""
        url = GEMINI_BASE_URL + self._quote(model, safe="") + GEMINI_METHOD
        request = self._request_cls(
            url,
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json", GEMINI_KEY_HEADER: self._key},
            method="POST",
        )
        outcome = _Outcome()
        worker = threading.Thread(target=self._exchange, args=(request, outcome), daemon=True)
        worker.start()
        worker.join(self._timeout_s)
        if worker.is_alive():
            raise GeminiRequestError(f"Gemini request timed out after {self._timeout_s:g} seconds")
        if outcome.failure is not None:
            raise GeminiRequestError(outcome.failure)
        status = outcome.status
        if not isinstance(status, int) or isinstance(status, bool) or not 200 <= status <= 299:
            raise GeminiRequestError(_status_message(status))
        return _parse_reply(outcome.payload)

    def _exchange(self, request: object, outcome: _Outcome) -> None:
        """Worker body: one open call; records only key-free facts about the result."""
        try:
            with self._opener.open(request, timeout=self._timeout_s) as response:
                outcome.status = getattr(response, "status", None)
                outcome.payload = response.read()
        except Exception as exc:  # every failure becomes a key-free message
            outcome.failure = _failure_message(exc)
            _close_quietly(exc)


def build_gemini_client(api_key: str, *, timeout_s: float = REQUEST_TIMEOUT_S) -> GeminiClient:
    """Build the real Gemini client. The only place that imports urllib. Opens nothing."""
    if not api_key.strip():
        raise ValueError("the Gemini API key must not be blank")
    import urllib.parse
    import urllib.request

    class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
        """Follow no redirect: the 3xx surfaces as an HTTP error with its code."""

        def redirect_request(
            self,
            req: object,
            fp: object,
            code: int,
            msg: str,
            headers: object,
            newurl: str,
        ) -> None:
            return None

    opener = urllib.request.build_opener(_NoRedirectHandler())
    return _UrllibGeminiClient(
        api_key, opener, urllib.request.Request, urllib.parse.quote, timeout_s
    )


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


def _first_text(observation: Observation) -> str:
    return f"Task: {observation.task}\nYou are in {observation.place}."


def _now_in_text(observation: Observation) -> str:
    return f"You are now in {observation.place}."


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
    provider: Final = PROVIDER_ANTHROPIC

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
        where = _now_in_text(observation) if self._history else _first_text(observation)
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


def _reply_parts(reply: object) -> list[object]:
    """The parts of candidates[0], or [] when any step of the reply shape is malformed."""
    if not isinstance(reply, Mapping):
        return []
    candidates = reply.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        return []
    first = candidates[0]
    if not isinstance(first, dict):
        return []
    content = first.get("content")
    if not isinstance(content, dict):
        return []
    parts = content.get("parts")
    return parts if isinstance(parts, list) else []


def _function_calls(parts: list[object]) -> list[tuple[str, dict[str, object], str | None]]:
    """(name, args, id) of every part that is a dict whose functionCall value is a dict."""
    calls: list[tuple[str, dict[str, object], str | None]] = []
    for part in parts:
        call = part.get("functionCall") if isinstance(part, dict) else None
        if not isinstance(call, dict):
            continue
        name = call.get("name")
        args = call.get("args")
        call_id = call.get("id")
        calls.append(
            (
                name if isinstance(name, str) else "",
                args if isinstance(args, dict) else {},
                call_id if isinstance(call_id, str) else None,
            )
        )
    return calls


def _function_response(name: str, call_id: str | None, text: str) -> dict[str, object]:
    """The functionResponse value; `id` is present only when the call had one."""
    response: dict[str, object] = {"name": name}
    if call_id is not None:
        response["id"] = call_id
    response["response"] = {_RESULT_KEY: text}
    return response


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
        """Send the History and the declarations once, and map the first Function_Call."""
        self._add_user_parts(observation)
        reply = self._client.generate_content(self._model, self._body(observation))
        parts = _reply_parts(reply)
        if parts:
            self._history.append({"role": "model", "parts": copy.deepcopy(parts)})
        calls = _function_calls(parts)
        self._pending = [(name, call_id) for name, _, call_id in calls]
        if not calls:
            return Proposal(FINISH_ACTION, {})
        name, args, _ = calls[0]
        return _to_proposal(name, args)

    def _add_user_parts(self, observation: Observation) -> None:
        """Add the User_Turn parts; merge into the last User_Turn after an empty reply."""
        if not self._history:
            self._history.append({"role": "user", "parts": [{"text": _first_text(observation)}]})
            return
        new_parts: list[object] = []
        for index, (name, call_id) in enumerate(self._pending):
            text = (observation.last_result or "") if index == 0 else _NOT_EXECUTED
            new_parts.append({"functionResponse": _function_response(name, call_id, text)})
        new_parts.append({"text": _now_in_text(observation)})
        last = self._history[-1]
        last_parts = last.get("parts")
        if last.get("role") == "user" and isinstance(last_parts, list):
            last_parts.extend(new_parts)
        else:
            self._history.append({"role": "user", "parts": new_parts})

    def _body(self, observation: Observation) -> dict[str, object]:
        return {
            "contents": copy.deepcopy(self._history),
            "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
            "tools": [{"functionDeclarations": _declarations(observation)}],
            "toolConfig": {"functionCallingConfig": {"mode": _FUNCTION_MODE}},
        }
