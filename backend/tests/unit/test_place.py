"""Unit tests for Place and Admission (CONTRACTS section 4, task 1.1)."""

from __future__ import annotations

import pytest

from telepermit.permit import Permit
from telepermit.place import (
    ADMIT,
    ADMIT_IMPOSED,
    EXCEEDS_CEILING,
    OK,
    REFUSE,
    Admission,
    Place,
    UnknownToolError,
)
from telepermit.tools import Tool, library_tools, vault_tools

PERMIT = Permit(1.0, 1, 1, frozenset())


def double(args: dict[str, str]) -> str:
    return args.get("x", "") * 2


def make_place() -> Place:
    tools = {
        "alpha": Tool("alpha", 2, "first", {"x": "str"}, double),
        "beta": Tool("beta", 0, "second", {}, double),
    }
    return Place(
        name="hall",
        tools=tools,
        ceiling=Permit(10.0, 5, 5, frozenset({"alpha", "beta"})),
        trusted={},
        allowed_classes=frozenset({"bot"}),
    )


def test_has_tool_and_tool_cost() -> None:
    """Requirement 2.1: has_tool never raises and tool_cost returns the cost."""
    place = make_place()
    assert place.has_tool("alpha") is True
    assert place.has_tool("nope") is False
    assert place.tool_cost("alpha") == 2
    assert place.tool_cost("beta") == 0


def test_execute_returns_tool_result() -> None:
    """Requirement 2.1: execute runs the named tool."""
    assert make_place().execute("alpha", {"x": "ab"}) == "abab"


def test_execute_unknown_tool_raises() -> None:
    """Requirement 2.8: an unknown tool raises an error naming the tool and the Place."""
    with pytest.raises(UnknownToolError) as info:
        make_place().execute("nope", {})
    assert "nope" in str(info.value)
    assert "hall" in str(info.value)
    assert isinstance(info.value, LookupError)
    assert not isinstance(info.value, KeyError)


def test_tool_cost_unknown_tool_raises() -> None:
    """Requirement 2.8: tool_cost of an unknown tool raises the same error."""
    with pytest.raises(UnknownToolError) as info:
        make_place().tool_cost("nope")
    assert "nope" in str(info.value)
    assert "hall" in str(info.value)
    assert isinstance(info.value, LookupError)
    assert not isinstance(info.value, KeyError)


def test_admission_invariant() -> None:
    """permit_after is None exactly when the decision is REFUSE."""
    with pytest.raises(ValueError):
        Admission(REFUSE, PERMIT, EXCEEDS_CEILING)
    for decision in (ADMIT, ADMIT_IMPOSED):
        with pytest.raises(ValueError):
            Admission(decision, None, OK)
    with pytest.raises(ValueError):
        Admission("MAYBE", PERMIT, OK)
    assert Admission(REFUSE, None, EXCEEDS_CEILING).permit_after is None
    assert Admission(ADMIT, PERMIT, OK).permit_after is PERMIT
    assert Admission(ADMIT_IMPOSED, PERMIT, OK).decision == ADMIT_IMPOSED


def run_catalog_sequence() -> list[str]:
    ceiling = Permit(60.0, 30, 60, frozenset())
    library = Place("library", library_tools(), ceiling, {}, frozenset({"bot"}))
    vault = Place("vault", vault_tools().tools, ceiling, {}, frozenset({"bot"}))
    return [
        library.execute("read_document", {"name": "briefing-q3"}),
        library.execute("search_archive", {"query": "x"}),
        vault.execute("read_records", {}),
        vault.execute("read_records", {}),
        vault.execute("export_records", {"destination": "d@x"}),
    ]


def test_fresh_places_identical_results() -> None:
    """Requirements 2.1, 2.7: two fresh Places given the same calls return identical results."""
    first = run_catalog_sequence()
    second = run_catalog_sequence()
    assert first == second
    assert first[2:] == [
        "records page 1",
        "records page 2",
        "exported all records to d@x (export #1)",
    ]
