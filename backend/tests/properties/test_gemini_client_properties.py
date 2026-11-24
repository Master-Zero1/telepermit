"""Property tests for the real Gemini client from build_gemini_client (CONTRACTS section 7).

Spec 6 (gemini-driver). Property P6.7 validates Requirements 6.6.2, 6.6.4, 6.6.5 and 6.6.6.

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
from typing import Protocol

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from telepermit.drivers.llm import GEMINI_BASE_URL, REQUEST_TIMEOUT_S, build_gemini_client

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
