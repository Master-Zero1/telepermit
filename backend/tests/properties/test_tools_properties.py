"""Property tests for the tool catalog (CONTRACTS section 4)."""

from __future__ import annotations

from collections.abc import Callable

from hypothesis import given
from hypothesis import strategies as st

from telepermit.permit import Permit
from telepermit.place import Place
from telepermit.tools import library_tools, vault_tools

CEILING = Permit(60.0, 30, 60, frozenset())
ARG_KEYS = {
    "read_document": "name",
    "search_archive": "query",
    "read_records": "",
    "export_records": "destination",
}


def build() -> tuple[dict[str, Place], Callable[[], tuple[str, ...]]]:
    """Fresh library and vault Places, keyed by the tool each one holds."""
    library = Place("library", library_tools(), CEILING, {}, frozenset())
    vault_set = vault_tools()
    vault = Place("vault", vault_set.tools, CEILING, {}, frozenset())
    owner = {
        "read_document": library,
        "search_archive": library,
        "read_records": vault,
        "export_records": vault,
    }
    return owner, vault_set.outbox


def run(calls: list[tuple[str, str]]) -> tuple[list[str], tuple[str, ...]]:
    owner, outbox = build()
    results = []
    for name, text in calls:
        key = ARG_KEYS[name]
        results.append(owner[name].execute(name, {key: text} if key else {}))
    return results, outbox()


# Feature: tools-places-admission, Property 5
@given(
    calls=st.lists(
        st.tuples(st.sampled_from(sorted(ARG_KEYS)), st.text(max_size=20)),
        max_size=40,
    )
)
def test_p2_5_fresh_places_deterministic(calls: list[tuple[str, str]]) -> None:
    """Property P2.5: two Places built from fresh factory calls return identical results for
    the same call sequence, and the Outbox length equals the number of export_records calls.
    Validates: Requirements 2.1, 2.7"""
    first_results, first_outbox = run(calls)
    second_results, second_outbox = run(calls)
    assert first_results == second_results
    assert first_outbox == second_outbox
    assert list(first_outbox) == [text for name, text in calls if name == "export_records"]
    pages = [
        result
        for (name, _), result in zip(calls, first_results, strict=True)
        if name == "read_records"
    ]
    assert pages == [f"records page {n}" for n in range(1, len(pages) + 1)]
