"""Property tests for Place.admit (CONTRACTS section 4)."""

from __future__ import annotations

import dataclasses

from hypothesis import assume, given
from hypothesis import strategies as st

from telepermit.identity import BAD_SIGNATURE, UNTRUSTED_AUTHORITY, Authority, verify_identity
from telepermit.permit import Permit
from telepermit.place import (
    ADMIT,
    ADMIT_IMPOSED,
    CLASS_NOT_ALLOWED,
    EXCEEDS_CEILING,
    OK,
    REFUSE,
    Place,
)

# DEMO ONLY seeded authority, fine for tests.
AUTHORITY = Authority.from_seed("home", b"place-properties")
BOT_ONLY = frozenset({"bot"})
ACTIONS = st.sampled_from(["a", "b", "c", "d"])

permits = st.builds(
    Permit,
    lifetime_s=st.floats(min_value=0, max_value=1000, allow_nan=False, allow_infinity=False),
    max_steps=st.integers(min_value=0, max_value=1000),
    allowance=st.integers(min_value=0, max_value=1000),
    allowed_actions=st.frozensets(ACTIONS),
)


def make_gate(ceiling: Permit) -> Place:
    return Place("gate", {}, ceiling, {"home": AUTHORITY.public_key}, BOT_ONLY)


@st.composite
def arrivals(draw: st.DrawFn) -> tuple[Permit, Permit, int, int, float]:
    """A permit, a ceiling and counters that do not exceed the narrowed limits."""
    permit = draw(permits)
    kind = draw(st.sampled_from(["any", "equal", "wider"]))
    if kind == "any":
        ceiling = draw(permits)
    elif kind == "equal":
        ceiling = permit
    else:
        ceiling = Permit(
            permit.lifetime_s + 1,
            permit.max_steps + 1,
            permit.allowance + 1,
            permit.allowed_actions | frozenset({"x"}),
        )
    narrowed = permit.narrowed_by(ceiling)
    steps = draw(st.integers(min_value=0, max_value=narrowed.max_steps))
    spent = draw(st.integers(min_value=0, max_value=narrowed.allowance))
    elapsed = draw(
        st.floats(
            min_value=0.0, max_value=narrowed.lifetime_s, allow_nan=False, allow_infinity=False
        )
    )
    return permit, ceiling, steps, spent, elapsed


# Feature: tools-places-admission, Property 1
@given(arrival=arrivals())
def test_p2_1_permit_after_never_wider(arrival: tuple[Permit, Permit, int, int, float]) -> None:
    """Property P2.1: permit_after is never wider than the requested permit or the ceiling, on
    any field. Validates: Requirements 2.5, 2.6"""
    permit, ceiling, steps, spent, elapsed = arrival
    identity = AUTHORITY.issue("agent-1", "bot", 0.0)
    after = make_gate(ceiling).admit(identity, permit, steps, spent, elapsed).permit_after
    assert after is not None
    for source in (permit, ceiling):
        assert after.lifetime_s <= source.lifetime_s
        assert after.max_steps <= source.max_steps
        assert after.allowance <= source.allowance
        assert after.allowed_actions <= source.allowed_actions


# Feature: tools-places-admission, Property 2
@given(
    kind=st.sampled_from(["unknown", "bad_signature", "bad_field", "class"]),
    other=st.text(min_size=1, max_size=10),
    bit=st.integers(min_value=0, max_value=511),
    permit=permits,
    ceiling=permits,
    steps=st.integers(min_value=0, max_value=10**6),
    spent=st.integers(min_value=0, max_value=10**6),
    elapsed=st.floats(min_value=0, max_value=1e6, allow_nan=False, allow_infinity=False),
)
def test_p2_2_bad_identity_or_class_refused(
    kind: str,
    other: str,
    bit: int,
    permit: Permit,
    ceiling: Permit,
    steps: int,
    spent: int,
    elapsed: float,
) -> None:
    """Property P2.2: an identity with an unknown authority, a corrupted signature, or a
    disallowed class is always refused. Validates: Requirements 2.2, 2.3"""
    identity = AUTHORITY.issue("agent-1", "bot", 0.0)
    if kind == "unknown":
        assume(other != "home")
        identity = Authority.from_seed(other, b"stranger").issue("agent-1", "bot", 0.0)
    elif kind == "bad_signature":
        flipped = bytearray(identity.signature)
        flipped[bit // 8] ^= 1 << (bit % 8)
        identity = dataclasses.replace(identity, signature=bytes(flipped))
    elif kind == "bad_field":
        assume(other != identity.agent_id)
        identity = dataclasses.replace(identity, agent_id=other)
    else:
        assume(other != "bot")
        identity = AUTHORITY.issue("agent-1", other, 0.0)
    gate = make_gate(ceiling)
    result = gate.admit(identity, permit, steps, spent, elapsed)
    assert result.decision == REFUSE
    assert result.permit_after is None
    if kind == "class":
        assert result.reason == CLASS_NOT_ALLOWED
    else:
        assert result.reason in (UNTRUSTED_AUTHORITY, BAD_SIGNATURE)
        assert result.reason == verify_identity(identity, gate.trusted)


# Feature: tools-places-admission, Property 3
@given(arrival=arrivals())
def test_p2_3_admit_iff_unchanged(arrival: tuple[Permit, Permit, int, int, float]) -> None:
    """Property P2.3: ADMIT happens if and only if narrowing changes nothing; otherwise
    ADMIT_IMPOSED. Validates: Requirements 2.5, 2.6"""
    permit, ceiling, steps, spent, elapsed = arrival
    narrowed = permit.narrowed_by(ceiling)
    identity = AUTHORITY.issue("agent-1", "bot", 0.0)
    result = make_gate(ceiling).admit(identity, permit, steps, spent, elapsed)
    assert result.reason == OK
    if narrowed == permit:
        assert result.decision == ADMIT
        assert result.permit_after == permit
    else:
        assert result.decision == ADMIT_IMPOSED
        assert result.permit_after == narrowed


# Feature: tools-places-admission, Property 4
@given(
    permit=permits,
    ceiling=permits,
    which=st.sampled_from(["spent", "steps", "elapsed"]),
    extra=st.integers(min_value=1, max_value=100),
)
def test_p2_4_exceeded_counters_refused(
    permit: Permit, ceiling: Permit, which: str, extra: int
) -> None:
    """Property P2.4: if counters exceed the narrowed limits the decision is REFUSE with
    EXCEEDS_CEILING, never an admission. Validates: Requirements 2.4"""
    narrowed = permit.narrowed_by(ceiling)
    counters = {
        "steps": narrowed.max_steps,
        "spent": narrowed.allowance,
        "elapsed": narrowed.lifetime_s,
    }
    gate = make_gate(ceiling)
    identity = AUTHORITY.issue("agent-1", "bot", 0.0)
    at_limit = gate.admit(identity, permit, **counters)  # type: ignore[arg-type]
    assert at_limit.decision != REFUSE
    counters[which] += extra
    over = gate.admit(identity, permit, **counters)  # type: ignore[arg-type]
    assert over.decision == REFUSE
    assert over.permit_after is None
    assert over.reason == EXCEEDS_CEILING
