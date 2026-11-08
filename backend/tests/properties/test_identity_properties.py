"""Property tests for Authority and Identity (CONTRACTS section 3)."""

from __future__ import annotations

from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from hypothesis import given
from hypothesis import strategies as st

from telepermit.identity import Authority

names = st.text(min_size=1, max_size=20)
seeds = st.binary(min_size=0, max_size=64)
issued_ats = st.floats(min_value=0, max_value=1e9, allow_nan=False, allow_infinity=False)


def raw_public(authority: Authority) -> bytes:
    return authority.public_key.public_bytes(Encoding.Raw, PublicFormat.Raw)


@given(name=names, seed=seeds, other=seeds, agent_id=names, agent_class=names, issued_at=issued_ats)
def test_p1_7_seeded_determinism(
    name: str, seed: bytes, other: bytes, agent_id: str, agent_class: str, issued_at: float
) -> None:
    """Property P1.7: same seed gives identical signatures and equal public keys; different
    seeds give different public keys. Validates: Requirements 1.8"""
    first = Authority.from_seed(name, seed)
    second = Authority.from_seed(name, seed)
    assert raw_public(first) == raw_public(second)
    assert first.issue(agent_id, agent_class, issued_at) == second.issue(
        agent_id, agent_class, issued_at
    )
    if other != seed:
        assert raw_public(Authority.from_seed(name, other)) != raw_public(first)
