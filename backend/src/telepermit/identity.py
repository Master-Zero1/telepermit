"""Signed Identity and the Authority that issues it (CONTRACTS section 3).

Identity, the canonical payload, Authority and verify_identity.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final, NoReturn

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

UNTRUSTED_AUTHORITY: Final = "UNTRUSTED_AUTHORITY"
BAD_SIGNATURE: Final = "BAD_SIGNATURE"
_SIGNATURE_LEN: Final = 64


@dataclass(frozen=True, slots=True)
class Identity:
    """An agent identity signed by an Authority over the canonical payload."""

    agent_id: str
    agent_class: str
    authority: str
    issued_at: float
    signature: bytes

    @property
    def signature_hex(self) -> str:
        """The signature as lowercase hex (128 characters for Ed25519)."""
        return self.signature.hex()


def _canonical_payload(agent_id: str, agent_class: str, authority: str, issued_at: float) -> bytes:
    """The exact bytes that are signed and verified (CONTRACTS section 3)."""
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


class Authority:
    """Issues signed identities. DEMO ONLY when built with from_seed.

    The private key lives in one private slot and is never exposed by an attribute, repr, str,
    pickle or copy. This guards against accidental leaks. It is not a sandbox: Python name
    privacy is not a security boundary.
    """

    __slots__ = ("name", "_Authority__key")

    def __init__(self, name: str) -> None:
        self.name = name
        self.__key = Ed25519PrivateKey.generate()

    @classmethod
    def from_seed(cls, name: str, seed: bytes) -> Authority:
        """Build an Authority whose key is derived from sha256(seed).

        DEMO ONLY. The key comes from a public, guessable seed so that recorded replays are
        byte-reproducible. Never use it to protect anything real.
        """
        authority = cls.__new__(cls)
        authority.name = name
        authority.__key = Ed25519PrivateKey.from_private_bytes(hashlib.sha256(seed).digest())
        return authority

    @property
    def public_key(self) -> Ed25519PublicKey:
        """The public half of this Authority's key."""
        return self.__key.public_key()

    def issue(self, agent_id: str, agent_class: str, issued_at: float) -> Identity:
        """Sign the canonical payload and return the resulting Identity."""
        payload = _canonical_payload(agent_id, agent_class, self.name, issued_at)
        return Identity(agent_id, agent_class, self.name, issued_at, self.__key.sign(payload))

    def __repr__(self) -> str:
        return f"Authority(name={self.name!r})"

    def __str__(self) -> str:
        return repr(self)

    def __reduce__(self) -> NoReturn:
        raise TypeError("Authority cannot be pickled or copied")

    def __reduce_ex__(self, protocol: int) -> NoReturn:
        raise TypeError("Authority cannot be pickled or copied")

    def __copy__(self) -> NoReturn:
        raise TypeError("Authority cannot be pickled or copied")

    def __deepcopy__(self, memo: dict[int, object]) -> NoReturn:
        raise TypeError("Authority cannot be pickled or copied")


def verify_identity(identity: Identity, trusted: Mapping[str, Ed25519PublicKey]) -> str | None:
    """Return None if valid, UNTRUSTED_AUTHORITY if the authority is unknown, else BAD_SIGNATURE.

    Never raises for any signature bytes. A signature that is not 64 bytes is rejected before
    the library call, and the call itself can only fail with InvalidSignature or ValueError.
    """
    if identity.authority not in trusted:
        return UNTRUSTED_AUTHORITY
    if len(identity.signature) != _SIGNATURE_LEN:
        return BAD_SIGNATURE
    payload = _canonical_payload(
        identity.agent_id, identity.agent_class, identity.authority, identity.issued_at
    )
    try:
        trusted[identity.authority].verify(identity.signature, payload)
    except (InvalidSignature, ValueError):
        return BAD_SIGNATURE
    return None
