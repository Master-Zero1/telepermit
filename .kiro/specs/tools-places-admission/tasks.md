# Implementation Plan: tools-places-admission

## Overview

Implements the Tool and Place models, the four-tool catalog and the border check (CONTRACTS section 4, document text from section 8), in the order of roadmap items T2.1 to T2.3. Language: Python. Branch: `spec/02-tools-places-admission`. Design decision already approved: Outbox Option B. `Place` keeps exactly the CONTRACTS fields and the Outbox is read through `VaultTools.outbox`.

Order of build:
- T2.1 builds `Tool` (in `tools.py`) and `Place` with `has_tool`, `tool_cost`, `execute`, `UnknownToolError` and the `Admission` data model (in `place.py`). No `admit` yet.
- T2.2 builds the catalog: `library_tools`, `vault_tools`, `VaultTools`, the name, cost and text constants, `BRIEFING_Q3_TEXT`, `ToolArgumentError`.
- T2.3 builds `Place.admit`, following the four CONTRACTS steps in exact order.

Hand-off mode: the human runs every command and pastes the output. Each test sub-task states the exact command and the expected result. Every task with both code and tests follows the same order: write the tests first, run them, confirm they fail for the stated reason (ModuleNotFoundError for a missing module, ImportError for a missing name, AttributeError for a missing method), then implement and re-run to green. Lint steps are separate single commands, never chained.

All five property tests (P2.1 to P2.5) are required, none optional. Each property docstring has the form `Property P2.n: <statement>. Validates: Requirements 2.x`. The Hypothesis profile in the existing conftest (deadline none, 200 examples) applies.

Conventions that apply to every file written in this spec:
- Start each Python module with `from __future__ import annotations`. Source modules have a docstring naming the CONTRACTS section they implement.
- Ruff isort: a blank line between third-party imports (pytest, hypothesis, cryptography) and `from telepermit...` imports, otherwise ruff reports I001.
- Every file ends with exactly one trailing newline (otherwise `ruff format --check` fails). Write LF line endings.
- The existing `test_permit.py`, `test_identity.py` and the two existing property files are not touched. All test files named below are new.
- `tests/unit/` and `tests/properties/` already exist. Create no folders and no `__init__.py`.
- Tests define their own small helpers inline (build an `Authority` with `Authority.from_seed` and a fixed seed, which is DEMO ONLY and fine in tests; build a `Place`; build an `Identity`). No shared test helper module.
- Tests may call `Place.execute`. No source module calls it (security invariant 1). Nothing imports `engine`, `drivers` or `audit`.
- Constants (tool names, costs, decisions, reason strings) are defined once and imported. Verification codes `UNTRUSTED_AUTHORITY` and `BAD_SIGNATURE` are imported from `identity.py`, never retyped.
- After each top-level task print: `DONE T<id>: <one line>. Tests: <passed>/<total>. Ruff: clean. Files: <list>.`

## Tasks

- [x] 1. T2.1 Tool and Place models
  - Builds `Tool`, `UnknownToolError`, `Place` (without `admit`) and `Admission`. Acceptance: `has_tool`, `tool_cost` and `execute` work on a Place built from inline test tools; unknown tool names raise `UnknownToolError`; `Admission` enforces `permit_after is None` exactly when the decision is REFUSE.
  - Edge cases: cost 0 is valid; `bool` cost is a TypeError; `has_tool` never raises; the error is a `LookupError` and not a `KeyError`.
  - _Requirements: 2.1, 2.8_

  - [x] 1.1 Write the Tool, Place and Admission unit tests first
    - Files: `backend/tests/unit/test_tools.py` (new), `backend/tests/unit/test_place.py` (new).
    - In `test_tools.py` write `test_negative_cost_raises_value_error` (cost -1 raises ValueError, cost 0 is valid) and `test_non_int_cost_raises_type_error` (a `bool` and a `float` cost raise TypeError).
    - In `test_place.py` build the Place inline from one or two test `Tool` values with a trivial `fn`, a ceiling Permit, a trusted map and `allowed_classes`.
    - In `test_place.py` write `test_has_tool_and_tool_cost` (true and false for `has_tool`, `tool_cost` returns the cost, `has_tool` of an unknown name returns False without raising).
    - In `test_place.py` write `test_execute_unknown_tool_raises` and `test_tool_cost_unknown_tool_raises`: both raise `UnknownToolError`; the message contains the tool name and the Place name; the error is an instance of `LookupError` and not of `KeyError`.
    - In `test_place.py` write `test_admission_invariant`: REFUSE with a Permit raises ValueError, ADMIT and ADMIT_IMPOSED without a Permit raise ValueError, an unknown decision string raises ValueError, and the three valid shapes construct.
    - Run `uv --directory backend run pytest -q tests/unit/test_tools.py tests/unit/test_place.py`
    - Expected: collection errors with `ModuleNotFoundError: No module named 'telepermit.tools'` (and `telepermit.place`). A different failure means a typo in the test.
    - `test_tools.py` and `test_place.py` fail with collection errors until sub-task 1.2, not 2.3.
    - _Requirements: 2.1, 2.8_

  - [x] 1.2 Implement Tool, UnknownToolError, Place and Admission and make the tests pass
    - Files: `backend/src/telepermit/tools.py` (new), `backend/src/telepermit/place.py` (new).
    - `tools.py`: docstring naming CONTRACTS section 4; frozen, slotted `Tool` dataclass with `name`, `cost`, `description`, `args`, `fn`; `__post_init__` rejects a non-int or `bool` cost with TypeError and a negative cost with ValueError.
    - `place.py`: docstring naming CONTRACTS section 4; constants `ADMIT`, `ADMIT_IMPOSED`, `REFUSE`, `OK`, `CLASS_NOT_ALLOWED`, `EXCEEDS_CEILING` defined once; `UnknownToolError(LookupError)` with a message naming the tool and the Place; frozen, slotted `Admission` with the invariant check; frozen, slotted `Place` with exactly the CONTRACTS fields and `has_tool`, `tool_cost`, `execute`. Do not add `admit` yet.
    - Run `uv --directory backend run pytest -q tests/unit/test_tools.py tests/unit/test_place.py`
    - Expected: all tests in both files pass.
    - Run `uv --directory backend run ruff check .`
    - Run `uv --directory backend run ruff format --check .`
    - Update docs/PROGRESS.md and print the DONE line.
    - _Requirements: 2.1, 2.8_

- [x] 2. T2.2 Tool catalog
  - Depends on T2.1. Builds `library_tools`, `vault_tools`, `VaultTools`, the constants, `BRIEFING_Q3_TEXT` and `ToolArgumentError` in `tools.py`. Acceptance: `read_document({"name": "briefing-q3"})` returns the exact document text; `read_records` returns `records page N` with incrementing N; `export_records` appends to the Outbox.
  - Edge cases: unknown document name gives `no such document`; `search_archive` for any query; Outbox length equals the number of `export_records` calls; two `vault_tools()` calls share no state.
  - _Requirements: 2.1, 2.7_

  - [x] 2.1 Write the catalog unit tests first
    - Files: `backend/tests/unit/test_tools.py` (append; keep the T2.1 tests) and `backend/tests/unit/test_place.py` (append; keep the T2.1 tests).
    - Write `test_catalog_costs`: costs are 1, 5, 3 and 20 for `read_document`, `search_archive`, `read_records`, `export_records`, taken from the factories.
    - Write `test_briefing_text_exact`: `BRIEFING_Q3_TEXT` equals the CONTRACTS section 8 string character for character (copy the string from the design document), and `read_document` with `{"name": "briefing-q3"}` returns it.
    - Write `test_read_document_unknown_name`: any other name returns `no such document`.
    - Write `test_search_archive_output`: `{"query": "q"}` returns `3 results for 'q'`; also an empty query and a query containing a quote.
    - Write `test_read_records_pages`: successive calls return `records page 1`, `records page 2`, `records page 3`.
    - Write `test_export_records_outbox`: first call returns `exported all records to <d> (export #1)`, second returns `(export #2)`, and `VaultTools.outbox()` returns the destinations as an immutable tuple in order.
    - Write `test_missing_argument_raises_tool_argument_error`: each of `read_document`, `search_archive`, `export_records` called with `{}` raises `ToolArgumentError` (a ValueError) whose message names the tool and the key; `read_records` accepts `{}`; extra keys are ignored.
    - Write `test_vault_tools_state_is_independent`: two `vault_tools()` calls have independent page counters and Outboxes.
    - Write `test_tool_args_metadata`: the `args` mappings are `{"name": "str"}`, `{"query": "str"}`, `{}`, `{"destination": "str"}`.
    - In `test_place.py` write `test_fresh_places_identical_results`: build two vault Places from two separate `vault_tools()` calls, and two library Places from two `library_tools()` calls; the same call sequence through `Place.execute` gives identical results on both, including `records page 1` and `records page 2` and `(export #1)`.
    - Run `uv --directory backend run pytest -q tests/unit/test_tools.py`
    - Run `uv --directory backend run pytest -q tests/unit/test_place.py`
    - Expected for both: a collection error `ImportError: cannot import name 'library_tools' from 'telepermit.tools'` (or another missing catalog name). Because the import is at the top of the file, the whole file fails at collection, including the T2.1 tests; they go green again after sub-task 2.3.
    - _Requirements: 2.1, 2.7_

  - [x] 2.2 Write property test P2.5 (fresh places are deterministic and the Outbox counts exports)
    - Files: `backend/tests/properties/test_tools_properties.py` (new).
    - Test function `test_p2_5_fresh_places_deterministic`. Generate a list of calls: tool names from the four catalog tools with generated string arguments (any text, including empty and unicode). Build two Places from two fresh factory sets (library and vault), run the same call sequence through `Place.execute` on both, and assert identical result sequences. Assert the Outbox length (via `VaultTools.outbox()`) equals the number of `export_records` calls, and that `read_records` results are `records page N` with N counting earlier `read_records` calls on that Place only. Tag the test with a comment `Feature: tools-places-admission, Property 5`.
    - Docstring: "Property P2.5: two Places built from fresh factory calls return identical results for the same call sequence, and the Outbox length equals the number of export_records calls. Validates: Requirements 2.1, 2.7".
    - Run `uv --directory backend run pytest -q tests/properties/test_tools_properties.py`
    - Expected: fails with `ImportError: cannot import name 'library_tools' from 'telepermit.tools'`.
    - **Property 5: P2.5 Fresh places are deterministic and the Outbox counts exports**
    - **Validates: Requirements 2.1, 2.7**

  - [x] 2.3 Implement the catalog and make the tests pass
    - Files: `backend/src/telepermit/tools.py`.
    - Define once: the four tool name constants, the four cost constants, `BRIEFING_NAME`, `NO_SUCH_DOCUMENT`, `BRIEFING_Q3_TEXT` (source literal may be split across lines; the runtime value must equal the CONTRACTS section 8 string).
    - Add `ToolArgumentError(ValueError)` and the helper `_require_arg(tool_name, args, key)`: a missing key raises with a message naming the tool and the key, no silent default.
    - Add `library_tools()` returning a dict of `read_document` and `search_archive`. Add the frozen `VaultTools` dataclass (`tools`, `outbox` callable returning a tuple snapshot) and `vault_tools()` that creates the page counter and Outbox inside the call and captures them in the closures. No module-level mutable state.
    - Run `uv --directory backend run pytest -q tests/unit/test_tools.py`
    - Expected: all tests in the file pass.
    - Run `uv --directory backend run pytest -q tests/unit/test_place.py`
    - Expected: all tests in the file pass, including `test_fresh_places_identical_results`.
    - Run `uv --directory backend run pytest -q tests/properties/test_tools_properties.py`
    - Expected: P2.5 passes.
    - Run `uv --directory backend run ruff check .`
    - Run `uv --directory backend run ruff format --check .`
    - Update docs/PROGRESS.md and print the DONE line.
    - _Requirements: 2.1, 2.7_

- [ ] 3. T2.3 Admission logic
  - Depends on T2.1 and Spec 1. Builds `Place.admit(identity, permit, steps, spent, elapsed)` with the exact four-step order of CONTRACTS section 4: identity verification, class check, counters versus the narrowed permit (strict `>`), then ADMIT versus ADMIT_IMPOSED. Acceptance: untrusted authority gives REFUSE with that code; wrong class gives REFUSE CLASS_NOT_ALLOWED; counters exceeding the narrowed permit give REFUSE EXCEEDS_CEILING; narrowing changes nothing gives ADMIT; otherwise ADMIT_IMPOSED.
  - Edge cases: a counter exactly equal to its narrowed limit is admitted (`spent == allowance`, `steps == max_steps`, `elapsed == lifetime_s`); one over is refused; zero-limit ceilings; a REFUSE always has `permit_after` None; `admit` never raises for any signature bytes.
  - Note: 3.1 to 3.5 are red until 3.6 implements `admit`; `AttributeError` is expected until then.
  - _Requirements: 2.2, 2.3, 2.4, 2.5, 2.6_

  - [ ] 3.1 Write the admit unit tests first
    - Files: `backend/tests/unit/test_place.py` (append; keep earlier tests).
    - Inline helpers: a fixed-seed `Authority.from_seed` (DEMO ONLY), a trusted map `{authority name: public key}`, a function that builds a Place with a chosen ceiling and `allowed_classes`, a function that builds an Identity with `Authority.issue`.
    - Write `test_untrusted_authority_refused` (authority not in `trusted`: REFUSE, `permit_after` None, reason equals `UNTRUSTED_AUTHORITY`) and `test_bad_signature_refused` (trusted authority name, tampered identity: REFUSE, reason equals `BAD_SIGNATURE`).
    - Write `test_class_not_allowed_refused`: valid identity, class not in `allowed_classes`: REFUSE with `CLASS_NOT_ALLOWED`.
    - Write `test_exceeds_ceiling_each_counter_boundary`: for each of `spent`, `steps`, `elapsed` separately, a value equal to the narrowed limit is admitted and one over is refused with `EXCEEDS_CEILING`. Use a ceiling that is narrower than the permit in one case so the narrowed limit (not the request) is what counts.
    - Write `test_zero_limit_ceiling`: ceiling with zero limits admits counters of 0 and refuses counters above 0.
    - Write `test_admit_unchanged`: permit already within the ceiling gives ADMIT, reason `OK`, and `permit_after` equal to the permit passed in.
    - Write `test_admit_imposed`: a wider permit gives ADMIT_IMPOSED, reason `OK`, `permit_after` equal to `permit.narrowed_by(ceiling)`, and at least `allowance` and `allowed_actions` differ from the request.
    - Write the order checks: `test_bad_signature_beats_class` (bad signature plus disallowed class returns the signature code), `test_class_beats_exceeded_counters` (disallowed class plus exceeded counters returns `CLASS_NOT_ALLOWED`), `test_exceeded_counters_refuse_before_admit` (exceeded counters with a permit that would otherwise be ADMIT or ADMIT_IMPOSED still refuse).
    - Run `uv --directory backend run pytest -q tests/unit/test_place.py`
    - Expected: the new tests fail with `AttributeError: 'Place' object has no attribute 'admit'`. The earlier tests in the file still pass.
    - _Requirements: 2.2, 2.3, 2.4, 2.5, 2.6_

  - [ ] 3.2 Write property test P2.1 (permit_after is never wider)
    - Files: `backend/tests/properties/test_place_properties.py` (new). Define the shared strategies here: Permit (include zero values and empty action sets), ceiling Permit, identity from a fixed-seed `Authority`, counters not above the narrowed limits.
    - Test function `test_p2_1_permit_after_never_wider`. For any admitted arrival, `permit_after` is not None and each of `lifetime_s`, `max_steps`, `allowance` is at most the minimum of the request and the ceiling, and `allowed_actions` is a subset of both. Tag with a comment `Feature: tools-places-admission, Property 1`.
    - Docstring: "Property P2.1: permit_after is never wider than the requested permit or the ceiling, on any field. Validates: Requirements 2.5, 2.6".
    - Run `uv --directory backend run pytest -q tests/properties/test_place_properties.py`
    - Expected: fails with `AttributeError: 'Place' object has no attribute 'admit'`.
    - **Property 1: P2.1 permit_after is never wider than the request or the ceiling**
    - **Validates: Requirements 2.5, 2.6**

  - [ ] 3.3 Write property test P2.2 (bad identities and disallowed classes are refused)
    - Files: `backend/tests/properties/test_place_properties.py`.
    - Test function `test_p2_2_bad_identity_or_class_refused`. Case one: an identity from an authority unknown to the Place, or with a corrupted signature or corrupted signed field, gives REFUSE, `permit_after` None, and `reason` equal to the code `verify_identity` returns for the same inputs. Case two: a validly signed identity from a trusted authority whose class is not in `allowed_classes` gives REFUSE with `CLASS_NOT_ALLOWED`. Make sure the corruption really changes the value.
    - Docstring: "Property P2.2: an identity with an unknown authority, a corrupted signature, or a disallowed class is always refused. Validates: Requirements 2.2, 2.3".
    - Run `uv --directory backend run pytest -q tests/properties/test_place_properties.py`
    - Expected: the new test fails with `AttributeError: 'Place' object has no attribute 'admit'`.
    - **Property 2: P2.2 Bad identities and disallowed classes are always refused**
    - **Validates: Requirements 2.2, 2.3**

  - [ ] 3.4 Write property test P2.3 (ADMIT if and only if narrowing changes nothing)
    - Files: `backend/tests/properties/test_place_properties.py`.
    - Test function `test_p2_3_admit_iff_unchanged`. For an admitted arrival: the decision is ADMIT exactly when `permit.narrowed_by(ceiling) == permit`, with `permit_after` equal to `permit`; otherwise ADMIT_IMPOSED with `permit_after` equal to the narrowed permit. `reason` is `OK` in both cases. Generators must produce both outcomes, including a ceiling equal to the permit.
    - Docstring: "Property P2.3: ADMIT happens if and only if narrowing changes nothing; otherwise ADMIT_IMPOSED. Validates: Requirements 2.5, 2.6".
    - Run `uv --directory backend run pytest -q tests/properties/test_place_properties.py`
    - Expected: the new test fails with `AttributeError: 'Place' object has no attribute 'admit'`.
    - **Property 3: P2.3 ADMIT if and only if narrowing changes nothing**
    - **Validates: Requirements 2.5, 2.6**

  - [ ] 3.5 Write property test P2.4 (exceeded counters always refuse)
    - Files: `backend/tests/properties/test_place_properties.py`.
    - Test function `test_p2_4_exceeded_counters_refused`. For a valid identity with an allowed class and counters where at least one of `spent`, `steps`, `elapsed` is strictly greater than the matching narrowed limit (`allowance`, `max_steps`, `lifetime_s`), the result is REFUSE, `permit_after` None, `reason` `EXCEEDS_CEILING`, never an admission. Also assert that counters equal to the limits are not refused.
    - Docstring: "Property P2.4: if counters exceed the narrowed limits the decision is REFUSE with EXCEEDS_CEILING, never an admission. Validates: Requirements 2.4".
    - Run `uv --directory backend run pytest -q tests/properties/test_place_properties.py`
    - Expected: the new test fails with `AttributeError: 'Place' object has no attribute 'admit'`.
    - **Property 4: P2.4 Exceeded counters always refuse with EXCEEDS_CEILING**
    - **Validates: Requirements 2.4**

  - [ ] 3.6 Implement admit and make the tests pass
    - Files: `backend/src/telepermit/place.py`.
    - Add `Place.admit(identity, permit, steps, spent, elapsed)`: step 1 `verify_identity(identity, self.trusted)`, any returned code gives REFUSE with that code; step 2 class not in `allowed_classes` gives REFUSE `CLASS_NOT_ALLOWED`; step 3 compute `n = permit.narrowed_by(self.ceiling)`, and `spent > n.allowance` or `steps > n.max_steps` or `elapsed > n.lifetime_s` gives REFUSE `EXCEEDS_CEILING`; step 4 `n == permit` gives ADMIT with `permit_after` the same permit object, otherwise ADMIT_IMPOSED with `n`. Reason is `OK` on both admissions. Import `UNTRUSTED_AUTHORITY` and `BAD_SIGNATURE` only if needed; do not retype the code strings.
    - Run `uv --directory backend run pytest -q tests/unit/test_place.py`
    - Expected: all tests in the file pass.
    - Run `uv --directory backend run pytest -q tests/properties/test_place_properties.py`
    - Expected: P2.1 to P2.4 pass.
    - Run `uv --directory backend run ruff check .`
    - Run `uv --directory backend run ruff format --check .`
    - Update docs/PROGRESS.md and print the DONE line.
    - _Requirements: 2.2, 2.3, 2.4, 2.5, 2.6_

- [ ] 4. Final checkpoint - Ensure all tests pass
  - Before task 1.1, record the test count with `uv --directory backend run pytest -q --collect-only -q`. Run `uv --directory backend run pytest -q` and report the final total as a difference from the recorded count, all passing, including the five properties P2.1 to P2.5.
  - Run `uv --directory backend run ruff check .`
  - Run `uv --directory backend run ruff format --check .`
  - Confirm by inspection: only the eight requirements and the approved design are implemented; no dependency outside tech.md was added; nothing imports `engine`; no source module calls `Place.execute`.
  - Update docs/PROGRESS.md (spec folder name, branch, completed items T2.1 to T2.3).
  - Print the DONE line with the real counts. Ensure all tests pass, ask the user if questions arise.
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8_

## Notes

- No task is optional. Property tests P2.1 to P2.5 are required, each in its own sub-task.
- Test files are shared between tasks, so the dependency graph places tasks that write to the same file in different waves.
- A task is done only when its tests were run, the output was pasted, ruff check and ruff format check are clean, and PROGRESS.md is updated.

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["1.2"] },
    { "id": 2, "tasks": ["2.1", "2.2"] },
    { "id": 3, "tasks": ["2.3"] },
    { "id": 4, "tasks": ["3.2"] },
    { "id": 5, "tasks": ["3.1", "3.3"] },
    { "id": 6, "tasks": ["3.4"] },
    { "id": 7, "tasks": ["3.5"] },
    { "id": 8, "tasks": ["3.6"] }
  ]
}
```
