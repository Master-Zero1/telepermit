"""Unit tests for Place and Admission (CONTRACTS section 4, task 1.1)."""

from __future__ import annotations

import dataclasses

import pytest

from telepermit.identity import BAD_SIGNATURE, UNTRUSTED_AUTHORITY, Authority, Identity
from telepermit.permit import Permit
from telepermit.place import (
    ADMIT,
    ADMIT_IMPOSED,
    CLASS_NOT_ALLOWED,
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


# DEMO ONLY seeded authority, fine for tests.
AUTHORITY = Authority.from_seed("home", b"place-tests")
BOT_ONLY = frozenset({"bot"})
REQUEST = Permit(60.0, 30, 60, frozenset({"a", "b"}))
WIDER_CEILING = Permit(60.0, 30, 60, frozenset({"a", "b", "c"}))
NARROW_CEILING = Permit(40.0, 20, 40, frozenset({"a"}))


def make_gate(ceiling: Permit, allowed: frozenset[str] = BOT_ONLY) -> Place:
    return Place("gate", {}, ceiling, {"home": AUTHORITY.public_key}, allowed)


def issue(agent_class: str = "bot") -> Identity:
    return AUTHORITY.issue("agent-1", agent_class, 0.0)


def test_untrusted_authority_refused() -> None:
    """Requirement 2.2: an authority missing from trusted is refused with that code."""
    stranger = Authority.from_seed("stranger", b"other").issue("agent-1", "bot", 0.0)
    result = make_gate(WIDER_CEILING).admit(stranger, REQUEST, 0, 0, 0.0)
    assert result.decision == REFUSE
    assert result.permit_after is None
    assert result.reason == UNTRUSTED_AUTHORITY


def test_bad_signature_refused() -> None:
    """Requirement 2.2: a trusted authority name with a tampered identity gets BAD_SIGNATURE."""
    tampered = dataclasses.replace(issue(), agent_id="evil")
    result = make_gate(WIDER_CEILING).admit(tampered, REQUEST, 0, 0, 0.0)
    assert result.decision == REFUSE
    assert result.permit_after is None
    assert result.reason == BAD_SIGNATURE


def test_class_not_allowed_refused() -> None:
    """Requirement 2.3: a verified identity with a disallowed class is refused."""
    result = make_gate(WIDER_CEILING).admit(issue("spy"), REQUEST, 0, 0, 0.0)
    assert result.decision == REFUSE
    assert result.permit_after is None
    assert result.reason == CLASS_NOT_ALLOWED


@pytest.mark.parametrize(
    ("counter", "limit", "over"),
    [("spent", 40, 41), ("steps", 20, 21), ("elapsed", 40.0, 40.5)],
)
def test_exceeds_ceiling_each_counter_boundary(counter: str, limit: float, over: float) -> None:
    """Requirement 2.4: equal to the narrowed limit is admitted, one over is refused."""
    gate = make_gate(NARROW_CEILING)
    base: dict[str, float] = {"steps": 0, "spent": 0, "elapsed": 0.0}
    at_limit = gate.admit(issue(), REQUEST, **{**base, counter: limit})  # type: ignore[arg-type]
    assert at_limit.decision == ADMIT_IMPOSED
    refused = gate.admit(issue(), REQUEST, **{**base, counter: over})  # type: ignore[arg-type]
    assert refused.decision == REFUSE
    assert refused.permit_after is None
    assert refused.reason == EXCEEDS_CEILING


def test_zero_limit_ceiling() -> None:
    """Requirement 2.4: a zero-limit ceiling admits zero counters and refuses anything above."""
    zero = Permit(0.0, 0, 0, frozenset())
    gate = make_gate(zero)
    admitted = gate.admit(issue(), REQUEST, 0, 0, 0.0)
    assert admitted.decision == ADMIT_IMPOSED
    assert admitted.permit_after == zero
    for steps, spent, elapsed in [(1, 0, 0.0), (0, 1, 0.0), (0, 0, 0.5)]:
        refused = gate.admit(issue(), REQUEST, steps, spent, elapsed)
        assert refused.decision == REFUSE
        assert refused.reason == EXCEEDS_CEILING


def test_admit_unchanged() -> None:
    """Requirement 2.5: narrowing changes nothing, so ADMIT with the permit unchanged."""
    result = make_gate(WIDER_CEILING).admit(issue(), REQUEST, 0, 0, 0.0)
    assert result.decision == ADMIT
    assert result.reason == OK
    assert result.permit_after is REQUEST


def test_admit_imposed() -> None:
    """Requirement 2.6: narrowing changes a field, so ADMIT_IMPOSED with the narrowed permit."""
    result = make_gate(NARROW_CEILING).admit(issue(), REQUEST, 0, 0, 0.0)
    assert result.decision == ADMIT_IMPOSED
    assert result.reason == OK
    assert result.permit_after == REQUEST.narrowed_by(NARROW_CEILING)
    assert result.permit_after is not None
    assert result.permit_after.allowance != REQUEST.allowance
    assert result.permit_after.allowed_actions != REQUEST.allowed_actions


def test_bad_signature_beats_class() -> None:
    """Requirements 2.2, 2.3: the identity check comes before the class check."""
    tampered = dataclasses.replace(issue("spy"), agent_id="evil")
    result = make_gate(WIDER_CEILING).admit(tampered, REQUEST, 0, 0, 0.0)
    assert result.reason == BAD_SIGNATURE


def test_class_beats_exceeded_counters() -> None:
    """Requirements 2.3, 2.4: the class check comes before the counter check."""
    result = make_gate(WIDER_CEILING).admit(issue("spy"), REQUEST, 10**6, 10**6, 10.0**6)
    assert result.reason == CLASS_NOT_ALLOWED


def test_exceeded_counters_refuse_before_admit() -> None:
    """Requirement 2.4: exceeded counters refuse even when the permit would be admitted."""
    unchanged = make_gate(WIDER_CEILING).admit(issue(), REQUEST, 0, 61, 0.0)
    imposed = make_gate(NARROW_CEILING).admit(issue(), REQUEST, 0, 41, 0.0)
    for result in (unchanged, imposed):
        assert result.decision == REFUSE
        assert result.permit_after is None
        assert result.reason == EXCEEDS_CEILING
