# Implementation Plan: permit-identity

## Overview

Implements the Permit (CONTRACTS section 2) and the signed Identity, Authority and verifier (CONTRACTS section 3), in the order of roadmap items T1.1 to T1.5. Language: Python. Branch: `spec/01-permit-identity`.

Every task with both code and tests follows the same order: write the tests first, run them and confirm they fail for the expected reason (missing import or missing attribute, not a typo), then implement and re-run to green. Lint steps are separate single commands. After each task print the quality.md line: `DONE T<id>: <one line>. Tests: <passed>/<total>. Ruff: clean. Files: <list>.`

All seven property tests are required. Each property test docstring has the form `Property P1.n: <statement>. Validates: Requirements 1.x`, and the Hypothesis profile from the existing conftest (deadline none, 200 examples) applies.

## Tasks

- [ ] 1. T1.1 Permit dataclass
  - Note: the design's extra validation is part of this task and gets tests too: `bool` or `float` for `max_steps` and `allowance` raises TypeError, a bare `str` for `allowed_actions` raises TypeError, non-finite `lifetime_s` (NaN, infinity) raises ValueError, and an `int` `lifetime_s` is coerced to float. The design's pickle and copy TypeError belongs to the Authority and is covered in task 4.
  - Edge cases: zero values are valid; empty `allowed_actions`; int vs float `lifetime_s`.
  - _Requirements: 1.1_

  - [ ] 1.1 Create the test folders and write the Permit unit tests first
    - Files: `backend/tests/unit/test_permit.py` (new). Create `backend/tests/unit/` and `backend/tests/properties/`. No `__init__.py` is needed: the existing layout has a single top-level conftest and every test file name is unique.
    - Write `test_negative_values_raise_value_error` (each of `lifetime_s`, `max_steps`, `allowance` negative, one at a time, and the value just below zero).
    - Write `test_zero_limits_and_empty_actions_valid` (all zeros, empty `allowed_actions`, empty frozenset after coercion).
    - Write tests for: int `lifetime_s` equals the same float, list/set/tuple coerced to frozenset, `bool` or `float` for the int fields raises TypeError, bare `str` for `allowed_actions` raises TypeError, NaN and infinity raise ValueError, the Permit is frozen (assignment raises).
    - Run `uv --directory backend run pytest -q tests/unit/test_permit.py` and confirm it fails because `telepermit.permit` cannot be imported.
    - _Requirements: 1.1_

  - [ ] 1.2 Implement Permit and make the tests pass
    - Files: `backend/src/telepermit/permit.py` (new). Start with `from __future__ import annotations` and a docstring naming CONTRACTS section 2. Frozen, slotted dataclass with validation and coercion in `__post_init__` as in the design.
    - Run `uv --directory backend run pytest -q tests/unit/test_permit.py` and confirm green.
    - Run `uv --directory backend run ruff check .`
    - Run `uv --directory backend run ruff format --check .`
    - Update docs/PROGRESS.md and print the DONE line.
    - _Requirements: 1.1_

- [ ] 2. T1.2 narrowed_by
  - Depends on T1.1. Edge cases: disjoint action sets give empty; identical permits give an equal result; a ceiling with zero fields.
  - _Requirements: 1.2_

  - [ ] 2.1 Write the narrowing unit tests first
    - Files: `backend/tests/unit/test_permit.py`.
    - Write `test_narrowing_zero_and_equal_boundaries`: known inputs with expected output, values equal to the ceiling stay equal, one over the ceiling is clamped, zero ceiling fields give zero, disjoint actions give an empty set, identical permits give an equal result, inputs are not mutated.
    - Run `uv --directory backend run pytest -q tests/unit/test_permit.py` and confirm the new test fails because `narrowed_by` does not exist.
    - _Requirements: 1.2_

  - [ ] 2.2 Write property test P1.1 (narrowing never widens)
    - Files: `backend/tests/properties/test_permit_properties.py` (new). Define the shared Permit strategy here (include zero values and empty action sets).
    - Test function `test_p1_1_narrowing_never_widens`. Docstring: "Property P1.1: every field of p.narrowed_by(c) is <= both inputs and the action set is a subset of both. Validates: Requirements 1.2".
    - Run `uv --directory backend run pytest -q tests/properties/test_permit_properties.py` and confirm it fails because `narrowed_by` does not exist.
    - **Property 1: P1.1 Narrowing never widens**
    - **Validates: Requirements 1.2**

  - [ ] 2.3 Write property test P1.2 (narrowing is idempotent)
    - Files: `backend/tests/properties/test_permit_properties.py`.
    - Test function `test_p1_2_narrowing_idempotent`. Docstring: "Property P1.2: p.narrowed_by(c).narrowed_by(c) equals p.narrowed_by(c). Validates: Requirements 1.2".
    - Run `uv --directory backend run pytest -q tests/properties/test_permit_properties.py` and confirm it fails because `narrowed_by` does not exist.
    - **Property 2: P1.2 Narrowing is idempotent**
    - **Validates: Requirements 1.2**

  - [ ] 2.4 Implement narrowed_by and make the tests pass
    - Files: `backend/src/telepermit/permit.py`. Component-wise minimum for the three numeric fields, set intersection for actions, returns a new Permit.
    - Run `uv --directory backend run pytest -q tests/unit/test_permit.py`
    - Run `uv --directory backend run pytest -q tests/properties/test_permit_properties.py`
    - Run `uv --directory backend run ruff check .`
    - Run `uv --directory backend run ruff format --check .`
    - Update docs/PROGRESS.md and print the DONE line.
    - _Requirements: 1.2_

- [ ] 3. T1.3 Permit JSON serialisation
  - Depends on T1.1. Edge cases: empty action list; unicode action names; float precision for `lifetime_s`.
  - _Requirements: 1.3_

  - [ ] 3.1 Write the JSON unit test first
    - Files: `backend/tests/unit/test_permit.py`.
    - Write `test_to_json_shape_and_sorted_actions`: exactly the four keys, `allowed_actions` is a sorted list, empty list case, unicode names, missing key in `from_json` raises KeyError.
    - Run `uv --directory backend run pytest -q tests/unit/test_permit.py` and confirm the new test fails because `to_json` does not exist.
    - _Requirements: 1.3_

  - [ ] 3.2 Write property test P1.3 (JSON round trip)
    - Files: `backend/tests/properties/test_permit_properties.py`.
    - Test function `test_p1_3_json_round_trip`. Include a pass through `json.dumps` and `json.loads`, and text strategies that cover unicode action names. Docstring: "Property P1.3: Permit.from_json(p.to_json()) equals p, also through json.dumps and json.loads. Validates: Requirements 1.3".
    - Run `uv --directory backend run pytest -q tests/properties/test_permit_properties.py` and confirm the new test fails because `to_json` does not exist.
    - **Property 3: P1.3 Permit JSON round trip**
    - **Validates: Requirements 1.3**

  - [ ] 3.3 Implement to_json and from_json and make the tests pass
    - Files: `backend/src/telepermit/permit.py`. `from_json` goes through the constructor so it gets the same validation.
    - Run `uv --directory backend run pytest -q tests/unit/test_permit.py`
    - Run `uv --directory backend run pytest -q tests/properties/test_permit_properties.py`
    - Run `uv --directory backend run ruff check .`
    - Run `uv --directory backend run ruff format --check .`
    - Update docs/PROGRESS.md and print the DONE line.
    - _Requirements: 1.3_

- [ ] 4. T1.4 Authority and Identity
  - Depends on T0.2 only. Edge cases: deterministic seeded keys; the `from_seed` docstring says "DEMO ONLY"; `repr(authority)` leaks no key material.
  - _Requirements: 1.4, 1.7, 1.8_

  - [ ] 4.1 Write the Authority and Identity unit tests first
    - Files: `backend/tests/unit/test_identity.py` (new).
    - Write `test_signature_hex_length`: `issue(...)` returns an Identity whose `signature_hex` is 128 hex chars and whose signature is 64 bytes.
    - Write `test_issue_signs_canonical_payload`: the signature validates against the canonical payload with the Authority's public key, using the `cryptography` library directly.
    - Write `test_authority_hides_key_material`: `repr`, `str`, `dir()` and the attribute names and values listed through `__slots__` contain no private key bytes (raw or hex) and no public attribute returns private bytes.
    - Write `test_authority_cannot_be_pickled_or_copied`: `pickle.dumps`, `copy.copy` and `copy.deepcopy` each raise TypeError.
    - Write `test_from_seed_docstring_says_demo_only`: `Authority.from_seed.__doc__` contains "DEMO ONLY".
    - Also assert Identity is frozen.
    - Run `uv --directory backend run pytest -q tests/unit/test_identity.py` and confirm it fails because `telepermit.identity` cannot be imported.
    - _Requirements: 1.4, 1.7, 1.8_

  - [ ] 4.2 Write property test P1.7 (seeded determinism)
    - Files: `backend/tests/properties/test_identity_properties.py` (new). Define the shared strategies here (agent fields, issued_at floats, seed bytes).
    - Test function `test_p1_7_seeded_determinism`. Docstring: "Property P1.7: same seed gives identical signatures and equal public keys; different seeds give different public keys. Validates: Requirements 1.8".
    - Run `uv --directory backend run pytest -q tests/properties/test_identity_properties.py` and confirm it fails because `telepermit.identity` cannot be imported.
    - **Property 7: P1.7 Seeded determinism**
    - **Validates: Requirements 1.8**

  - [ ] 4.3 Implement Identity, Authority and the canonical payload helper
    - Files: `backend/src/telepermit/identity.py` (new). Start with `from __future__ import annotations` and a docstring naming CONTRACTS section 3. Define the `Identity` dataclass with `signature_hex`, the single `_canonical_payload` helper, and `Authority` with a private slot for the key, `from_seed` (sha256 of the seed, docstring and class docstring containing "DEMO ONLY"), `public_key`, `issue`, `repr` and `str` without key material, and `TypeError` for pickle and copy.
    - Run `uv --directory backend run pytest -q tests/unit/test_identity.py`
    - Run `uv --directory backend run pytest -q tests/properties/test_identity_properties.py`
    - Run `uv --directory backend run ruff check .`
    - Run `uv --directory backend run ruff format --check .`
    - Update docs/PROGRESS.md and print the DONE line.
    - _Requirements: 1.4, 1.7, 1.8_

- [ ] 5. T1.5 verify_identity
  - Depends on T1.4. Edge cases: empty signature bytes; signature lengths 0 to 200; empty trusted map; authority name present but wrong key. Result codes are module constants defined once.
  - _Requirements: 1.4, 1.5, 1.6_

  - [ ] 5.1 Write the verifier unit tests first
    - Files: `backend/tests/unit/test_identity.py`.
    - Write `test_verify_result_codes`: a valid identity gives None, an unknown authority gives UNTRUSTED_AUTHORITY, an authority name changed to another name that is still in the map gives BAD_SIGNATURE, a tampered field gives BAD_SIGNATURE.
    - Write `test_wrong_length_signatures_bad_signature`: signature lengths 0, 1, 63, 65 and 200 each return BAD_SIGNATURE without raising, and a 64-byte signature of zeros does too.
    - Run `uv --directory backend run pytest -q tests/unit/test_identity.py` and confirm the new tests fail because `verify_identity` does not exist.
    - _Requirements: 1.5, 1.6_

  - [ ] 5.2 Write property test P1.4 (tampering fails verification)
    - Files: `backend/tests/properties/test_identity_properties.py`.
    - Test function `test_p1_4_tampering_fails_verification`. Change one of `agent_id`, `agent_class`, `authority` (the new name must stay in the trust map under the same key) or `issued_at`, making sure the new value really differs, or flip one bit of the signature. The unmodified identity verifies as None. Docstring: "Property P1.4: changing any one field of a signed identity, or flipping any single bit of the signature, makes verification return BAD_SIGNATURE. Validates: Requirements 1.4, 1.5".
    - Run `uv --directory backend run pytest -q tests/properties/test_identity_properties.py` and confirm it fails because `verify_identity` does not exist.
    - **Property 4: P1.4 Any change to an identity or its signature fails verification**
    - **Validates: Requirements 1.4, 1.5**

  - [ ] 5.3 Write property test P1.5 (wrong key and empty trust map)
    - Files: `backend/tests/properties/test_identity_properties.py`.
    - Test function `test_p1_5_wrong_key_and_empty_trust`. Docstring: "Property P1.5: a valid identity verified against a different key under the same authority name returns BAD_SIGNATURE; against an empty trust map returns UNTRUSTED_AUTHORITY. Validates: Requirements 1.5".
    - Run `uv --directory backend run pytest -q tests/properties/test_identity_properties.py` and confirm it fails because `verify_identity` does not exist.
    - **Property 5: P1.5 Wrong key and empty trust map**
    - **Validates: Requirements 1.5**

  - [ ] 5.4 Write property test P1.6 (verification never raises)
    - Files: `backend/tests/properties/test_identity_properties.py`.
    - Test function `test_p1_6_verify_never_raises`: arbitrary signature bytes of length 0 to 200; result is one of None, UNTRUSTED_AUTHORITY or BAD_SIGNATURE, and anything other than the genuine signature gives BAD_SIGNATURE. Docstring: "Property P1.6: verification never raises for arbitrary signature bytes of length 0 to 200. Validates: Requirements 1.6".
    - Run `uv --directory backend run pytest -q tests/properties/test_identity_properties.py` and confirm it fails because `verify_identity` does not exist.
    - **Property 6: P1.6 Verification never raises**
    - **Validates: Requirements 1.6**

  - [ ] 5.5 Implement verify_identity and make the tests pass
    - Files: `backend/src/telepermit/identity.py`. Decision order as in the design: unknown authority first, then length check (64), then `verify` inside a `try` that catches only `InvalidSignature` and `ValueError`. No bare `except`. Constants `UNTRUSTED_AUTHORITY` and `BAD_SIGNATURE` defined once.
    - Run `uv --directory backend run pytest -q tests/unit/test_identity.py`
    - Run `uv --directory backend run pytest -q tests/properties/test_identity_properties.py`
    - Run `uv --directory backend run ruff check .`
    - Run `uv --directory backend run ruff format --check .`
    - Update docs/PROGRESS.md and print the DONE line.
    - _Requirements: 1.4, 1.5, 1.6_

- [ ] 6. Final checkpoint - Ensure all tests pass
  - Run `uv --directory backend run pytest -q` and confirm every unit test and all seven properties (P1.1 to P1.7) pass.
  - Run `uv --directory backend run ruff check .`
  - Run `uv --directory backend run ruff format --check .`
  - Update docs/PROGRESS.md (spec folder name, branch, completed items).
  - Print the DONE line with the real passed/total counts. Ensure all tests pass, ask the user if questions arise.
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8_

## Notes

- Nothing is built beyond requirements 1.1 to 1.8 and the approved design. No dependency outside tech.md is added.
- Test files are shared between tasks, so the dependency graph keeps tasks that write to the same file in different waves.
- A task is done only when its tests were run in the session, ruff check and ruff format check are clean, and PROGRESS.md is updated.

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["1.2", "4.1"] },
    { "id": 2, "tasks": ["2.1", "2.2", "4.2"] },
    { "id": 3, "tasks": ["2.3", "3.1", "4.3"] },
    { "id": 4, "tasks": ["2.4", "3.2", "5.1"] },
    { "id": 5, "tasks": ["3.3", "5.2"] },
    { "id": 6, "tasks": ["5.3"] },
    { "id": 7, "tasks": ["5.4"] },
    { "id": 8, "tasks": ["5.5"] }
  ]
}
```
