# Seed: spec 1, permit and identity

Brief for the Kiro spec workflow. Contract details: `docs/CONTRACTS.md` sections 2 and 3. Branch: `spec/01-permit-identity`.

## Goal
Immutable `Permit` with `narrowed_by`, and Ed25519-signed `Identity` with `Authority` and `verify_identity`. Pure library code, no I/O.

## Files
`backend/src/telepermit/permit.py`, `identity.py`; tests in `backend/tests/unit/` and `backend/tests/properties/`.

## Requirements to capture (EARS, number them 1.1, 1.2, ...)
1. WHEN a Permit is constructed with a negative lifetime, step limit or allowance, THE Permit SHALL raise ValueError.
2. WHEN a permit is narrowed by a ceiling, THE Permit SHALL return a new permit whose lifetime, steps and allowance are the minimum of both and whose allowed actions are the intersection.
3. THE Permit SHALL serialise to and from JSON losslessly, with allowed actions sorted.
4. WHEN an Authority issues an identity, THE Authority SHALL sign the canonical payload defined in CONTRACTS section 3 with Ed25519.
5. WHEN an identity is verified against trusted authorities, THE verifier SHALL return None if valid, "UNTRUSTED_AUTHORITY" if the authority is unknown, and "BAD_SIGNATURE" otherwise.
6. THE verifier SHALL NOT raise for any signature bytes of any length.
7. THE Authority SHALL NOT expose its private key through any attribute, repr or str.
8. WHEN an Authority is created from a seed, THE Authority SHALL derive the same key every time, and its docstring SHALL state that this is demo only.

## Correctness properties (each becomes a Hypothesis test, tagged with requirement IDs)
- P1.1 Narrowing never widens: every field of `p.narrowed_by(c)` is <= both inputs and the action set is a subset of both. (Req 1.2)
- P1.2 Narrowing is idempotent. (Req 1.2)
- P1.3 JSON round-trip returns an equal Permit for any valid permit. (Req 1.3)
- P1.4 Changing any one field of a signed identity, or flipping any single bit of the signature, makes verification return BAD_SIGNATURE. (Req 1.4, 1.5)
- P1.5 A valid identity verified against a different key under the same authority name returns BAD_SIGNATURE; against an empty trust map returns UNTRUSTED_AUTHORITY. (Req 1.5)
- P1.6 Verification never raises for arbitrary signature bytes (length 0 to 200). (Req 1.6)
- P1.7 Same seed gives identical signatures; different seeds give different public keys. (Req 1.8)
Also unit tests: negative-value ValueError; `repr(authority)` contains no key material.

## Exit criteria
In `backend/`: `uv run pytest -q` all green including the seven properties, `uv run ruff check .` and `uv run ruff format --check .` clean. PROGRESS.md updated; branch ready for `MERGE`.
