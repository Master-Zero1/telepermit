"""Unit tests for the real Gemini client returned by build_gemini_client (CONTRACTS section 7).

Spec 6 (gemini-driver), task 8.1. Requirements tested here: 6.6.2, 6.6.3, 6.6.4, 6.6.5, 6.6.6,
6.6.7, 6.6.8, 6.6.9, 6.7.4, 6.7.5, 6.12.1. The opener factory is replaced by its string path, so
this module never imports urllib (6.12.3).
"""

from __future__ import annotations

import json
import socket
import threading
import time
from collections.abc import Callable, Iterator
from typing import Protocol

import pytest

from telepermit.drivers.llm import (
    GEMINI_BASE_URL,
    REQUEST_TIMEOUT_S,
    GeminiRequestError,
    build_gemini_client,
)

OPENER_FACTORY = "urllib.request.build_opener"
KEY = "AIza" + "FakeKeyForTestsOnlyAbcdefgh"
MODEL = "fake-model"
LOCATION = "https://elsewhere.example/collect"
BODY: dict[str, object] = {"contents": [{"role": "user", "parts": [{"text": "hello"}]}]}
REPLY: dict[str, object] = {"candidates": [{"content": {"parts": [{"text": "hi"}]}}]}
REDIRECT_CODES = [301, 302, 303, 307, 308]


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


class RecordedRequest(Protocol):
    """The public Request attributes the fake opener reads."""

    full_url: str
    data: bytes | None

    def get_method(self) -> str: ...

    def header_items(self) -> list[tuple[str, str]]: ...


class RecordedHandler(Protocol):
    """The redirect hook of the handler passed to the opener factory."""

    def redirect_request(
        self,
        req: object,
        fp: object,
        code: int,
        msg: str,
        headers: object,
        newurl: str,
    ) -> object: ...


class FakeHTTPError(OSError):
    """An HTTP failure: an OSError carrying an int code, which the client reads as a status."""

    def __init__(self, code: int, message: str) -> None:
        super().__init__(message)
        self.code = code

    def close(self) -> None:
        """Accept the close the client may call before dropping the error."""


class FakeResponse:
    """A prepared reply: status, body bytes, usable as a context manager."""

    def __init__(self, status: int, payload: bytes) -> None:
        self.status = status
        self._payload = payload

    def read(self) -> bytes:
        return self._payload

    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, *exc_info: object) -> None:
        return None


Behaviour = Callable[[RecordedRequest], FakeResponse]


class FakeOpener:
    """Records every open call and answers it with the given behaviour."""

    def __init__(self, behaviour: Behaviour) -> None:
        self.behaviour = behaviour
        self.calls: list[tuple[RecordedRequest, float | None]] = []

    def open(self, request: RecordedRequest, timeout: float | None = None) -> FakeResponse:
        self.calls.append((request, timeout))
        return self.behaviour(request)


class FakeFactory:
    """Stands in for build_opener: records the handlers and returns one FakeOpener."""

    def __init__(self, behaviour: Behaviour) -> None:
        self.opener = FakeOpener(behaviour)
        self.handler_calls: list[tuple[RecordedHandler, ...]] = []

    def __call__(self, *handlers: RecordedHandler) -> FakeOpener:
        self.handler_calls.append(handlers)
        return self.opener


def install(monkeypatch: pytest.MonkeyPatch, behaviour: Behaviour) -> FakeFactory:
    """Replace the opener factory by string path and return the fake."""
    factory = FakeFactory(behaviour)
    monkeypatch.setattr(OPENER_FACTORY, factory)
    return factory


def replying(status: int, payload: bytes) -> Behaviour:
    def behaviour(request: RecordedRequest) -> FakeResponse:
        return FakeResponse(status, payload)

    return behaviour


def raising(error: Exception) -> Behaviour:
    def behaviour(request: RecordedRequest) -> FakeResponse:
        raise error

    return behaviour


def ok_reply() -> Behaviour:
    return replying(200, json.dumps(REPLY).encode("utf-8"))


def chain_texts(error: BaseException) -> list[str]:
    """str and repr of the error and of every exception reachable by __cause__ or __context__."""
    seen: list[BaseException] = []
    pending = [error]
    while pending:
        current = pending.pop()
        if any(current is known for known in seen):
            continue
        seen.append(current)
        pending += [link for link in (current.__cause__, current.__context__) if link is not None]
    return [text for known in seen for text in (str(known), repr(known))]


def test_network_guard_blocks_and_names_operation(network_attempts: list[str]) -> None:
    """Requirement 6.12.2: the guard raises, names the operation, and records the attempt."""
    with pytest.raises(RuntimeError, match="network access blocked: getaddrinfo"):
        socket.getaddrinfo("example.invalid", 443)
    assert network_attempts == ["getaddrinfo"]
    network_attempts.clear()


@pytest.mark.parametrize("key", ["", "\t\n", " \t\n\r "], ids=["empty", "tab-newline", "mixed"])
def test_blank_key_raises_value_error_without_factory(
    monkeypatch: pytest.MonkeyPatch, key: str
) -> None:
    """Requirements 6.6.3, 6.7.4: a blank key raises ValueError, keyless, before any opener."""
    factory = install(monkeypatch, ok_reply())
    with pytest.raises(ValueError) as caught:
        build_gemini_client(key)
    assert factory.handler_calls == []
    assert factory.opener.calls == []
    if key:
        assert all(key not in text for text in chain_texts(caught.value))


def test_construction_opens_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    """Requirement 6.6.2: building the client assembles one opener and calls no open."""
    factory = install(monkeypatch, ok_reply())
    build_gemini_client(KEY)
    assert len(factory.handler_calls) == 1
    assert factory.opener.calls == []


def test_one_call_sends_one_keyed_post(monkeypatch: pytest.MonkeyPatch) -> None:
    """Requirements 6.6.4, 6.6.5, 6.6.6, 6.12.1: one POST, key in one header, reply returned."""
    factory = install(monkeypatch, ok_reply())
    client = build_gemini_client(KEY)
    result = client.generate_content(MODEL, BODY)
    assert len(factory.opener.calls) == 1
    request, timeout = factory.opener.calls[0]
    assert timeout == REQUEST_TIMEOUT_S == 60
    assert request.get_method() == "POST"
    assert request.full_url == GEMINI_BASE_URL + "fake-model:generateContent"
    headers = {name.lower(): value for name, value in request.header_items()}
    assert headers["content-type"] == "application/json"
    assert headers["x-goog-api-key"] == KEY
    assert [name for name, value in headers.items() if KEY in value] == ["x-goog-api-key"]
    assert request.data is not None
    assert json.loads(request.data.decode("utf-8")) == BODY
    assert KEY not in request.full_url
    assert KEY.encode("utf-8") not in request.data
    assert result == REPLY


def test_model_is_percent_encoded_with_no_safe_characters(monkeypatch: pytest.MonkeyPatch) -> None:
    """Requirement 6.6.4: '/', '?' and '#' in the model name are percent-encoded in the path."""
    factory = install(monkeypatch, ok_reply())
    build_gemini_client(KEY).generate_content("a/b?c#d", BODY)
    (request, _timeout), *_ = factory.opener.calls
    assert request.full_url == GEMINI_BASE_URL + "a%2Fb%3Fc%23d:generateContent"


def test_302_reply_raises_without_key_or_location(monkeypatch: pytest.MonkeyPatch) -> None:
    """Requirements 6.6.8, 6.6.9, 6.7.4: a 302 raises after one open, naming 302 only."""
    error = FakeHTTPError(302, f"Found, see {LOCATION} (x-goog-api-key: {KEY})")
    factory = install(monkeypatch, raising(error))
    client = build_gemini_client(KEY)
    with pytest.raises(GeminiRequestError) as caught:
        client.generate_content(MODEL, BODY)
    assert len(factory.opener.calls) == 1
    assert "302" in str(caught.value)
    for text in chain_texts(caught.value):
        assert KEY not in text
        assert LOCATION not in text


@pytest.mark.parametrize("code", REDIRECT_CODES)
def test_redirect_handler_follows_nothing(monkeypatch: pytest.MonkeyPatch, code: int) -> None:
    """Requirement 6.6.9: the handler is an HTTPRedirectHandler that builds no new request."""
    factory = install(monkeypatch, ok_reply())
    build_gemini_client(KEY)
    (handlers,) = factory.handler_calls
    (handler,) = handlers
    assert "HTTPRedirectHandler" in [cls.__name__ for cls in type(handler).__mro__]
    headers = {"Location": LOCATION}
    assert handler.redirect_request(object(), None, code, "Redirect", headers, LOCATION) is None


def test_slow_request_times_out(monkeypatch: pytest.MonkeyPatch) -> None:
    """Requirement 6.6.7: a request still open after timeout_s raises GeminiRequestError."""
    release = threading.Event()

    def blocked(request: RecordedRequest) -> FakeResponse:
        release.wait(5.0)
        return FakeResponse(200, b"{}")

    install(monkeypatch, blocked)
    client = build_gemini_client(KEY, timeout_s=0.05)
    started = time.monotonic()
    try:
        with pytest.raises(GeminiRequestError) as caught:
            client.generate_content(MODEL, BODY)
        elapsed = time.monotonic() - started
    finally:
        release.set()
    assert elapsed < 1.0
    assert all(KEY not in text for text in chain_texts(caught.value))


@pytest.mark.parametrize(
    "payload",
    [b"not json", b"\xff\xfe\x00", b"[1, 2]", b'"text"', b"null"],
    ids=["not-json", "not-utf8", "list", "string", "null"],
)
def test_bad_reply_body_raises(monkeypatch: pytest.MonkeyPatch, payload: bytes) -> None:
    """Requirements 6.6.8, 6.7.4: a body that is not a UTF-8 JSON object raises, keyless."""
    factory = install(monkeypatch, replying(200, payload))
    client = build_gemini_client(KEY)
    with pytest.raises(GeminiRequestError) as caught:
        client.generate_content(MODEL, BODY)
    assert len(factory.opener.calls) == 1
    assert all(KEY not in text for text in chain_texts(caught.value))


def test_repr_and_str_hide_the_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Requirement 6.7.5: neither repr nor str of the client holds the key."""
    install(monkeypatch, ok_reply())
    client = build_gemini_client(KEY)
    assert KEY not in repr(client)
    assert KEY not in str(client)
