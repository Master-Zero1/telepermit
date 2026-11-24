"""Property tests for the real Gemini client from build_gemini_client (CONTRACTS section 7).

Spec 6 (gemini-driver). Property P6.7 validates Requirements 6.6.2, 6.6.4, 6.6.5 and 6.6.6.
Property P6.8 validates Requirements 6.6.3, 6.6.8, 6.6.9, 6.7.4 and 6.7.5.

The opener factory is replaced by its string path inside each example, so this module never
imports urllib (6.12.3). The network guard is module-scoped: it installs the socket blockers once
for the whole module through `pytest.MonkeyPatch.context()`, so Hypothesis never sees a
function-scoped fixture and no health check is suppressed. Teardown fails the module if any
network attempt was recorded.
"""

from __future__ import annotations

import json
import socket
import string
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import Protocol

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from telepermit.drivers.llm import (
    GEMINI_BASE_URL,
    REQUEST_TIMEOUT_S,
    GeminiRequestError,
    build_gemini_client,
)

OPENER_FACTORY = "urllib.request.build_opener"
METHOD_SUFFIX = ":generateContent"
UNRESERVED = frozenset(string.ascii_letters + string.digits + "-._~")
HEX_DIGITS = frozenset(string.hexdigits)
KEY_ALPHABET = string.ascii_letters + string.digits + "_-"


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


class RecordedRequest(Protocol):
    """The public Request attributes the fake opener reads."""

    full_url: str
    data: bytes | None

    def get_method(self) -> str: ...

    def header_items(self) -> list[tuple[str, str]]: ...


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


class FakeOpener:
    """Records every open call and answers each with the same prepared reply."""

    def __init__(self, status: int, payload: bytes) -> None:
        self._status = status
        self._payload = payload
        self.calls: list[tuple[RecordedRequest, float | None]] = []

    def open(self, request: RecordedRequest, timeout: float | None = None) -> FakeResponse:
        self.calls.append((request, timeout))
        return FakeResponse(self._status, self._payload)


class FakeFactory:
    """Stands in for build_opener: records the handlers and returns one FakeOpener."""

    def __init__(self, status: int, payload: bytes) -> None:
        self.opener = FakeOpener(status, payload)
        self.handler_calls: list[tuple[object, ...]] = []

    def __call__(self, *handlers: object) -> FakeOpener:
        self.handler_calls.append(handlers)
        return self.opener


def percent_decode(segment: str) -> str:
    """Decode `%XX` triplets and plain characters as UTF-8 bytes; reject malformed triplets."""
    raw = bytearray()
    index = 0
    while index < len(segment):
        if segment[index] == "%":
            triplet = segment[index + 1 : index + 3]
            assert len(triplet) == 2 and set(triplet) <= HEX_DIGITS, segment
            raw.append(int(triplet, 16))
            index += 3
        else:
            raw.extend(segment[index].encode("utf-8"))
            index += 1
    return raw.decode("utf-8")


json_scalars = (
    st.none()
    | st.booleans()
    | st.integers()
    | st.floats(allow_nan=False, allow_infinity=False)
    | st.text(max_size=20)
)


def json_containers(children: st.SearchStrategy[object]) -> st.SearchStrategy[object]:
    """Lists and string-keyed objects of the given JSON values."""
    lists = st.lists(children, max_size=3)
    objects = st.dictionaries(st.text(max_size=10), children, max_size=3)
    return lists | objects


json_values = st.recursive(json_scalars, json_containers, max_leaves=10)
json_objects = st.dictionaries(st.text(max_size=10), json_values, max_size=4)
models = st.text(
    alphabet=st.sampled_from("/?#: %") | st.characters(),
    min_size=1,
    max_size=30,
).filter(lambda model: model.strip() != "")
keys = st.text(alphabet=KEY_ALPHABET, min_size=20, max_size=40).map(lambda tail: "AIza" + tail)


# Feature: gemini-driver, Property P6.7: The real client sends one key-in-header POST to the
# encoded endpoint
@given(
    model=models,
    key=keys,
    body=json_objects,
    reply=json_objects,
    status=st.integers(min_value=200, max_value=299),
)
def test_p6_7_one_key_in_header_post_to_encoded_endpoint(
    model: str,
    key: str,
    body: dict[str, object],
    reply: dict[str, object],
    status: int,
) -> None:
    """Property P6.7: for any non-blank model, generated key and JSON-object body, building
    the client opens nothing, and one generate_content call makes exactly one POST, timeout 60,
    to GEMINI_BASE_URL + percent-encoded model + ":generateContent", sends the body as UTF-8
    JSON with a JSON content type, carries the key only in the x-goog-api-key header, and
    returns the stub's JSON object. Validates: 6.6.2, 6.6.4, 6.6.5, 6.6.6"""
    assume(key not in json.dumps(body))
    assume(key not in model)
    factory = FakeFactory(status, json.dumps(reply).encode("utf-8"))
    with pytest.MonkeyPatch.context() as patcher:
        patcher.setattr(OPENER_FACTORY, factory)
        client = build_gemini_client(key)
        assert factory.opener.calls == []
        result = client.generate_content(model, body)

    assert len(factory.opener.calls) == 1
    request, timeout = factory.opener.calls[0]
    assert timeout == REQUEST_TIMEOUT_S == 60
    assert request.get_method() == "POST"

    url = request.full_url
    assert url.startswith(GEMINI_BASE_URL)
    assert url.endswith(METHOD_SUFFIX)
    segment = url[len(GEMINI_BASE_URL) : len(url) - len(METHOD_SUFFIX)]
    assert not {"/", "?", "#"} & set(segment)
    assert set(segment) <= UNRESERVED | {"%"}
    assert percent_decode(segment) == model

    headers = {name.lower(): value for name, value in request.header_items()}
    assert headers["content-type"] == "application/json"
    assert headers["x-goog-api-key"] == key

    assert request.data is not None
    assert request.data == json.dumps(body).encode("utf-8")
    assert json.loads(request.data.decode("utf-8")) == body
    assert key not in url
    assert key.encode("utf-8") not in request.data
    assert result == reply


MODEL = "fake-model"
REQUEST_BODY: dict[str, object] = {"contents": [{"role": "user", "parts": [{"text": "hello"}]}]}
WHITESPACE = " \t\n\r\x0b\x0c"
RAISED_TYPES: tuple[type[Exception], ...] = (
    OSError,
    ConnectionError,
    TimeoutError,
    RuntimeError,
    ValueError,
)


class FakeHTTPError(OSError):
    """An HTTP failure: an OSError carrying an int code, a URL and a Location header."""

    def __init__(self, code: int, message: str, location: str) -> None:
        super().__init__(message)
        self.code = code
        self.url = location
        self.headers = {"Location": location}

    def close(self) -> None:
        """Accept the close the client may call before dropping the error."""


class RaisingOpener(FakeOpener):
    """Records every open call and answers each by raising the prepared error."""

    def __init__(self, error: Exception) -> None:
        super().__init__(0, b"")
        self._error = error

    def open(self, request: RecordedRequest, timeout: float | None = None) -> FakeResponse:
        self.calls.append((request, timeout))
        raise self._error


class RaisingFactory(FakeFactory):
    """Stands in for build_opener and returns one RaisingOpener."""

    def __init__(self, error: Exception) -> None:
        super().__init__(0, b"")
        self.opener = RaisingOpener(error)


@dataclass(frozen=True)
class FailureCase:
    """One failure mode: a raised error, or a returned status and body."""

    status_in_message: int | None
    error: Exception | None = None
    reply_status: int = 200
    payload: bytes = b""


def factory_for(case: FailureCase) -> FakeFactory:
    """A fake opener factory that produces the failure the case describes."""
    if case.error is not None:
        return RaisingFactory(case.error)
    return FakeFactory(case.reply_status, case.payload)


def parses_as_json(payload: bytes) -> bool:
    """True when the bytes are UTF-8 text that parses as JSON."""
    try:
        json.loads(payload.decode("utf-8"))
    except ValueError:
        return False
    return True


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


def http_errors(key: str, location: str) -> st.SearchStrategy[FailureCase]:
    """A raised error with an int code from 300 to 599 whose message holds the key."""
    return st.integers(min_value=300, max_value=599).map(
        lambda code: FailureCase(
            status_in_message=code,
            error=FakeHTTPError(
                code, f"HTTP {code}: see {location} (x-goog-api-key: {key})", location
            ),
        )
    )


def bad_statuses(key: str, location: str) -> st.SearchStrategy[FailureCase]:
    """A returned status outside 200 to 299 with a JSON object body that holds the key."""
    payload = json.dumps({"error": {"message": f"bad key {key}", "location": location}})
    statuses = st.integers(min_value=100, max_value=199) | st.integers(min_value=300, max_value=599)
    return statuses.map(
        lambda status: FailureCase(
            status_in_message=status, reply_status=status, payload=payload.encode("utf-8")
        )
    )


def raised_exceptions(key: str, location: str) -> st.SearchStrategy[FailureCase]:
    """An OSError or other Exception, without a code, whose message holds the key."""
    return st.tuples(st.sampled_from(RAISED_TYPES), st.text(max_size=20)).map(
        lambda pair: FailureCase(
            status_in_message=None, error=pair[0](f"{pair[1]} {key} via {location}")
        )
    )


def non_json_bodies(key: str) -> st.SearchStrategy[FailureCase]:
    """A 2xx reply whose body is not UTF-8 JSON, sometimes holding the key."""
    payloads = st.one_of(
        st.binary(max_size=40),
        st.text(max_size=20).map(lambda text: f"{{{text} {key}".encode()),
        st.just(b"\xff\xfe" + key.encode("utf-8")),
    ).filter(lambda payload: not parses_as_json(payload))
    return st.tuples(st.integers(min_value=200, max_value=299), payloads).map(
        lambda pair: FailureCase(status_in_message=None, reply_status=pair[0], payload=pair[1])
    )


def non_object_bodies(key: str) -> st.SearchStrategy[FailureCase]:
    """A 2xx reply whose body is valid JSON but not an object, sometimes holding the key."""
    values = st.one_of(
        json_scalars,
        st.lists(json_values, max_size=3),
        st.just(key),
        st.lists(json_values, max_size=3).map(lambda items: [*items, key]),
    )
    return st.tuples(st.integers(min_value=200, max_value=299), values).map(
        lambda pair: FailureCase(
            status_in_message=None,
            reply_status=pair[0],
            payload=json.dumps(pair[1]).encode("utf-8"),
        )
    )


@st.composite
def keyed_failures(draw: st.DrawFn) -> tuple[str, FailureCase]:
    """A generated key and one failure mode built around it."""
    key = draw(keys)
    location = f"https://elsewhere.example/collect?key={key}"
    case = draw(
        st.one_of(
            http_errors(key, location),
            bad_statuses(key, location),
            raised_exceptions(key, location),
            non_json_bodies(key),
            non_object_bodies(key),
        )
    )
    return key, case


blank_keys = st.text(alphabet=WHITESPACE, max_size=10)


# Feature: gemini-driver, Property P6.8: Client failures raise key-free exceptions
@given(keyed=keyed_failures(), blank=blank_keys)
def test_p6_8_client_failures_raise_key_free_exceptions(
    keyed: tuple[str, FailureCase],
    blank: str,
) -> None:
    """Property P6.8: for any generated key and any failure mode (a raised error with an int
    code from 300 to 599, a returned non-2xx status, an OSError or other Exception holding the
    key, a body that is not UTF-8 JSON, JSON that is not an object), generate_content raises
    GeminiRequestError after exactly one open call, a status failure names its code, and no
    exception in the cause/context chain holds the key; a whitespace-only key makes
    build_gemini_client raise a keyless ValueError before any opener is built; repr and str of
    the client never hold the key. Validates: 6.6.3, 6.6.8, 6.6.9, 6.7.4, 6.7.5"""
    key, case = keyed
    factory = factory_for(case)
    with pytest.MonkeyPatch.context() as patcher:
        patcher.setattr(OPENER_FACTORY, factory)
        client = build_gemini_client(key)
        assert key not in repr(client)
        assert key not in str(client)
        with pytest.raises(GeminiRequestError) as caught:
            client.generate_content(MODEL, REQUEST_BODY)

    assert len(factory.opener.calls) == 1
    if case.status_in_message is not None:
        assert str(case.status_in_message) in str(caught.value)
    for text in chain_texts(caught.value):
        assert key not in text

    blank_factory = FakeFactory(200, b"{}")
    with pytest.MonkeyPatch.context() as patcher:
        patcher.setattr(OPENER_FACTORY, blank_factory)
        with pytest.raises(ValueError) as refused:
            build_gemini_client(blank)
    assert blank_factory.handler_calls == []
    assert blank_factory.opener.calls == []
    # A key of spaces only is a substring of any multi-word message, so only keys holding
    # another whitespace character are checked for a leak.
    if blank.strip(" "):
        for text in chain_texts(refused.value):
            assert blank not in text
