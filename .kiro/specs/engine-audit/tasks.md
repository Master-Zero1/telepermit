# Implementation Plan: engine-audit

## Overview

Implements the Clock, the audit Event models with `reduce_events` and the JSONL writer, the driver types, the Engine (spawn, `step` with and without enforcement, `run`) and the architecture test (CONTRACTS sections 5, 6 and 7, golden traces from section 8), in the order of roadmap items T3.1 to T3.8. Language: Python. Branch: `spec/03-engine-audit`. The requirement IDs are the criteria 3.1 to 3.15 of requirements.md (criterion 3.15 is an owner-approved addition to the 14 seed items). Design decisions (a) tool errors and (d) conditional clock advance are approved, but their CONTRACTS amendment is applied later by the owner. The work is therefore split in two groups.

- Group A is everything except decisions (a) and (d). It follows the CURRENT CONTRACTS text: five statuses only (no ERROR), no try/except around `place.execute` (a tool exception just propagates, and no test raises one), the Engine `clock` parameter typed `TickClock`, and `run` calling `clock.advance(TICK_S)` unconditionally. Property-test arguments in Group A are valid for the tool, drawn from a table of required keys: `read_document` needs `name`, `search_archive` needs `query`, `export_records` needs `destination`, `read_records` needs none, values are arbitrary text. A missing key would raise `ToolArgumentError`, which Group A does not handle.
- Group B is the (a) and (d) work. It starts only after the owner applies the CONTRACTS amendment (task 10) and confirms in chat.

Order of build:
- T3.1 builds `clock.py` and `audit.py` (constants, five statuses, `Event`, TypedDicts, `permit_json`, `narrowed_fields`).
- T3.2 adds `reduce_events`, `to_jsonl` and `write_jsonl` to `audit.py`.
- T3.3 builds `drivers/__init__.py` and `drivers/base.py` (only `Proposal`, `Observation`, `AgentDriver`).
- T3.4 builds `engine.py` up to construction, spawn border check, `state`, `events`, and row 1 of `step`, with a temporary `NotImplementedError` guard for an ALIVE agent.
- T3.5 builds the enforce=True step algorithm (eleven rows of design.md) and removes the guard. Until task 6 the `enforce` flag is stored but not consulted, so an Engine built with enforcement off still runs the enforced rows (it fails safe: it enforces more, never less).
- T3.6 builds the enforce=False variant: `step` starts consulting the `enforce` flag.
- T3.7 builds `run`, `_observe`, `_last_result` and the task consistency check of criterion 3.15.
- T3.8 builds `tests/test_architecture.py`.

Hand-off mode: the human runs every command and pastes the output. Each test sub-task states the exact command and the expected result. Every task with both code and tests follows the same order: write the tests first, run them, confirm they fail for the stated reason, then implement and re-run to green. Lint steps are separate single commands, never chained, and ruff is run only after implementation (while modules are missing, ruff reports spurious I001).

All nine property tests (P3.1 to P3.9) are required, none optional. Each property docstring has the form `Property P3.n: <statement>. Validates: Requirements 3.x`. The Hypothesis profile in the existing conftest (deadline none, 200 examples) applies.

Conventions that apply to every file written in this spec:
- Start each Python module with `from __future__ import annotations`. Source modules have a docstring naming the CONTRACTS section they implement (it comes before the future import).
- Ruff isort: once the modules exist, a blank line between third-party imports (pytest, hypothesis, cryptography) and `from telepermit...` imports, otherwise ruff reports I001.
- Every file ends with exactly one trailing newline (otherwise `ruff format --check` fails). Write LF line endings.
- Tests build their world inline (CONTRACTS section 8 numbers, `Authority.from_seed` with a fixed seed, which is DEMO ONLY and fine in tests). No shared helper module.
- The existing test files from Specs 1 and 2 are not touched. `tests/unit/` and `tests/properties/` already exist. Create no folders and no `__init__.py` in tests.
- Commit each green top-level task BEFORE writing the next top-level task's tests, so red tests never land in an earlier task's commit. Run `git status --short` before every commit and stage files by name.
- Before sub-task 1.1, record the test count with `uv --directory backend run pytest -q --collect-only -q` (the baseline on this branch is 89). Report the final totals as a difference from the recorded count.
- After each top-level task print: `DONE T<id>: <one line>. Tests: <passed>/<total>. Ruff: clean. Files: <list>.`
- No source module calls `Place.execute` except `engine.py` (security invariant 1). Nothing outside tech.md is added. No scenario, no driver implementation and no CLI is built in this spec. No Spec 1 or Spec 2 module is changed.
- Any change that would touch a security invariant, CONTRACTS.md or the replay format is a stop condition: stop and ask.

## Tasks

### Group A

- [ ] 1. T3.1 Clock and Event models
  - Builds `clock.py` (`TICK_S`, `Clock` protocol, `TickClock`) and the first half of `audit.py` (event type, status, denial, kill constants, `UNENFORCED`, `PERMIT_FIELD_ORDER`, `Event`, the data TypedDicts, `permit_json`, `narrowed_fields`). Statuses are the FIVE of CONTRACTS: ALIVE, KILLED, FINISHED, REFUSED, HARNESS_CAP, each with the `STATUS_` prefix. No `STATUS_ERROR` in Group A.
  - Acceptance: `TickClock` advances and rejects bad values; `Event` accepts the seven types and rejects any other; `permit_json(p)` equals `p.to_json()`.
  - Edge cases: `advance(0)` is allowed; negative, NaN and infinite `dt` raise `ValueError`; non-finite `start` raises; 30 ticks of `TICK_S` give exactly 30.0.
  - _Requirements: 3.11, 3.14_

  - [ ] 1.1 Write the Clock and Event unit tests first
    - Files: `backend/tests/unit/test_clock.py` (new), `backend/tests/unit/test_audit.py` (new).
    - Before writing anything, run `uv --directory backend run pytest -q --collect-only -q` and record the count (baseline 89).
    - In `test_clock.py`: `test_start_value_and_now`, `test_advance_by_one`, `test_advance_zero_allowed`, `test_advance_negative_raises` (ValueError), `test_advance_nan_and_infinity_raise` (ValueError for NaN, inf, -inf), `test_non_finite_start_raises` (ValueError), `test_thirty_ticks_equal_thirty` (30 calls of `advance(TICK_S)` give exactly 30.0), `test_tick_s_is_one`.
    - In `test_audit.py`: `test_seven_event_types` (all seven types construct), `test_unknown_event_type_raises` (ValueError), `test_event_to_dict_fields` (keys exactly `seq, t, type, place, step, spent, data`, and `data` is a copy), `test_permit_json_equals_permit_to_json` (including an empty and a multi-member `allowed_actions`), `test_narrowed_fields_order` (names returned in the fixed order lifetime_s, max_steps, allowance, allowed_actions; empty list when nothing differs), `test_statuses_are_the_five` (the `STATUSES` set holds exactly ALIVE, KILLED, FINISHED, REFUSED, HARNESS_CAP).
    - Run `uv --directory backend run pytest -q tests/unit/test_clock.py`
    - Run `uv --directory backend run pytest -q tests/unit/test_audit.py`
    - Expected red: collection errors `ModuleNotFoundError: No module named 'telepermit.clock'` for the first file and `ModuleNotFoundError: No module named 'telepermit.audit'` for the second. A different failure means a typo in the test. Do not run ruff in this state.
    - Acceptance check: both files fail at collection with exactly those two errors.
    - _Requirements: 3.11, 3.14_

  - [ ] 1.2 Implement clock.py and the first half of audit.py and make the tests pass
    - Files: `backend/src/telepermit/clock.py` (new), `backend/src/telepermit/audit.py` (new).
    - `clock.py`: docstring naming CONTRACTS section 5; `TICK_S: Final = 1.0`; `Clock` protocol with `now()`; `TickClock(start=0.0)` with `now()` and `advance(dt)`; validation as in the design (`ValueError` for negative, NaN or infinite `dt` and for a non-finite `start`; `dt == 0` allowed).
    - `audit.py`: docstring naming CONTRACTS section 6; the seven event type constants and `EVENT_TYPES`; the five `STATUS_*` constants and `STATUSES`; `NOT_IN_PERMIT`, `NOT_IN_PLACE`, `LIFETIME_EXCEEDED`, `STEPS_EXCEEDED`, `ALLOWANCE_EXCEEDED`, `UNENFORCED`, `PERMIT_FIELD_ORDER`; decisions and place reasons imported from `place.py`, never retyped; frozen slotted `Event` with the `__post_init__` check and `to_dict`; the TypedDicts of the design; `permit_json`; `narrowed_fields`. No `engine` import.
    - Run `uv --directory backend run pytest -q tests/unit/test_clock.py`
    - Run `uv --directory backend run pytest -q tests/unit/test_audit.py`
    - Expected: all tests in both files pass.
    - Run `uv --directory backend run ruff check .`
    - Run `uv --directory backend run ruff format --check .`
    - Update docs/PROGRESS.md. Run `git status --short`, stage the four files of this task by name, commit `feat(audit): clock and event models (task 1.2)`, print the DONE line.
    - Acceptance check: both test files green, ruff clean, commit made.
    - _Requirements: 3.11, 3.14_

- [ ] 2. T3.2 reduce_events and JSONL writer
  - Depends on T3.1. Adds `reduce_events`, `ReducedState`, `to_jsonl` and `write_jsonl` to `audit.py`. Acceptance: the hand-built Run B event list reduces to place vault, step 17, spent 38, permit allowance 40, status KILLED.
  - Edge cases: empty list raises `ValueError`; a list without `RUN_STARTED` raises `ValueError`; no `RUN_ENDED` gives ALIVE; permit comes from `RUN_STARTED` when there is no `BORDER_CHECK`; the result never aliases event data; JSONL lines end in LF only.
  - _Requirements: 3.14, 3.11_

  - [ ] 2.1 Write the reduce_events and JSONL unit tests first
    - Files: `backend/tests/unit/test_audit.py` (append; keep the T3.1 tests).
    - `test_reduce_events_golden_run_b`: a hand-built 20-event list in the shape of CONTRACTS section 8 Run B (events built with the `Event` constructor and `permit_json`) reduces to `{place: "vault", step: 17, spent: 38, permit: allowance 40 with allowed_actions read_records and go:library, status: "KILLED"}`.
    - `test_reduce_empty_raises` and `test_reduce_without_run_started_raises` (ValueError).
    - `test_reduce_no_run_ended_is_alive`.
    - `test_reduce_permit_sources`: permit from `RUN_STARTED` when no `BORDER_CHECK`; permit from the LAST `BORDER_CHECK` when there are several; a refused `BORDER_CHECK` carries the current permit as `permit_after` and reduces to it.
    - `test_reduce_does_not_alias_event_data`: mutating the returned `allowed_actions` list leaves the events unchanged.
    - `test_to_jsonl_format`: one line per event, each line ends with `"\n"`, keys sorted, each line parses back with `json.loads` to `event.to_dict()`, output is pure ASCII (an action string with a non-ASCII character is escaped).
    - `test_to_jsonl_empty`: `""` for an empty list.
    - `test_write_jsonl_lf_only`: write to `tmp_path`, read back in binary mode, assert no `b"\r"` and that the content ends with `b"\n"`.
    - Run `uv --directory backend run pytest -q tests/unit/test_audit.py`
    - Expected red: `ImportError: cannot import name 'reduce_events' from 'telepermit.audit'`. The import is at the top of the file, so the whole file errors at collection, including the T3.1 tests; they go green again after sub-task 2.2. `test_clock.py` is unaffected. Do not run ruff in this state.
    - Acceptance check: the single collection error above and nothing else.
    - _Requirements: 3.14, 3.11_

  - [ ] 2.2 Implement reduce_events, to_jsonl and write_jsonl and make the tests pass
    - Files: `backend/src/telepermit/audit.py`.
    - `reduce_events`: snapshot (`place`, `step`, `spent`) from the last event; permit from the last `RUN_STARTED` (`data["permit"]`) or `BORDER_CHECK` (`data["permit_after"]`); status from the last `RUN_ENDED` (`data["status"]`), otherwise ALIVE; `ValueError` for an empty list or no `RUN_STARTED`; return a fresh dict with a fresh `allowed_actions` list.
    - `to_jsonl`: each event as `json.dumps(event.to_dict(), sort_keys=True)` followed by `"\n"`, default `ensure_ascii=True`. `write_jsonl(path, events)`: `open(path, "w", encoding="utf-8", newline="\n")`, no parent directory creation.
    - Run `uv --directory backend run pytest -q tests/unit/test_audit.py`
    - Expected: all tests in the file pass.
    - Run `uv --directory backend run ruff check .`
    - Run `uv --directory backend run ruff format --check .`
    - Update docs/PROGRESS.md. Run `git status --short`, stage the changed files by name, commit `feat(audit): reduce_events and jsonl writer (task 2.2)`, print the DONE line.
    - Acceptance check: `test_audit.py` green including golden Run B reduction, ruff clean, commit made.
    - _Requirements: 3.14, 3.11_

- [ ] 3. T3.3 Driver protocol
  - Builds `drivers/__init__.py` (docstring only) and `drivers/base.py` holding ONLY `Proposal`, `Observation`, `AgentDriver`. Acceptance: the `Observation` field set is exactly `{task, turn, place, tools, last_result}`, so a permit, spend, cost, step count or key cannot be added by accident.
  - Edge cases: both dataclasses are frozen; `base.py` imports no `telepermit` module; a class with a `propose` method satisfies the protocol structurally.
  - _Requirements: 3.13_

  - [ ] 3.1 Write the driver types unit tests first
    - Files: `backend/tests/unit/test_drivers_base.py` (new).
    - `test_proposal_and_observation_are_frozen` (assigning a field raises `FrozenInstanceError`).
    - `test_observation_field_set_exactly_five`: `{f.name for f in dataclasses.fields(Observation)}` equals `{"task", "turn", "place", "tools", "last_result"}`.
    - `test_base_imports_no_telepermit_modules`: parse `drivers/base.py` with `ast` (path computed from the test file location) and assert no import has `telepermit` as its first segment and no relative import exists.
    - `test_structural_agent_driver`: a small class with `propose(self, observation) -> Proposal` is accepted where an `AgentDriver` is expected and returns the `Proposal` it was built to return.
    - Run `uv --directory backend run pytest -q tests/unit/test_drivers_base.py`
    - Expected red: `ModuleNotFoundError: No module named 'telepermit.drivers'`. Do not run ruff in this state.
    - Acceptance check: collection error with exactly that message.
    - _Requirements: 3.13_

  - [ ] 3.2 Implement drivers/__init__.py and drivers/base.py and make the tests pass
    - Files: `backend/src/telepermit/drivers/__init__.py` (new, docstring only), `backend/src/telepermit/drivers/base.py` (new).
    - `base.py`: docstring naming CONTRACTS section 7; imports only `dataclasses` and `typing`; frozen slotted `Proposal(action, args)`; frozen slotted `Observation(task, turn, place, tools, last_result)` with `tools: list[dict[str, object]]`; `AgentDriver` protocol with `propose(observation) -> Proposal`. Nothing else in the module.
    - Run `uv --directory backend run pytest -q tests/unit/test_drivers_base.py`
    - Expected: all tests pass.
    - Run `uv --directory backend run ruff check .`
    - Run `uv --directory backend run ruff format --check .`
    - Update docs/PROGRESS.md. Run `git status --short`, stage the three files by name, commit `feat(drivers): proposal, observation, driver protocol (task 3.2)`, print the DONE line.
    - Acceptance check: `test_drivers_base.py` green, ruff clean, commit made.
    - _Requirements: 3.13_

- [ ] 4. T3.4 Engine construction and spawn border check
  - Depends on T3.1 and T3.3 and Spec 2. Builds `engine.py` with `GO_COST`, `HARNESS_CAP`, `AgentNotAlive`, `EngineState`, `RunResult`, `Engine.__init__` (keyword-only `scenario`, `driver`, `task`; `clock` typed `TickClock` in Group A), `state`, `events`, the spawn border check and row 1 of `step`. For an ALIVE agent `step` temporarily does `raise NotImplementedError("rows 2 to 11: task 5")`. The guard is removed in sub-task 5.9.
  - Acceptance: constructing an Engine with a forged identity and enforcement on gives status REFUSED and exactly three events.
  - Edge cases: `enforce=False` emits only `RUN_STARTED`; an unknown start place raises `ValueError` before any event; an imposed permit at spawn replaces the current permit; `state` is a fresh frozen snapshot; `events` is a copy.
  - _Requirements: 3.9, 3.1, 3.11_

  - [ ] 4.1 Write the construction and spawn unit tests first
    - Files: `backend/tests/unit/test_engine.py` (new). The world is built inline: `library_tools()`, `vault_tools()` (keep the `VaultTools` handle for its outbox), ceilings library `Permit(60.0, 30, 60, six actions)` and vault `Permit(60.0, 30, 40, {read_records, go:library})`, allowed class `briefing-bot`, `Authority.from_seed("home-authority", b"telepermit-demo-authority")` (DEMO ONLY), identity `briefing-bot-001`, `TickClock(0.0)`, start place library. The six actions are `read_document, search_archive, read_records, export_records, go:vault, go:library`.
    - `test_construct_enforced_admit_emits_two_events` (RUN_STARTED then BORDER_CHECK library ADMIT; step 0, spent 0, cost 0, `via_action` None).
    - `test_construct_imposed_permit_at_spawn` (start in the vault with the home permit gives ADMIT_IMPOSED and `state.permit` equal to the narrowed permit).
    - `test_construct_enforce_off_emits_run_started_only`.
    - `test_construct_unknown_start_place_raises_before_any_event` (`ValueError`; use a places mapping and assert no Engine exists and the clock was not read for an event; the check is that the constructor raises before anything else).
    - `test_run_started_data_fields` (scenario, driver, enforce, task from the keyword arguments; identity with agent_id, agent_class, authority, issued_at, signature_hex; permit equals `permit_json` of the constructor permit).
    - `test_run_started_identity_has_only_public_fields` (no key material; the identity dict holds exactly the five public keys).
    - `test_state_is_fresh_frozen_snapshot` (two accesses give equal but distinct objects; assigning a field raises `FrozenInstanceError`).
    - `test_events_returns_a_copy` (mutating the returned list leaves the Engine log unchanged).
    - `test_forged_identity_refused_run_c`: identity signature replaced by 64 zero bytes, enforce on: exactly `RUN_STARTED`, `BORDER_CHECK` (REFUSE, BAD_SIGNATURE, `permit_after` equal to the RUN_STARTED permit, `narrowed_fields` `[]`), `RUN_ENDED` REFUSED; status REFUSED.
    - `test_step_after_refused_raises` (`AgentNotAlive`, and the log is unchanged).
    - Run `uv --directory backend run pytest -q tests/unit/test_engine.py`
    - Expected red: `ModuleNotFoundError: No module named 'telepermit.engine'`. Do not run ruff in this state.
    - Acceptance check: collection error with exactly that message.
    - _Requirements: 3.9, 3.1, 3.11_

  - [ ] 4.2 Write property test P3.9 and the shared strategies (forged identity at spawn)
    - Files: `backend/tests/properties/test_engine_properties.py` (new). This sub-task also defines, inline in this file, the shared world builder (fresh places on every example, CONTRACTS section 8 numbers as in 4.1) and the strategies that every later property in this file reuses:
      - action pool: `read_document`, `search_archive`, `read_records`, `export_records`, `go:vault`, `go:library`, `finish`, `bogus`, plus adversarial strings `"unknown"`, `""`, `" read_records "`, `"read_recоrds"` (Cyrillic о), `"go:välts"`, `"go:"`, `"go:nowhere"`;
      - args drawn from a table of required keys (Group A): `read_document` gets `name`, `search_archive` gets `query`, `export_records` gets `destination`, `read_records` gets none, values arbitrary text; any other action gets any dict because it is never executed;
      - permit: `lifetime_s` from `{0.0, 0.5, 1.0, 5.0, 60.0}` or a small-range float, `max_steps` 0 to 40, `allowance` 0 to 80 weighted to small values and 0, `allowed_actions` a subset of the pool plus `go:nowhere`, the main strategy always including `go:vault`;
      - step sequence: up to 40 items, each a proposal plus an optional clock advance before it (dt from `{0.0, 0.5, 1.0, 30.0, 100.0}`).
    - Test function `test_p3_9_forged_identity_three_event_refusal`. Forged identity: random bytes of length 0 to 128, or the valid signature with one bit flipped, never equal to the valid signature. With enforcement on and a trusted authority name, assert the log is exactly `RUN_STARTED`, `BORDER_CHECK` (REFUSE, BAD_SIGNATURE, `permit_after` equal to the RUN_STARTED permit, `narrowed_fields == []`, `cost == 0`, `via_action` None), `RUN_ENDED(REFUSED)`; status REFUSED; any `step` raises `AgentNotAlive`. Tag with a comment `Feature: engine-audit, Property 9`.
    - Docstring: "Property P3.9: a forged identity at spawn gives exactly RUN_STARTED, BORDER_CHECK(REFUSE, BAD_SIGNATURE), RUN_ENDED(REFUSED), and the agent can never act. Validates: Requirements 3.9".
    - Run `uv --directory backend run pytest -q tests/properties/test_engine_properties.py`
    - Expected red: `ModuleNotFoundError: No module named 'telepermit.engine'`. Do not run ruff in this state.
    - **Property 9: P3.9 A forged identity at spawn gives exactly the three-event refusal**
    - **Validates: Requirements 3.9**

  - [ ] 4.3 Implement engine construction, spawn, state, events and row 1 and make the tests pass
    - Files: `backend/src/telepermit/engine.py` (new).
    - Docstring naming CONTRACTS section 5. Define once: `GO_COST: Final = 1`, `HARNESS_CAP: Final = 30`. Add `AgentNotAlive(RuntimeError)` (message holds the status only), frozen slotted `EngineState` and `RunResult`.
    - `Engine.__init__(places, identity, permit, start_place, clock, enforce=True, *, scenario="", driver="scripted", task="")` with `clock` typed `TickClock`. `ValueError` for an unknown `start_place` before any state is set. `_born` assigned once. Emit `RUN_STARTED` in both modes. With enforcement on call `places[start_place].admit(identity, permit, 0, 0, 0.0)` and emit `BORDER_CHECK` (step 0, `via_action` None, cost 0); ADMIT or ADMIT_IMPOSED replaces the current permit; REFUSE keeps it, sets `permit_after` in the event to the current permit, `narrowed_fields` `[]`, status REFUSED, then `RUN_ENDED(REFUSED)`.
    - One private `_emit(type, data)` is the only writer of the log and reads the post-transition state. `state` returns a new `EngineState` on every access. `events` returns a copy.
    - `step(proposal)`: row 1 only (raise `AgentNotAlive` when the status is not ALIVE, emit nothing), then for an ALIVE agent `raise NotImplementedError("rows 2 to 11: task 5")`. This guard is temporary and is removed in sub-task 5.9.
    - The Engine imports `Identity` only as a type; it never sees `Authority`.
    - Run `uv --directory backend run pytest -q tests/unit/test_engine.py`
    - Expected: all tests pass.
    - Run `uv --directory backend run pytest -q tests/properties/test_engine_properties.py`
    - Expected: P3.9 passes.
    - Run `uv --directory backend run ruff check .`
    - Run `uv --directory backend run ruff format --check .`
    - Update docs/PROGRESS.md. Run `git status --short`, stage the three files by name, commit `feat(engine): construction and spawn border check (task 4.3)`, print the DONE line.
    - Acceptance check: 4.1 tests and P3.9 green, ruff clean, commit made.
    - _Requirements: 3.9, 3.1, 3.11_

- [ ] 5. T3.5 Engine step() with enforcement on
  - Depends on T3.4. Implements the eleven-row algorithm of design.md exactly, in the stated order; the first matching row decides the call. Acceptance: hand-driving the Engine through the golden Run B sequence gives the 20 events of CONTRACTS section 8.
  - Edge cases: lifetime exactly equal is allowed; `finish` costs 0 and consumes no step; a `finish` after the lifetime is a kill; denied actions consume a step and charge nothing; `go` to the current place is DENIED NOT_IN_PLACE; `go` cost is charged even when the destination refuses; the status is set to KILLED before the events are emitted; the killed allowance action does not run.
  - Each of the properties P3.1 to P3.7 is its own sub-task and is red with `NotImplementedError` until 5.9.
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8, 3.11_

  - [ ] 5.1 Write the enforced step unit tests first
    - Files: `backend/tests/unit/test_engine.py` (append; keep the T3.4 tests).
    - Lifetime: `test_lifetime_exactly_equal_is_allowed` (60.0 allowed), `test_lifetime_just_over_is_killed` (60.001 killed: `KILLED` reason LIFETIME_EXCEEDED, `limit` 60.0, `observed` 60.001, followed by `RUN_ENDED(KILLED)`), `test_lifetime_kill_does_not_increment_step_snapshot`, `test_finish_after_lifetime_is_a_kill`, `test_lifetime_zero_with_zero_elapsed_allowed`.
    - Finish: `test_finish_emits_finished_then_run_ended`, `test_finish_changes_neither_steps_nor_spent`.
    - Steps: `test_steps_nth_allowed`, `test_steps_n_plus_one_killed` (`observed` N+1, snapshot step N), `test_max_steps_zero_kills_first_action` and `finish` still allowed with `max_steps` 0.
    - Denials: `test_not_in_permit_consumes_step_charges_nothing`, `test_not_in_place_for_other_places_tool`, `test_go_current_place_denied`, `test_go_unknown_place_denied`, `test_go_empty_place_denied` (`go:`), `test_padded_action_is_not_matched`, `test_not_in_permit_wins_over_not_in_place`.
    - Allowance: `test_allowance_exact_is_allowed` (spend reaching exactly the allowance), `test_allowance_one_over_kills_without_executing` (the killed action did NOT execute: vault outbox empty or page counter unchanged; `spent` unchanged; step snapshot includes the attempt; `limit` is the allowance and `observed` is `spent + cost`).
    - Crossing: `test_go_charges_cost_and_emits_border_check_only` (cost 1, no `TOOL_CALL`), `test_go_admit_imposed_replaces_permit`, `test_go_refused_charges_cost_and_keeps_place_and_permit` (use an inline destination Place that refuses the class; `permit_after` is the agent's current permit), `test_return_crossing_uses_current_permit` (vault to library after the vault narrowed the permit gives a permit no wider than the current one).
    - Termination and shape: `test_step_returns_only_new_events`, `test_step_on_killed_raises`, `test_step_on_finished_raises` (both `AgentNotAlive`, log unchanged).
    - `test_golden_run_b_hand_driven`: through `step()` only: `read_document` with `{"name": "briefing-q3"}`, `go:vault`, `export_records` twice (any destination text), `read_records` thirteen times. Assert all 20 events by type, step, spent and place; `BORDER_CHECK` vault `ADMIT_IMPOSED` with `narrowed_fields == ["allowance", "allowed_actions"]`; `DENIED` NOT_IN_PERMIT at steps 3 and 4; twelve `TOOL_CALL read_records` at steps 5 to 16 and spent 5 to 38; `KILLED` ALLOWANCE_EXCEEDED at step 17, spent 38, limit 40, observed 41; then `RUN_ENDED(KILLED)`; vault outbox empty; `reduce_events(engine.events)` equals `{place: "vault", step: 17, spent: 38, permit: allowance 40, status: "KILLED"}`.
    - `explain` strings are never asserted exactly.
    - Run `uv --directory backend run pytest -q tests/unit/test_engine.py`
    - Expected red: `NotImplementedError: rows 2 to 11: task 5` for every new test that steps an ALIVE agent. The T3.4 tests and the tests that only raise `AgentNotAlive` on a pre-ended Engine are not affected. Do not run ruff in this state.
    - Acceptance check: every failure is that NotImplementedError; no import error, no other exception.
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8, 3.11, 3.14_

  - [ ] 5.2 Write property test P3.1 (counters stay within the current permit while ALIVE)
    - Files: `backend/tests/properties/test_engine_properties.py` (append; reuse the shared strategies of 4.2).
    - Test function `test_p3_1_counters_within_current_permit`. Enforcement on, any permit and step sequence. After construction and after every `step` call that leaves the status ALIVE, assert `state.spent <= state.permit.allowance` and `state.steps <= state.permit.max_steps`, where `state.permit` is the Engine's current permit (which may have been narrowed by a crossing). Tag with a comment `Feature: engine-audit, Property 1`.
    - Docstring: "Property P3.1: while ALIVE, spent <= allowance and steps <= max_steps of the current permit. Validates: Requirements 3.4, 3.5, 3.6, 3.7, 3.8".
    - Run `uv --directory backend run pytest -q tests/properties/test_engine_properties.py`
    - Expected red: `NotImplementedError: rows 2 to 11: task 5`. Do not run ruff in this state.
    - **Property 1: P3.1 Counters stay within the current permit while ALIVE**
    - **Validates: Requirements 3.4, 3.5, 3.6, 3.7, 3.8**

  - [ ] 5.3 Write property test P3.2 (after a kill the only further event is RUN_ENDED)
    - Files: `backend/tests/properties/test_engine_properties.py` (append).
    - Test function `test_p3_2_after_kill_only_run_ended`. Enforcement on. If a `step` call produces a `KILLED` event, that call emits exactly `KILLED` then `RUN_ENDED(KILLED)`; afterwards every remaining proposal from the pool (and the adversarial strings) raises `AgentNotAlive` inside `pytest.raises` and leaves `engine.events` unchanged. The same check after `FINISHED`.
    - Docstring: "Property P3.2: after KILLED the only further event is RUN_ENDED, and step raises AgentNotAlive. Validates: Requirements 3.1, 3.7".
    - Run `uv --directory backend run pytest -q tests/properties/test_engine_properties.py`
    - Expected red: `NotImplementedError: rows 2 to 11: task 5`. Do not run ruff in this state.
    - **Property 2: P3.2 After a kill the only further event is RUN_ENDED**
    - **Validates: Requirements 3.1, 3.7**

  - [ ] 5.4 Write property test P3.3 (exactly one event per transition, contiguous seq)
    - Files: `backend/tests/properties/test_engine_properties.py` (append).
    - Test function `test_p3_3_one_event_per_transition`. Enforcement on. `seq` over `engine.events` is `0, 1, 2, ...` with no gap; construction emits exactly 2 events when the spawn is admitted and exactly 3 when refused (use the forged-identity strategy of P3.9 for a share of the examples); every `step` call on an ALIVE agent emits exactly one event if the status stays ALIVE and exactly two (cause event `KILLED` or `FINISHED`, then `RUN_ENDED`) if the call ends the run; a call on a non-ALIVE agent emits zero events.
    - Docstring: "Property P3.3: seq is contiguous from 0 and every transition emits exactly one event. Validates: Requirements 3.11".
    - Run `uv --directory backend run pytest -q tests/properties/test_engine_properties.py`
    - Expected red: `NotImplementedError: rows 2 to 11: task 5`. Do not run ruff in this state.
    - **Property 3: P3.3 Exactly one event per transition and contiguous seq**
    - **Validates: Requirements 3.11**

  - [ ] 5.5 Write property test P3.4 (counters never decrease and permits never grow)
    - Files: `backend/tests/properties/test_engine_properties.py` (append).
    - Test function `test_p3_4_counters_monotone_permits_shrink`. Enforcement on. Across consecutive events: `step`, `spent` and `t` never decrease. Across consecutive permit-carrying events (RUN_STARTED `permit`, then each BORDER_CHECK `permit_after`) each permit is no wider than the one before on every field (`lifetime_s <=`, `max_steps <=`, `allowance <=`, `allowed_actions` a subset). The same comparison holds for `state.permit` between calls. Generate sequences with repeated crossings (`go:vault`, `go:library`).
    - Docstring: "Property P3.4: step, spent and t never decrease, and permit fields never grow across any event. Validates: Requirements 3.8".
    - Run `uv --directory backend run pytest -q tests/properties/test_engine_properties.py`
    - Expected red: `NotImplementedError: rows 2 to 11: task 5`. Do not run ruff in this state.
    - **Property 4: P3.4 Counters never decrease and permits never grow**
    - **Validates: Requirements 3.8**

  - [ ] 5.6 Write property test P3.5 (reduce_events equals the Engine's final state)
    - Files: `backend/tests/properties/test_engine_properties.py` (append).
    - Test function `test_p3_5_reduce_events_equals_state`. Enforcement on. After construction and after every `step` call (so every prefix of the log is covered), assert `reduce_events(engine.events)` equals `{place, step, spent, permit, status}` taken from `engine.state`, with the permit as `permit_json(state.permit)`. A refused spawn is covered by P3.9.
    - Docstring: "Property P3.5: reduce_events(events) equals the engine's final place, steps, spent, permit and status. Validates: Requirements 3.11, 3.14".
    - Run `uv --directory backend run pytest -q tests/properties/test_engine_properties.py`
    - Expected red: `NotImplementedError: rows 2 to 11: task 5`. Do not run ruff in this state.
    - **Property 5: P3.5 reduce_events equals the Engine's final state**
    - **Validates: Requirements 3.11, 3.14**

  - [ ] 5.7 Write property test P3.6 (TOOL_CALL names a tool of the recorded place)
    - Files: `backend/tests/properties/test_engine_properties.py` (append).
    - Test function `test_p3_6_tool_call_names_tool_of_recorded_place`. Enforcement on. For every `TOOL_CALL` event `e`, `places[e.place].has_tool(e.data["action"])` is true.
    - Docstring: "Property P3.6: TOOL_CALL events only name tools that exist in the place recorded on that event. Validates: Requirements 3.6".
    - Run `uv --directory backend run pytest -q tests/properties/test_engine_properties.py`
    - Expected red: `NotImplementedError: rows 2 to 11: task 5`. Do not run ruff in this state.
    - **Property 6: P3.6 TOOL_CALL names a tool of the recorded place**
    - **Validates: Requirements 3.6**

  - [ ] 5.8 Write property test P3.7 (a loop of denied actions ends in KILLED(STEPS_EXCEEDED))
    - Files: `backend/tests/properties/test_engine_properties.py` (append).
    - Test function `test_p3_7_denied_loop_ends_in_steps_exceeded`. Enforcement on, a small `max_steps`, and a sequence drawn only from always-denied actions with the agent never leaving the library: `bogus`, `""`, `" read_records "`, `"read_recоrds"`, `"go:"`, `"go:nowhere"`, `"go:välts"`, `"go:library"`, and the vault tools `read_records` and `export_records` (not held by the library). `go:vault` is excluded. Drive `step` directly with an un-advanced clock, so the lifetime cannot be the cause. Let `n` be `engine.state.permit.max_steps` after construction (the library ceiling may narrow the generated permit). Assert the count of `DENIED` events equals `n` (0 when `n` is 0), the run ends with `KILLED(STEPS_EXCEEDED)` with `limit == n` and `observed == n + 1`, no tool was executed, and `spent` is 0.
    - Docstring: "Property P3.7: a loop of denied actions ends in KILLED(STEPS_EXCEEDED). Validates: Requirements 3.4, 3.5".
    - Run `uv --directory backend run pytest -q tests/properties/test_engine_properties.py`
    - Expected red: `NotImplementedError: rows 2 to 11: task 5`. Do not run ruff in this state.
    - **Property 7: P3.7 A loop of denied actions ends in KILLED(STEPS_EXCEEDED)**
    - **Validates: Requirements 3.4, 3.5**

  - [ ] 5.9 Implement the enforce=True step algorithm and make the tests pass
    - Files: `backend/src/telepermit/engine.py`.
    - Replace the `NotImplementedError("rows 2 to 11: task 5")` guard with rows 2 to 11 of the table in design.md, in that order, first match decides. Action matching is exact string comparison; an action is a go action when `action.startswith("go:")` and its destination is `action[3:]`. Add no guard for enforce=False: until task 6 the `enforce` flag is stored but not consulted, so an Engine built with enforcement off runs the enforced rows. Sub-tasks 6.1 and 6.2 are red for that reason.
    - Kill: set the status to KILLED BEFORE emitting, then emit `KILLED` and `RUN_ENDED(KILLED)` with the same snapshot. Lifetime and steps kills do not increment the snapshot step; the allowance kill already includes the attempt and leaves `spent` unchanged. `elapsed = clock.now() - born`; equal to the limit is allowed on every limit.
    - `place.execute` is called in exactly one place in the code base, in row 10 of this method, with NO try/except around it in Group A (a tool exception just propagates).
    - Row 11 calls `admit` on the destination with the CURRENT permit (`state.permit`), steps and spent AFTER the increments, and elapsed. On REFUSE the place and permit stay, `permit_after` in the event is the current permit and `narrowed_fields` is `[]`. `step` returns only the events emitted by that call.
    - Run `uv --directory backend run pytest -q tests/unit/test_engine.py`
    - Expected: all tests pass, including `test_golden_run_b_hand_driven`.
    - Run `uv --directory backend run pytest -q tests/properties/test_engine_properties.py`
    - Expected: P3.1 to P3.7 and P3.9 pass.
    - Run `uv --directory backend run ruff check .`
    - Run `uv --directory backend run ruff format --check .`
    - Run `git grep -n NotImplementedError -- backend/src/telepermit/engine.py`
    - Expected: prints nothing (exit code 1). Do not tick or commit task 5.9 until it prints nothing. PowerShell has no plain `grep`; `git grep` searches the same file.
    - Update docs/PROGRESS.md. Run `git status --short`, stage the changed files by name, commit `feat(engine): enforced step algorithm (task 5.9)`, print the DONE line.
    - Acceptance check: all 5.x tests green, golden Run B green, the `NotImplementedError` search above prints nothing, ruff clean, commit made.
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8, 3.11_

- [ ] 6. T3.6 Engine step() with enforcement off
  - Depends on T3.5. Implements the enforce=False variant of the design table: lifetime, steps, permit and allowance checks skipped, no kills; NOT_IN_PLACE still denies and consumes a step; `finish` still ends the run; steps and spent still metered; `go` moves at once with `BORDER_CHECK(ADMIT, UNENFORCED)` and no identity or class check.
  - Edge cases: a forged identity still runs when enforcement is off; spend may exceed the allowance.
  - _Requirements: 3.10_

  - [ ] 6.1 Write the unenforced step unit tests first
    - Files: `backend/tests/unit/test_engine.py` (append; keep earlier tests).
    - `test_unenforced_no_kill_on_any_limit` (lifetime far exceeded, steps beyond `max_steps`, spend beyond the allowance: no `KILLED` event, status ALIVE).
    - `test_unenforced_no_not_in_permit_denial` (an action outside the permit runs).
    - `test_unenforced_not_in_place_still_denies` (the other place's tool is `DENIED` NOT_IN_PLACE and consumes a step).
    - `test_unenforced_go_border_check_unenforced`: `BORDER_CHECK` with decision ADMIT, reason UNENFORCED, `permit_after` equal to the unchanged permit, `narrowed_fields` `[]`, cost 1, the agent moved; this works with a forged identity and a disallowed class (no identity or class check).
    - `test_unenforced_finish_ends_run`.
    - `test_unenforced_spend_exceeds_allowance_witness`: a deterministic sequence in which `state.spent` ends above `state.permit.allowance` (existential fact, so a unit test and not a property).
    - Run `uv --directory backend run pytest -q tests/unit/test_engine.py`
    - Expected red: there is no guard, so an Engine built with enforcement off still runs the enforced rows. The tests fail with `AssertionError` (for example a `KILLED` event or a `DENIED` NOT_IN_PERMIT event is present, or the `BORDER_CHECK` is not ADMIT with reason UNENFORCED). `test_unenforced_not_in_place_still_denies` and `test_unenforced_finish_ends_run` may already pass, because the enforced rows deny and finish the same way; that is acceptable. Earlier tests stay green. Do not run ruff in this state.
    - Acceptance check: at least `test_unenforced_no_kill_on_any_limit`, `test_unenforced_no_not_in_permit_denial`, `test_unenforced_go_border_check_unenforced` and `test_unenforced_spend_exceeds_allowance_witness` fail with `AssertionError`, and no test fails with an import error or a `NotImplementedError`.
    - _Requirements: 3.10_

  - [ ] 6.2 Write property test P3.8 (with enforcement off there is no kill and no permit denial)
    - Files: `backend/tests/properties/test_engine_properties.py` (append).
    - Test function `test_p3_8_unenforced_no_kill_no_permit_denial`. Enforcement off, any permit and sequence, including a forged identity in a share of examples. Assert: no `KILLED` event; no `DENIED` with reason NOT_IN_PERMIT; every `DENIED` has reason NOT_IN_PLACE; no spawn `BORDER_CHECK` (the log starts with only `RUN_STARTED`); every `BORDER_CHECK` has decision ADMIT, reason UNENFORCED, `narrowed_fields == []`, and `permit_after` equal to the unchanged permit; `step` and `spent` in the snapshots keep being metered (non-decreasing). Only the universal parts are asserted here; the existential "spend may exceed the allowance" is the witness unit test of 6.1.
    - Docstring: "Property P3.8: with enforcement off there is never a KILLED event or a permit-reason DENIED. Validates: Requirements 3.10".
    - Run `uv --directory backend run pytest -q tests/properties/test_engine_properties.py`
    - Expected red: `AssertionError` with a shrunk counterexample (for example a `KILLED` event in an unenforced run). Do not run ruff in this state.
    - **Property 8: P3.8 With enforcement off there is no kill and no permit denial**
    - **Validates: Requirements 3.10**

  - [ ] 6.3 Implement the enforce=False variant and make the tests pass
    - Files: `backend/src/telepermit/engine.py`.
    - Per the design table: skip rows 2, 4, 6 and 8; keep rows 1, 3, 5, 7, 9, 10; replace row 11 with the immediate move and `BORDER_CHECK(ADMIT, UNENFORCED, permit_after = unchanged permit, narrowed_fields [], cost 1)`, no `admit` call. Make `step` consult the `enforce` flag.
    - Run `uv --directory backend run pytest -q tests/unit/test_engine.py`
    - Expected: all tests pass.
    - Run `uv --directory backend run pytest -q tests/properties/test_engine_properties.py`
    - Expected: P3.1 to P3.9 pass.
    - Run `uv --directory backend run ruff check .`
    - Run `uv --directory backend run ruff format --check .`
    - Run `git grep -n NotImplementedError -- backend/src/telepermit/engine.py`
    - Expected: prints nothing (exit code 1). Do not tick or commit task 6.3 until it prints nothing.
    - Update docs/PROGRESS.md. Run `git status --short`, stage the changed files by name, commit `feat(engine): unenforced step variant (task 6.3)`, print the DONE line.
    - Acceptance check: all nine properties and the unit tests green, the `NotImplementedError` search above prints nothing, ruff clean, commit made.
    - _Requirements: 3.10_

- [ ] 7. T3.7 Engine run() loop
  - Depends on T3.5 and T3.6. Adds `run(driver, task, max_turns=HARNESS_CAP)`, the private `_observe` and `_last_result`, and the task consistency check of criterion 3.15 (a non-empty constructor `task` must equal the `task` given to `run`). In Group A `run` calls `clock.advance(TICK_S)` unconditionally (the current CONTRACTS text). Acceptance: a 30-turn run with `TICK_S` leaves a `TickClock` at exactly 30.0.
  - Edge cases: `max_turns` 0 gives HARNESS_CAP at once with no driver call and no clock advance; the agent finishes mid-loop; an Engine that is already REFUSED returns REFUSED without calling the driver; a negative `max_turns` raises `ValueError`; turns are numbered from 1; a `run` task that differs from a non-empty constructor task raises `ValueError` before anything happens, and an empty constructor task accepts any task.
  - _Requirements: 3.12, 3.10, 3.11, 3.15_

  - [ ] 7.1 Write the run loop unit tests first
    - Files: `backend/tests/unit/test_engine.py` (append; keep earlier tests). The replay driver class is defined INSIDE this file, not under `drivers/`: it returns a list of `Proposal` objects in order, repeats the last one, and records every `Observation` it receives.
    - `test_run_thirty_turns_clock_at_thirty` (a never-finishing driver; status HARNESS_CAP; `TickClock.now() == 30.0`).
    - `test_run_max_turns_zero_is_harness_cap` (no driver call, no clock advance, `RUN_ENDED(HARNESS_CAP)` emitted once).
    - `test_run_finish_mid_loop` (the loop stops, status FINISHED, no HARNESS_CAP event).
    - `test_run_on_refused_engine_skips_driver` (REFUSED returned, driver never called, no new event).
    - `test_run_negative_max_turns_raises` (`ValueError`, no turn taken).
    - Criterion 3.15, four tests. The Engine is built with `task="Summarise the quarterly briefing and file a short note."` unless stated otherwise:
      - `test_run_task_mismatch_raises_value_error`: `run(driver, "A different task")` raises `ValueError`, and the recording driver was never called.
      - `test_run_task_mismatch_has_no_side_effects`: after that `ValueError` the `TickClock` time, `engine.events` and `engine.state` are unchanged and the status is ALIVE; a following `run` with the matching task proceeds normally to HARNESS_CAP.
      - `test_run_matching_task_is_accepted`: the matching task runs normally; `run(driver, "")` on the same Engine raises `ValueError`, because an empty run task differs from a non-empty constructor task.
      - `test_run_empty_constructor_task_accepts_any_task`: an Engine built without `task` (default empty) runs with any task, and the recorded `Observation.task` equals the task given to `run`.
    - `test_run_turns_are_one_based` (the recorded observations have `turn` 1, 2, 3, ...).
    - `test_observation_tools_listing`: the current place's tools in the order of that Place's `tools` dict, each as `{"name", "description", "args"}`; then `go:<place>` for every other place in `places` order with description `Move to <place>.` and `args` `{}`, never the current place; then `finish` with description `End the run.` last.
    - `test_last_result_mapping`: first turn `None`; tool result string after a `TOOL_CALL`; exactly `DENIED: action '<action>' is not available to you here.` after a denial; `You are now in <place>.` after an admitted crossing; `REFUSED at the border of <place>.` after a refused crossing (inline refusing destination), with no reason code.
    - `test_observations_contain_no_forbidden_words_or_signature`: across the Run A and Run B `run()` calls, no string in any Observation (fields, tool names, descriptions, results) contains `permit`, `allowance` or `teleclick` (case-insensitive) or the identity signature hex.
    - `test_golden_run_a_via_run`: `enforce=False`, inline replay driver (`read_document`, `go:vault`, `export_records` twice, then `read_records` repeated): 32 events, final status HARNESS_CAP, step 30, spent 120, `export_records` spent values 22 and 42, two exports in the vault outbox, no `DENIED` and no `KILLED`.
    - `test_golden_run_b_via_run`: `enforce=True`, the Run B script through `run()` produces the same events as the hand-driven run apart from `t`.
    - Run `uv --directory backend run pytest -q tests/unit/test_engine.py`
    - Expected red: `AttributeError: 'Engine' object has no attribute 'run'`. Earlier tests stay green. Do not run ruff in this state.
    - Acceptance check: every new test fails with that AttributeError. This includes the four criterion 3.15 tests, which are red here only because `run` does not exist. Sub-task 7.2 shows them red for the right reason before the check is added.
    - _Requirements: 3.12, 3.10, 3.11, 3.15_

  - [ ] 7.2 Implement run, _observe and _last_result and make the tests pass
    - Files: `backend/src/telepermit/engine.py`.
    - Step 1 (right-reason red for criterion 3.15): implement `run`, `_observe` and `_last_result` WITHOUT the task consistency check.
    - Run `uv --directory backend run pytest -q tests/unit/test_engine.py`
    - Expected: everything passes except `test_run_task_mismatch_raises_value_error`, `test_run_task_mismatch_has_no_side_effects` and `test_run_matching_task_is_accepted` (its empty-run-task case), which fail with `Failed: DID NOT RAISE <class 'ValueError'>`. Paste this output before step 2.
    - Step 2: store the constructor `task` in the Engine as `_task` and, at the top of `run`, before the `max_turns` check and before any clock advance, driver call or event, raise `ValueError` if `self._task` is non-empty and `task != self._task`. An empty constructor `task` never raises.
    - `run`: `ValueError` for a negative `max_turns` before any turn. Loop `turn` from 1 to `max_turns`: stop if the status is not ALIVE; `self._clock.advance(TICK_S)` (unconditional in Group A; import `TICK_S` from `clock.py`); build the Observation; `driver.propose`; `step`; derive `last_result` from the events that step emitted. After the loop, if the status is still ALIVE set HARNESS_CAP and emit `RUN_ENDED(HARNESS_CAP)`. Return `RunResult(status, copy of events, state)`.
    - `_observe` and `_last_result` exactly as in the design tables. Observation text contains no permit, spend, cost or key information.
    - Run `uv --directory backend run pytest -q tests/unit/test_engine.py`
    - Expected: all tests pass, including both golden runs via `run()`.
    - Run `uv --directory backend run pytest -q tests/properties/test_engine_properties.py`
    - Expected: P3.1 to P3.9 still pass.
    - Run `uv --directory backend run ruff check .`
    - Run `uv --directory backend run ruff format --check .`
    - Update docs/PROGRESS.md. Run `git status --short`, stage the changed files by name, commit `feat(engine): run loop and observations (task 7.2)`, print the DONE line.
    - Acceptance check: step 1 showed exactly the three 3.15 tests red with DID NOT RAISE; after step 2 `test_engine.py` and the property file are green including all four criterion 3.15 tests; ruff clean; commit made.
    - _Requirements: 3.12, 3.10, 3.11, 3.15_

- [ ] 8. T3.8 Architecture test
  - Depends on T3.3 and T3.5. Builds `tests/test_architecture.py` with pure checker functions over a source string and a file name: `check_driver_imports`, `check_no_execute_calls`, `is_engine_module`, `collect_sources`. Security invariants 1 and 2. Acceptance: the real-source scans pass and a deliberately bad snippet is caught by the self-test.
  - Edge cases: method definitions named `execute` are fine (only calls are flagged); test files are not scanned; a file named `engine.py` in a sub-package is NOT exempt; imports inside functions or `if TYPE_CHECKING` blocks count.
  - _Requirements: 3.13_

  - [ ] 8.1 Write the architecture test file first, with stub checkers
    - Files: `backend/tests/test_architecture.py` (new).
    - Define the four checker functions as STUBS: `check_driver_imports` and `check_no_execute_calls` return an empty list, `is_engine_module` returns `False`, `collect_sources` returns an empty list. Write the complete tests around them.
    - Self-test with bad snippets, each asserted to return at least one violation: `import telepermit.engine`, `import telepermit.engine as e`, `import telepermit.place.sub`, bare `import engine`, `from telepermit.engine import X`, `from telepermit import engine`, `from .engine import X`, `from ..tools import Y`, `from . import engine`, `from .. import place`, an import inside a function body, `place.execute("x", {})` and `Place.execute(p, "x", {})`. Test name `test_checker_self_test_catches_bad_snippets`.
    - Self-test with good snippets, each asserted to return no violation: `import json`, `from telepermit.drivers.base import Proposal`, `from . import base`, `from .base import Observation`, `from telepermit.permit import Permit`, `class P:\n    def execute(self): ...`, `place.execute_plan()`. Test name `test_checker_self_test_passes_good_snippets`.
    - `test_is_engine_module_cases`: `is_engine_module(Path("engine.py"))` is True, `is_engine_module(Path("drivers/engine.py"))` is False.
    - Real-source tests: `test_drivers_do_not_import_runtime_modules` (every file under `src/telepermit/drivers/`), `test_only_engine_calls_execute` (every `.py` file under `src/telepermit/` except `engine.py` at the package root; tests are not scanned). The package root is `Path(__file__).resolve().parents[1] / "src" / "telepermit"`.
    - `test_walker_is_not_vacuous`: the root directory exists and `collect_sources` returns a non-empty set containing `engine.py`, `place.py` and `drivers/base.py`.
    - Run `uv --directory backend run pytest -q tests/test_architecture.py`
    - Expected red: the self-test of bad snippets fails with `AssertionError` because the stubs flag nothing, `test_is_engine_module_cases` fails with `AssertionError`, and `test_walker_is_not_vacuous` fails with `AssertionError` because `collect_sources` returns nothing. The two real-source scans and the good-snippet self-test pass vacuously at this stage, which is why the non-vacuity guard exists. Do not run ruff in this state.
    - Acceptance check: exactly the three failing tests above, each with `AssertionError`.
    - _Requirements: 3.13_

  - [ ] 8.2 Implement the checkers with ast and make the tests pass
    - Files: `backend/tests/test_architecture.py`.
    - `check_driver_imports`: walk every `ast.Import` and `ast.ImportFrom` at any depth. Flag `import telepermit.<banned>...` (any alias), bare `import <banned>`, `from telepermit.<banned> import X`, `from telepermit import <banned>`, relative `from .<banned> import X` at any level, and relative `from . import <banned>` at any level. Banned names: `engine`, `identity`, `place`, `tools`. Third-party names such as `anthropic.lib.tools` are not flagged.
    - `check_no_execute_calls`: flag every `ast.Call` whose `func` is an `ast.Attribute` with `attr == "execute"`. A `FunctionDef` named `execute` is not a call and passes.
    - `is_engine_module`: True only for `engine.py` at the package root. `collect_sources`: every `*.py` file under the package root.
    - Each violation string has the form `<filename>:<line>: <message>`.
    - Known limitation to state in a comment in the file and in the DONE report: this is a static check. It does not detect dynamic imports (`importlib.import_module`, `__import__`), `getattr(place, "execute")`, aliasing such as `run = place.execute`, or attribute access through a bare `import telepermit`. It reduces accidental breaches and is not a sandbox.
    - Run `uv --directory backend run pytest -q tests/test_architecture.py`
    - Expected: all tests pass.
    - Run `uv --directory backend run ruff check .`
    - Run `uv --directory backend run ruff format --check .`
    - Update docs/PROGRESS.md. Run `git status --short`, stage the file by name, commit `test(architecture): ast checks for invariants 1 and 2 (task 8.2)`, print the DONE line.
    - Acceptance check: self-tests and real-source scans green, the limitation stated, ruff clean, commit made.
    - _Requirements: 3.13_

- [ ] 9. Group A final checkpoint
  - Run `uv --directory backend run pytest -q`
  - Report the final total as a difference from the count recorded before sub-task 1.1 (baseline 89), all passing.
  - Run `uv --directory backend run ruff check .`
  - Run `uv --directory backend run ruff format --check .`
  - Inspection: run `git grep -n "\.execute(" -- backend/src`. Expected hits only in `engine.py`; any other hit (even in a docstring) is reported, not silently accepted.
  - Inspection: run `git grep -n -E "^\s*(from|import) " -- backend/src/telepermit/drivers`. Expected: only standard-library imports (`__future__`, `dataclasses`, `typing`) and no import of `engine`, `identity`, `place` or `tools`.
  - Confirm that all nine properties P3.1 to P3.9 and the architecture test pass, that no dependency outside tech.md was added, and that no scenario, driver implementation or CLI exists.
  - Update docs/PROGRESS.md: spec folder `.kiro/specs/engine-audit`, branch `spec/03-engine-audit`, Group A done (T3.1 to T3.8), Group B pending the owner.
  - Print the DONE line with the real counts. Ensure all tests pass, ask the user if questions arise.
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8, 3.9, 3.10, 3.11, 3.12, 3.13, 3.14, 3.15_

### Group B

**Do not start any Group B task until the owner confirms in chat that task 10 is done.**

Group B implements the approved decisions (a) tool errors and (d) conditional clock advance. It needs the CONTRACTS amendment first, because the amendment adds the status `ERROR` and the conditional `advance`.

- [ ] 10. Owner applies the CONTRACTS amendment
  - Owner-only task. The agent does not edit docs/CONTRACTS.md. The owner uses the suggested text kept at the end of design.md: the status `ERROR` in the section 5 status line, the `RUN_ENDED` status list in section 6, the `TOOL_CALL` error result `"error: <message>"`, and `run` advancing the clock only when the clock provides `advance`.
  - Test command: none (owner action).
  - _Requirements: 3.11, 3.12_

  - [ ] 10.1 Owner edits docs/CONTRACTS.md and confirms in chat
    - Files: `docs/CONTRACTS.md` (owner edit; the agent does not touch it and does not stage it).
    - Acceptance check: the owner confirms in chat that the amendment is applied.
    - _Requirements: 3.11, 3.12_

  - [ ] 10.2 Agent confirms the amendment with read-only searches
    - Files: none changed.
    - Run `git grep -n "ERROR" -- docs/CONTRACTS.md`
    - Run `git grep -n "error:" -- docs/CONTRACTS.md`
    - Run `git grep -n "advance" -- docs/CONTRACTS.md`
    - Expected: `ERROR` appears in the section 5 status line and in the section 6 `RUN_ENDED` status list; `error:` appears in the section 6 `TOOL_CALL` result text; `advance` appears in section 5 with the condition that the clock provides it. If any of the three is missing, stop and tell the owner; do not edit CONTRACTS.md.
    - Acceptance check: all three found in the stated sections.
    - _Requirements: 3.11, 3.12_

- [ ] 11. Decision (a): tool errors
  - Blocked until the owner confirms task 10.
  - Adds `STATUS_ERROR` (literal `"ERROR"`) to `audit.py` and rows 10a and 10b to `engine.py`. A `ToolArgumentError` from `place.execute` becomes a `TOOL_CALL` with result `"error: <message>"` (cost stays charged, step stays consumed, status stays ALIVE). Any other `Exception` sets the status ERROR before emitting, emits `RUN_ENDED(ERROR)` and re-raises unchanged. `BaseException` and a bare `except` are never used.
  - Edge cases: `KeyboardInterrupt` propagates and the status is not set to ERROR; the `RUN_ENDED(ERROR)` snapshot includes the attempt and the charged cost; `reduce_events` equals the Engine state; `step` after ERROR raises `AgentNotAlive`.
  - _Requirements: 3.1, 3.11_

  - [ ] 11.1 Write the tool error tests first
    - Blocked until the owner confirms task 10.
    - Files: `backend/tests/unit/test_audit.py` (append), `backend/tests/unit/test_engine.py` (append).
    - In `test_audit.py`: `test_status_error_constant` (`STATUS_ERROR == "ERROR"` and it is in `STATUSES`), `test_reduce_run_ended_error` (a hand-built `RUN_ENDED(ERROR)` reduces to status ERROR).
    - Change of an existing test, moved here from Group A on the owner's instruction: `test_statuses_are_the_five`, written in sub-task 1.1 and left unchanged with FIVE statuses throughout Group A, changes in this sub-task. Its expected set becomes the six statuses ALIVE, KILLED, FINISHED, REFUSED, HARNESS_CAP and ERROR, and it is renamed `test_statuses_are_the_six`. The change is required by approved decision (a) and the CONTRACTS amendment of task 10. It does not weaken the check, because it still asserts the exact set. State this in the commit message of 11.2.
    - In `test_engine.py`, with a small inline `Tool` whose `fn` raises `RuntimeError("boom")` placed in an inline Place:
      - `test_tool_argument_error_is_logged_as_tool_call_error` (for example `read_document` called with `{}`): exactly one event, a `TOOL_CALL` whose `result` starts with `error:`, the cost stays charged, the step stays consumed, the status stays ALIVE.
      - `test_unexpected_tool_exception_sets_error_and_reraises`: the same `RuntimeError` propagates out of `step`; status ERROR; exactly one new event, `RUN_ENDED` with status ERROR, and no `KILLED` or `FINISHED`; the snapshot step includes the attempt and spent includes the charged cost; `reduce_events(engine.events)` equals the Engine state values with status ERROR.
      - `test_step_after_error_raises` (`AgentNotAlive`, log unchanged).
      - `test_base_exception_is_not_caught`: a tool raising `KeyboardInterrupt` propagates it, the status stays ALIVE, no `RUN_ENDED` is emitted.
      - `test_run_propagates_tool_exception_after_error_status`: `run` with a driver proposing the raising tool lets the exception out and the Engine status is ERROR.
    - Run `uv --directory backend run pytest -q tests/unit/test_audit.py`
    - Run `uv --directory backend run pytest -q tests/unit/test_engine.py`
    - Expected red: `ImportError: cannot import name 'STATUS_ERROR' from 'telepermit.audit'` at collection of both files (both import the constant), so the earlier tests in both files error at collection too until 11.2. Do not run ruff in this state.
    - Acceptance check: the single ImportError for each of the two files.
    - _Requirements: 3.1, 3.11_

  - [ ] 11.2 Implement STATUS_ERROR and rows 10a and 10b and make the tests pass
    - Blocked until the owner confirms task 10.
    - Files: `backend/src/telepermit/audit.py`, `backend/src/telepermit/engine.py`.
    - `audit.py`: add `STATUS_ERROR: Final = "ERROR"` and include it in `STATUSES`.
    - `engine.py`: the `try` wraps only the `place.execute` call. `except ToolArgumentError` first: emit `TOOL_CALL` with `result = "error: <message>"` and the normal snapshot. Then `except Exception`: set the status to ERROR BEFORE emitting, emit `RUN_ENDED(ERROR)`, then a bare `raise`. Never `BaseException`, never a bare `except`. Exceptions raised anywhere else (from `admit`, from `driver.propose`) are not caught: state this limitation in the DONE report.
    - Run `uv --directory backend run pytest -q tests/unit/test_audit.py`
    - Run `uv --directory backend run pytest -q tests/unit/test_engine.py`
    - Run `uv --directory backend run pytest -q tests/properties/test_engine_properties.py`
    - Expected: all tests pass in all three files.
    - Run `uv --directory backend run ruff check .`
    - Run `uv --directory backend run ruff format --check .`
    - Update docs/PROGRESS.md. Run `git status --short`, stage the changed files by name, commit `feat(engine): tool error handling (task 11.2)`, print the DONE line.
    - Acceptance check: the five new engine tests and two new audit tests green, earlier tests still green, ruff clean, commit made.
    - _Requirements: 3.1, 3.11_

- [ ] 12. Decision (d): conditional clock advance
  - Blocked until the owner confirms task 10.
  - The Engine `clock` parameter is typed `Clock` (only `now()`), and `run` advances the clock by `TICK_S` only when the clock object provides a callable `advance`.
  - Edge cases: a clock with only `now()` runs to HARNESS_CAP without an error and its reported time never changes; a `TickClock` still advances 1.0 per turn.
  - _Requirements: 3.12_

  - [ ] 12.1 Write the now-only clock test first
    - Blocked until the owner confirms task 10.
    - Files: `backend/tests/unit/test_engine.py` (append).
    - `test_run_with_now_only_clock_does_not_advance`: an inline clock class `NowOnlyClock` with only `now()`; `run` to HARNESS_CAP completes without `AttributeError` and the reported time never changes; in the same test a `TickClock` run still ends with the clock advanced by 1.0 per turn.
    - Run `uv --directory backend run pytest -q tests/unit/test_engine.py`
    - Expected red: `AttributeError: 'NowOnlyClock' object has no attribute 'advance'` for the new test only. Do not run ruff in this state.
    - Acceptance check: only the new test fails, with that AttributeError.
    - _Requirements: 3.12_

  - [ ] 12.2 Implement the conditional advance and make the test pass
    - Blocked until the owner confirms task 10.
    - Files: `backend/src/telepermit/engine.py`.
    - Type the `clock` parameter as `Clock`. In `run` read `advance = getattr(self._clock, "advance", None)` and call `advance(TICK_S)` only if it is callable.
    - Run `uv --directory backend run pytest -q tests/unit/test_engine.py`
    - Expected: all tests pass.
    - Run `uv --directory backend run ruff check .`
    - Run `uv --directory backend run ruff format --check .`
    - Update docs/PROGRESS.md. Run `git status --short`, stage the changed file by name, commit `feat(engine): conditional clock advance (task 12.2)`, print the DONE line.
    - Acceptance check: `test_engine.py` green including the 30-turn clock test, ruff clean, commit made.
    - _Requirements: 3.12_

- [ ] 13. Widen the property generators
  - Blocked until the owner confirms task 10.
  - Tests-only task. In Group A the args strategy drew from the required-keys table because a missing key would have raised an unhandled `ToolArgumentError`. With task 11 in place a missing key becomes a `TOOL_CALL` with an `error:` result, so the strategy can be widened.
  - _Requirements: 3.1, 3.4, 3.5, 3.6, 3.7, 3.8, 3.9, 3.10, 3.11, 3.14_

  - [ ] 13.1 Replace the args strategy with random dicts and re-run P3.1 to P3.9
    - Blocked until the owner confirms task 10.
    - Files: `backend/tests/properties/test_engine_properties.py`.
    - Change the shared args strategy from the required-keys table to random dicts: keys drawn from `name`, `query`, `destination` and arbitrary text, values arbitrary text, missing keys allowed. No property assertion is changed or weakened.
    - This is the one task that is NOT expected to be red first. The nine properties already exist and the Group B implementation is already in place, so the first run is expected to be green. If it is red, the counterexample exposes a real defect: stop, show the shrunk counterexample and the diagnosis, and do not weaken a property.
    - Run `uv --directory backend run pytest -q tests/properties/test_engine_properties.py`
    - Expected: P3.1 to P3.9 pass.
    - Run `uv --directory backend run ruff check .`
    - Run `uv --directory backend run ruff format --check .`
    - Update docs/PROGRESS.md. Run `git status --short`, stage the changed file by name, commit `test(engine): widen property arguments (task 13.1)`, print the DONE line.
    - Acceptance check: nine properties green with the widened strategy, ruff clean, commit made.
    - _Requirements: 3.1, 3.4, 3.5, 3.6, 3.7, 3.8, 3.9, 3.10, 3.11, 3.14_

- [ ] 14. Group B final checkpoint
  - Blocked until the owner confirms task 10.
  - Run `uv --directory backend run pytest -q`
  - Report the final total as a difference from the count recorded before sub-task 1.1 (baseline 89), all passing.
  - Run `uv --directory backend run ruff check .`
  - Run `uv --directory backend run ruff format --check .`
  - Run `git grep -n "\.execute(" -- backend/src` and confirm hits only in `engine.py`.
  - Confirm that `except` in `engine.py` appears only as `except ToolArgumentError` and `except Exception`, with no bare `except` and no `BaseException`.
  - Update docs/PROGRESS.md: spec folder `.kiro/specs/engine-audit`, branch `spec/03-engine-audit`, Groups A and B done, branch ready for `MERGE`.
  - Print the DONE line with the real counts. Ensure all tests pass, ask the user if questions arise.
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8, 3.9, 3.10, 3.11, 3.12, 3.13, 3.14, 3.15_

## Notes

- No task is optional. Property tests P3.1 to P3.9 are required, each in its own sub-task.
- Group B task 10 is the owner's. The agent may not start any Group B task before the owner confirms in chat that task 10 is done.
- `engine.py` carries one temporary `NotImplementedError` guard during Group A (added in 4.3, removed in 5.9). A test that fails with that error before 5.9 is the expected red. `git grep -n NotImplementedError -- backend/src/telepermit/engine.py` must print nothing before tasks 5.9 and 6.3 are ticked.
- Test files are shared between tasks, so the dependency graph places tasks that write to the same file in different waves. The tasks are built strictly in order, and each green top-level task is committed before the next task's tests are written.
- A task is done only when its tests were run, the output was pasted, ruff check and ruff format check are clean, and PROGRESS.md is updated.
- The architecture test is a static check and has the limitations stated in sub-task 8.2.
- Exceptions raised outside `place.execute` (from `admit`, from `driver.propose`) are not caught by decision (a). They propagate, and the log has no terminal event.

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["1.2"] },
    { "id": 2, "tasks": ["2.1"] },
    { "id": 3, "tasks": ["2.2"] },
    { "id": 4, "tasks": ["3.1"] },
    { "id": 5, "tasks": ["3.2"] },
    { "id": 6, "tasks": ["4.1"] },
    { "id": 7, "tasks": ["4.2"] },
    { "id": 8, "tasks": ["4.3"] },
    { "id": 9, "tasks": ["5.1"] },
    { "id": 10, "tasks": ["5.2"] },
    { "id": 11, "tasks": ["5.3"] },
    { "id": 12, "tasks": ["5.4"] },
    { "id": 13, "tasks": ["5.5"] },
    { "id": 14, "tasks": ["5.6"] },
    { "id": 15, "tasks": ["5.7"] },
    { "id": 16, "tasks": ["5.8"] },
    { "id": 17, "tasks": ["5.9"] },
    { "id": 18, "tasks": ["6.1"] },
    { "id": 19, "tasks": ["6.2"] },
    { "id": 20, "tasks": ["6.3"] },
    { "id": 21, "tasks": ["7.1"] },
    { "id": 22, "tasks": ["7.2"] },
    { "id": 23, "tasks": ["8.1"] },
    { "id": 24, "tasks": ["8.2"] },
    { "id": 25, "tasks": ["10.1"] },
    { "id": 26, "tasks": ["10.2"] },
    { "id": 27, "tasks": ["11.1"] },
    { "id": 28, "tasks": ["11.2"] },
    { "id": 29, "tasks": ["12.1"] },
    { "id": 30, "tasks": ["12.2"] },
    { "id": 31, "tasks": ["13.1"] }
  ]
}
```
