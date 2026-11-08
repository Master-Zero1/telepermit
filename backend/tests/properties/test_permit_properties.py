"""Property tests for Permit (CONTRACTS section 2)."""

from __future__ import annotations

import json

from hypothesis import given
from hypothesis import strategies as st

from telepermit.permit import Permit

_ACTIONS = st.sampled_from(["read_document", "search_archive", "read_records", "go:vault", "x"])

permits = st.builds(
    Permit,
    lifetime_s=st.floats(min_value=0, max_value=1e6, allow_nan=False, allow_infinity=False),
    max_steps=st.integers(min_value=0, max_value=10_000),
    allowance=st.integers(min_value=0, max_value=10_000),
    allowed_actions=st.frozensets(_ACTIONS),
)


@given(p=permits, c=permits)
def test_p1_1_narrowing_never_widens(p: Permit, c: Permit) -> None:
    """Property P1.1: every field of p.narrowed_by(c) is <= both inputs and the action set is a
    subset of both. Validates: Requirements 1.2"""
    n = p.narrowed_by(c)
    for src in (p, c):
        assert n.lifetime_s <= src.lifetime_s
        assert n.max_steps <= src.max_steps
        assert n.allowance <= src.allowance
        assert n.allowed_actions <= src.allowed_actions


@given(p=permits, c=permits)
def test_p1_2_narrowing_idempotent(p: Permit, c: Permit) -> None:
    """Property P1.2: p.narrowed_by(c).narrowed_by(c) equals p.narrowed_by(c).
    Validates: Requirements 1.2"""
    assert p.narrowed_by(c).narrowed_by(c) == p.narrowed_by(c)


@given(
    p=st.builds(
        Permit,
        lifetime_s=st.floats(min_value=0, max_value=1e9, allow_nan=False, allow_infinity=False),
        max_steps=st.integers(min_value=0, max_value=10**9),
        allowance=st.integers(min_value=0, max_value=10**9),
        allowed_actions=st.frozensets(st.text(max_size=12), max_size=8),
    )
)
def test_p1_3_json_round_trip(p: Permit) -> None:
    """Property P1.3: Permit.from_json(p.to_json()) equals p, also through json.dumps and
    json.loads. Validates: Requirements 1.3"""
    data = p.to_json()
    assert data["allowed_actions"] == sorted(p.allowed_actions)
    assert Permit.from_json(data) == p
    assert Permit.from_json(json.loads(json.dumps(data))) == p
