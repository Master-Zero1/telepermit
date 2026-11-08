"""Unit tests for Authority and Identity (CONTRACTS section 3, tasks 4.1 and 5.1)."""

from __future__ import annotations

import copy
import dataclasses
import hashlib
import json
import pickle

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from telepermit.identity import Authority, Identity

SEED = b"unit-test-seed"


def private_bytes_of_seeded(seed: bytes) -> bytes:
    """The raw private key that Authority.from_seed(name, seed) must derive (CONTRACTS 3)."""
    return hashlib.sha256(seed).digest()


def canonical(agent_id: str, agent_class: str, authority: str, issued_at: float) -> bytes:
    """Independent copy of the CONTRACTS section 3 payload, so the test does not trust the code."""
    return json.dumps(
        {
            "agent_id": agent_id,
            "agent_class": agent_class,
            "authority": authority,
            "issued_at": issued_at,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def test_signature_hex_length() -> None:
    """Requirement 1.4: a 64-byte signature whose signature_hex is 128 hex characters."""
    identity = Authority("home").issue("agent-1", "bot", 0.0)
    assert isinstance(identity, Identity)
    assert len(identity.signature) == 64
    assert len(identity.signature_hex) == 128
    assert identity.signature_hex == identity.signature.hex()
    int(identity.signature_hex, 16)


def test_issue_signs_canonical_payload() -> None:
    """Requirement 1.4: the signature validates over the CONTRACTS section 3 payload."""
    authority = Authority("home")
    identity = authority.issue("agent-1", "bot", 12.5)
    assert (identity.agent_id, identity.agent_class) == ("agent-1", "bot")
    assert (identity.authority, identity.issued_at) == ("home", 12.5)
    payload = canonical("agent-1", "bot", "home", 12.5)
    authority.public_key.verify(identity.signature, payload)


def test_identity_is_frozen() -> None:
    identity = Authority("home").issue("agent-1", "bot", 0.0)
    with pytest.raises(dataclasses.FrozenInstanceError):
        identity.agent_id = "other"  # type: ignore[misc]


def test_authority_hides_key_material() -> None:
    """Requirement 1.7: no key material in repr, str, dir or public attribute values."""
    authority = Authority.from_seed("home", SEED)
    private = private_bytes_of_seeded(SEED)
    secrets = {private.hex(), repr(private), str(list(private))}
    public_raw = authority.public_key.public_bytes(Encoding.Raw, PublicFormat.Raw)
    assert public_raw != private

    for text in (repr(authority), str(authority)):
        assert "home" in text
        assert not any(secret in text for secret in secrets)

    assert not hasattr(authority, "__dict__")
    for name in dir(authority):
        if name.startswith("_"):
            continue
        value = getattr(authority, name)
        if callable(value):
            continue
        assert value != private
        assert not any(secret in repr(value) for secret in secrets)

    for slot in type(authority).__slots__:
        assert not any(secret in repr(getattr(authority, slot)) for secret in secrets)


def test_authority_cannot_be_pickled_or_copied() -> None:
    """Requirement 1.7: serialisation and copying raise TypeError."""
    authority = Authority("home")
    with pytest.raises(TypeError):
        pickle.dumps(authority)
    with pytest.raises(TypeError):
        copy.copy(authority)
    with pytest.raises(TypeError):
        copy.deepcopy(authority)


def test_from_seed_docstring_says_demo_only() -> None:
    """Requirement 1.8: the from_seed docstring states DEMO ONLY."""
    assert Authority.from_seed.__doc__ is not None
    assert "DEMO ONLY" in Authority.from_seed.__doc__


def test_from_seed_matches_sha256_of_seed() -> None:
    """Requirement 1.8: the seeded public key is the one derived from sha256(seed)."""
    expected = Ed25519PrivateKey.from_private_bytes(private_bytes_of_seeded(SEED)).public_key()
    actual = Authority.from_seed("home", SEED).public_key
    assert actual.public_bytes(Encoding.Raw, PublicFormat.Raw) == expected.public_bytes(
        Encoding.Raw, PublicFormat.Raw
    )
