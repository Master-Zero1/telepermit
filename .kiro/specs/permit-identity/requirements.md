# Requirements Document

## Introduction

This spec covers the first building block of TelePermit: an immutable Permit that bounds an agent, and an Ed25519-signed Identity that an Authority issues and a verifier checks. It is pure library code with no I/O and no network. The behaviour is defined by CONTRACTS sections 2 and 3, which are binding.

Criterion IDs 1.1 to 1.8 are the seed reference IDs, and Requirement N holds criterion 1.N.

Note for design (no scope change): when the `authority` field of a signed Identity is changed to a name absent from the trusted mapping, verification returns UNTRUSTED_AUTHORITY, not BAD_SIGNATURE. BAD_SIGNATURE applies when the changed authority name is still present in the trusted mapping. The P1.4 test must keep the altered authority name in the trust map.

## Glossary

- **Permit**: Immutable value with fields `lifetime_s` (float), `max_steps` (int), `allowance` (int, teleclicks) and `allowed_actions` (frozenset of str).
- **Ceiling**: A Permit used as the upper bound in a narrowing operation.
- **Identity**: Immutable value with fields `agent_id`, `agent_class`, `authority`, `issued_at` and `signature` (bytes).
- **Authority**: Object that holds an Ed25519 private key and issues Identity values.
- **Verifier**: The function `verify_identity(identity, trusted)`, where `trusted` maps authority names to Ed25519 public keys.
- **Canonical_Payload**: The bytes `json.dumps({"agent_id","agent_class","authority","issued_at"}, sort_keys=True, separators=(",", ":")).encode("utf-8")`, built from the Identity fields of the same names.
- **UNTRUSTED_AUTHORITY**: Verifier result string meaning the authority name is not in `trusted`.
- **BAD_SIGNATURE**: Verifier result string meaning the signature does not validate for a trusted authority name.
- **Demo_Seed_Key**: An Ed25519 private key derived from `sha256(seed)` by `Authority.from_seed`, for demo use only.

## Requirements

### Requirement 1: Permit validation

**User Story:** As a runtime developer, I want invalid Permit values rejected at construction, so that no Permit with a negative limit can exist.

#### Acceptance Criteria

1.1. WHEN a Permit is constructed with a negative `lifetime_s`, a negative `max_steps` or a negative `allowance`, THE Permit SHALL raise ValueError.

### Requirement 2: Permit narrowing

**User Story:** As a runtime developer, I want to narrow a Permit by a ceiling, so that an imposed Permit is never wider than either input.

#### Acceptance Criteria

1.2. WHEN a Permit is narrowed by a Ceiling, THE Permit SHALL return a new Permit whose `lifetime_s`, `max_steps` and `allowance` are the minimum of the two inputs and whose `allowed_actions` is the set intersection of the two inputs.

### Requirement 3: Permit JSON round trip

**User Story:** As a runtime developer, I want lossless Permit serialisation, so that a Permit can be stored in an audit record and restored unchanged.

#### Acceptance Criteria

1.3. THE Permit SHALL serialise with `to_json` to a mapping with keys `lifetime_s`, `max_steps`, `allowance` and `allowed_actions`, where `allowed_actions` is a sorted list, and SHALL restore an equal Permit with `from_json`.

### Requirement 4: Identity signing

**User Story:** As a place operator, I want identities signed over a fixed payload, so that any change to an identity field is detectable.

#### Acceptance Criteria

1.4. WHEN an Authority issues an Identity, THE Authority SHALL set the Identity `signature` to the Ed25519 signature of the Canonical_Payload.

### Requirement 5: Identity verification result codes

**User Story:** As a place operator, I want a verification result code, so that I can tell an unknown authority from a forged identity.

#### Acceptance Criteria

1.5. WHEN an Identity is verified against a `trusted` mapping, THE Verifier SHALL return None if the authority name is in `trusted` and the signature is valid for the Canonical_Payload, SHALL return UNTRUSTED_AUTHORITY if the authority name is not in `trusted`, and SHALL return BAD_SIGNATURE in every other case.

### Requirement 6: Verification totality

**User Story:** As a place operator, I want verification that cannot crash on hostile input, so that a malformed signature never becomes an unhandled error.

#### Acceptance Criteria

1.6. WHEN an Identity carries signature bytes of any length from 0 to 200, THE Verifier SHALL return a result without raising an exception.

### Requirement 7: Private key confinement

**User Story:** As a security reviewer, I want the private key kept inside the Authority, so that it cannot leak through inspection or logging.

#### Acceptance Criteria

1.7. THE Authority SHALL omit private key material from every public attribute, from `repr` output and from `str` output.

### Requirement 8: Deterministic seeded authority

**User Story:** As a scenario author, I want reproducible keys from a seed, so that recorded runs are byte-reproducible, with a clear demo-only warning.

#### Acceptance Criteria

1.8. WHEN `Authority.from_seed` is called with the same name and seed bytes, THE Authority SHALL derive the same Ed25519 key from `sha256(seed)` every time, and THE Authority docstring SHALL state that the Demo_Seed_Key is demo only.
