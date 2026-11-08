"""Property tests for Authority and Identity (CONTRACTS section 3)."""

from __future__ import annotations

import dataclasses

from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from hypothesis import assume, given
from hypothesis import strategies as st

from telepermit.identity import Authority, verify_identity

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


FIELDS = ["agent_id", "agent_class", "authority", "issued_at", "signature"]


def flip_bit(signature: bytes, bit: int) -> bytes:
    flipped = bytearray(signature)
    flipped[bit // 8] ^= 1 << (bit % 8)
    return bytes(flipped)


@given(
    agent_id=names,
    agent_class=names,
    issued_at=issued_ats,
    field=st.sampled_from(FIELDS),
    new_text=names,
    new_time=issued_ats,
    bit=st.integers(min_value=0, max_value=511),
)
def test_p1_4_tampering_fails_verification(
    agent_id: str,
    agent_class: str,
    issued_at: float,
    field: str,
    new_text: str,
    new_time: float,
    bit: int,
) -> None:
    """Property P1.4: changing any one field of a signed identity, or flipping any single bit of
    the signature, makes verification return BAD_SIGNATURE. Validates: Requirements 1.4, 1.5"""
    authority = Authority.from_seed("home", b"p1-4")
    key = authority.public_key
    trusted = {"home": key, "alt": key}
    identity = authority.issue(agent_id, agent_class, issued_at)
    assert verify_identity(identity, trusted) is None

    if field == "signature":
        changed = dataclasses.replace(identity, signature=flip_bit(identity.signature, bit))
    elif field == "issued_at":
        assume(new_time != issued_at)
        changed = dataclasses.replace(identity, issued_at=new_time)
    elif field == "authority":
        changed = dataclasses.replace(identity, authority="alt")
    else:
        assume(new_text != getattr(identity, field))
        changed = dataclasses.replace(identity, **{field: new_text})
    assert verify_identity(changed, trusted) == "BAD_SIGNATURE"


@given(
    name=names,
    seed=seeds,
    other_seed=seeds,
    agent_id=names,
    agent_class=names,
    issued_at=issued_ats,
)
def test_p1_5_wrong_key_and_empty_trust(
    name: str,
    seed: bytes,
    other_seed: bytes,
    agent_id: str,
    agent_class: str,
    issued_at: float,
) -> None:
    """Property P1.5: a valid identity verified against a different key under the same authority
    name returns BAD_SIGNATURE; against an empty trust map returns UNTRUSTED_AUTHORITY.
    Validates: Requirements 1.5"""
    assume(seed != other_seed)
    identity = Authority.from_seed(name, seed).issue(agent_id, agent_class, issued_at)
    wrong = {name: Authority.from_seed(name, other_seed).public_key}
    assert verify_identity(identity, wrong) == "BAD_SIGNATURE"
    assert verify_identity(identity, {}) == "UNTRUSTED_AUTHORITY"


@given(signature=st.binary(min_size=0, max_size=200), agent_id=names, issued_at=issued_ats)
def test_p1_6_verify_never_raises(signature: bytes, agent_id: str, issued_at: float) -> None:
    """Property P1.6: verification never raises for arbitrary signature bytes of length 0 to 200.
    Validates: Requirements 1.6"""
    authority = Authority.from_seed("home", b"p1-6")
    genuine = authority.issue(agent_id, "bot", issued_at)
    forged = dataclasses.replace(genuine, signature=signature)
    result = verify_identity(forged, {"home": authority.public_key})
    assert result in (None, "BAD_SIGNATURE")
    if signature != genuine.signature:
        assert result == "BAD_SIGNATURE"
