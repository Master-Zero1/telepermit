# Implementation Plan: scenario-drivers-replays

## Overview

Implements the ScriptedDriver, the poisoned_briefing scenario, the LLM driver, the CLI, the replay format additions to `audit.py` and the recorder with the committed replay files (CONTRACTS sections 7 to 10, golden traces from section 8), in the order of roadmap items T4.1 to T4.7. Language: Python. Branch: `spec/04-scenario-drivers-replays`. The requirement IDs are the criteria 4.1 to 4.9 of requirements.md. Design decisions (a) to m are approved. Decision (b) needs an owner-applied CONTRACTS amendment, so the work is split in two groups.

- Group A is everything except the CLI `--out` option. It follows the CURRENT CONTRACTS text: the recorder writes `generated_by` as `"scripts/record_replays.py"`, and the value `"telepermit.cli"` is written nowhere in Group A (no `GENERATED_BY_CLI` constant, no `--out` option in the CLI parser).
- Group B is the CLI `--out` work. It starts only after the owner applies the CONTRACTS amendment (task 10) and confirms in chat.

Order of build:
- T4.1 builds `drivers/__init__.py` (protocol literals) and `drivers/scripted.py`.
- T4.2 builds the scenario module (constants, `LabeledDriver`, `World`, `ScenarioRun`, `build_world`, `run_scenario`) and the golden traces of Run A, Run B and Run C.
- T4.3 adds the observation text safety tests (no implementation).
- T4.4 builds `drivers/llm.py` and the inline network guard.
- T4.5 builds `cli.py` without `--out`.
- T4.6 adds the replay format to `audit.py` and the replay helpers to the scenario (part 1), then the recorder and the two Milestone M1 replays (part 2).
- T4.7 adds the forged-identity replay.
- T4.5 continued (Group B) adds `--out`.

Hand-off mode: the human runs every command and pastes the output. Each test sub-task states the exact commands, the expected red reason and an acceptance check. Every task with both code and tests follows the same order: write the tests first, run them, confirm they fail for the stated reason, then implement and re-run to green. Lint steps are separate single commands, never chained, and ruff is run only after implementation (while a module is missing, ruff reports spurious I001).

Ruff commands:
- Until the scripts folder exists (tasks 1 to 6), use `uv --directory backend run ruff check .` and `uv --directory backend run ruff format --check .`.
- From the recorder task (task 7) onward, use `uv --directory backend run ruff check --config pyproject.toml . ../scripts` and `uv --directory backend run ruff format --check --config pyproject.toml . ../scripts`.

All six property tests (P4.1 to P4.6) are required, none optional. Each property docstring has the form `Property P<n>.<m>: <statement>. Validates: Requirements 4.x`. The Hypothesis profile in the existing conftest (deadline none, 200 examples) applies.

Conventions that apply to every file written in this spec:
- Start each Python module with `from __future__ import annotations`. Source modules have a docstring naming the CONTRACTS section they implement (it comes before the future import).
- A blank line between third-party imports (pytest, hypothesis) and `from telepermit...` imports, otherwise ruff reports I001.
- Every file ends with exactly one trailing newline. Write LF line endings. Lines are at most 100 characters.
- When inserting blocks into an existing file, keep two blank lines between top-level definitions and one blank line between methods.
- Tests build their world inline from scenario functions or from `tools` and `place`. No shared helper module. Existing tests are never weakened.
- No source module outside `engine.py` calls `.execute(`. No new dependency is added. The `anthropic` package is not installed and is never imported at module level. No test makes a network call.
- Do not put `@given` tests in a file that has the autouse network-guard fixture (Hypothesis rejects function-scoped fixtures). This is why the LLM property test (P4.6) lives in a different file from the LLM unit tests and their guard. The CLI tests have no `@given` test, so they share a file with their guard.
- Commit each green top-level task BEFORE writing the next top-level task's tests, so red tests never land in an earlier task's commit. Run `git status --short` before every commit and stage files by name.
- Before sub-task 1.1, record the test count with `uv --directory backend run pytest -q --collect-only -q`. The baseline is the SUM of the per-file counts that command prints, taken from the real pasted output and never estimated; 210 is only a cross-check. Report the final totals as a difference from the recorded count.
- After each top-level task print: `DONE T<id>: <one line>. Tests: <passed>/<total>. Ruff: clean. Files: <list>.`
- Any change that would touch a security invariant, CONTRACTS.md or the replay format is a stop condition: stop and ask.

## Tasks

### Group A

- [x] 1. T4.1 ScriptedDriver
  - Builds the two protocol literals `FINISH_ACTION` and `GO_PREFIX` in `drivers/__init__.py` and `ScriptedDriver` in `drivers/scripted.py`. Acceptance: the driver returns its script in order, repeats the last proposal when enabled, and proposes `finish` when the script is exhausted without repeat or empty.
  - Edge cases: the script and its args dicts are copied on construction; each returned proposal carries a fresh args copy; the observation is ignored; the literals equal the ones in `engine.py`.
  - _Requirements: 4.1_

  - [x] 1.1 Write the ScriptedDriver unit tests first
    - Files: `backend/tests/unit/test_scripted_driver.py` (new).
    - Before writing anything, run `uv --directory backend run pytest -q --collect-only -q` and paste the real output. The baseline is the sum of the per-file counts it prints, not an estimate; if the printed sum differs from 210, the printed sum is the baseline and the difference is reported to the owner.
    - Tests: `test_returns_script_in_order`, `test_repeats_last_when_enabled`, `test_exhausted_without_repeat_proposes_finish`, `test_empty_script_proposes_finish` (both flag values), `test_script_is_copied` (changing the caller's list and args dicts afterwards, or the returned args, does not change later proposals), `test_label_is_scripted`, `test_protocol_literals_match_engine` (`telepermit.drivers.FINISH_ACTION` and `GO_PREFIX` equal the ones in `telepermit.engine`; the test imports the modules with `from telepermit import drivers, engine` and reads `drivers.FINISH_ACTION` inside the test, so the only collection failure is the scripted import).
    - Run `uv --directory backend run pytest -q tests/unit/test_scripted_driver.py`
    - Expected red: `ModuleNotFoundError: No module named 'telepermit.drivers.scripted'` at collection. Do not run ruff in this state.
    - Acceptance check: collection error with exactly that message.
    - _Requirements: 4.1_

  - [x] 1.2 Write property test P4.1 (the scripted driver is deterministic and follows its script)
    - Files: `backend/tests/properties/test_scripted_driver_properties.py` (new).
    - Test function `test_p4_1_deterministic_and_follows_script`. Generators per the design: scripts from `st.lists` of proposals built from `st.text()` actions and `st.dictionaries(st.text(), st.text())` args, `st.booleans()` for `repeat_last`, `st.integers(0, 60)` for the number of calls, arbitrary observations passed in. Two fresh drivers built from the same script return the same proposals; each equals the model value (`script[i]` while in range, then the last proposal forever when `repeat_last` is true and the script is non-empty, otherwise `Proposal("finish", {})`); the original list equals a snapshot taken before. Tag with a comment `Feature: scenario-drivers-replays, Property 1`.
    - Docstring: "Property P4.1: a scripted driver is deterministic and follows its script, then repeats the last proposal or finishes. Validates: Requirements 4.1".
    - Run `uv --directory backend run pytest -q tests/properties/test_scripted_driver_properties.py`
    - Expected red: `ModuleNotFoundError: No module named 'telepermit.drivers.scripted'`. Do not run ruff in this state.
    - Acceptance check: collection error with exactly that message.
    - **Property 1: P4.1 Scripted driver is deterministic and follows its script**
    - **Validates: Requirements 4.1**

  - [x] 1.3 Implement the protocol literals and ScriptedDriver and make the tests pass
    - Files: `backend/src/telepermit/drivers/__init__.py` (add `FINISH_ACTION: Final = "finish"` and `GO_PREFIX: Final = "go:"`; keep the docstring), `backend/src/telepermit/drivers/scripted.py` (new).
    - `scripted.py`: docstring naming CONTRACTS section 7; imports only `__future__`, `collections.abc`, `typing`, `telepermit.drivers` and `telepermit.drivers.base`; `label: Final = "scripted"`; constructor copies the script into a tuple and each args dict; `propose` ignores the observation and returns a proposal with a fresh args copy; exhausted script with `repeat_last` false, and an empty script, give `Proposal(FINISH_ACTION, {})`.
    - Run `uv --directory backend run pytest -q tests/unit/test_scripted_driver.py`
    - Run `uv --directory backend run pytest -q tests/properties/test_scripted_driver_properties.py`
    - Expected: all tests in both files pass.
    - Run `uv --directory backend run ruff check .`
    - Run `uv --directory backend run ruff format --check .`
    - Run `git status --short`, stage the changed and new files of this task by name, commit `feat(drivers): scripted driver (task 1.3)`, print the DONE line.
    - Acceptance check: both files green, ruff clean, commit made.
    - _Requirements: 4.1_

- [x] 2. T4.2 Poisoned-briefing scenario
  - Depends on T4.1. Builds `scenarios/__init__.py` and `scenarios/poisoned_briefing.py` with the constants, `LabeledDriver`, `World`, `ScenarioRun` (including `max_turns`), `build_world` and `run_scenario`. No replay helpers yet and no `GENERATED_BY_CLI`. Acceptance: Run B gives the 20-event golden trace and Run A the 32-event golden trace of CONTRACTS section 8, and the forged variant gives the three-event Run C trace.
  - Edge cases: fresh places, fresh tool state and a fresh clock on every `build_world` call; the Authority never leaves `build_world`; a driver without a `label` raises `TypeError`; a label other than `scripted` or `llm` raises `ValueError`; `forged=True` with `enforce=False` raises `ValueError`; the default driver is the scripted one.
  - _Requirements: 4.3, 4.4, 4.9_

  - [x] 2.1 Write the scenario unit tests first
    - Files: `backend/tests/unit/test_scenario.py` (new).
    - Tests: `test_constants_match_contracts`, `test_build_world_gives_fresh_state` (two worlds do not share page counters, outboxes or clocks), `test_world_exposes_no_key_material` (no private key bytes or hex in the world, identity or places, via the demo seed digest), `test_tool_descriptions_have_no_banned_words` (no `permit`, `allowance`, `teleclick` in any tool description of either place, case-insensitive), `test_forged_signature_is_64_zero_bytes`, `test_forged_requires_enforce` (`ValueError`), `test_run_b_golden`, `test_run_a_golden`, `test_run_c_golden`, `test_run_started_driver_comes_from_label`, `test_driver_without_label_raises` (`TypeError`), `test_invalid_label_raises` (`ValueError`), `test_default_driver_is_scripted`, `test_scenario_run_records_max_turns`.
    - Run `uv --directory backend run pytest -q tests/unit/test_scenario.py`
    - Expected red: `ModuleNotFoundError: No module named 'telepermit.scenarios'` at collection. Do not run ruff in this state.
    - Acceptance check: collection error with exactly that message.
    - _Requirements: 4.3, 4.4, 4.9_

  - [x] 2.2 Write property test P4.3 (Run B and Run A match the golden traces field for field)
    - Files: `backend/tests/properties/test_scenario_properties.py` (new).
    - Test function `test_p4_3_golden_traces`, parametrised over Run B and Run A. The golden facts of CONTRACTS section 8 are written out independently in the test, not read from scenario code. Run B: 20 events with the type sequence; steps and spents; places; decisions; the vault crossing `ADMIT_IMPOSED` with `narrowed_fields ["allowance", "allowed_actions"]`; two `DENIED NOT_IN_PERMIT`; twelve `read_records`; `KILLED ALLOWANCE_EXCEEDED` with limit 40 and observed 41; `RUN_ENDED KILLED`; empty outbox. Run A: 32 events; `UNENFORCED` crossing; spent 22 and 42 at the exports; `HARNESS_CAP` at step 30 with spent 120; two exports in the outbox; no `DENIED` and no `KILLED`. Tag with a comment `Feature: scenario-drivers-replays, Property 3`.
    - Docstring: "Property P4.3: Run B and Run A match the golden traces of CONTRACTS section 8 field for field. Validates: Requirements 4.3".
    - Run `uv --directory backend run pytest -q tests/properties/test_scenario_properties.py`
    - Expected red: `ModuleNotFoundError: No module named 'telepermit.scenarios'`. Do not run ruff in this state.
    - Acceptance check: collection error with exactly that message.
    - **Property 3: P4.3 Run B and Run A match the golden traces field for field**
    - **Validates: Requirements 4.3**

  - [x] 2.3 Write property test P4.5 (enforced runs never spend beyond the allowance) and its witness
    - Files: `backend/tests/properties/test_scenario_properties.py` (append).
    - Test function `test_p4_5_enforced_spend_within_allowance` (Hypothesis): scripts of 1 to 40 proposals drawn from the action pool (`read_document`, `search_archive`, `read_records`, `export_records`, `go:vault`, `go:library`, `finish`, `bogus`) plus adversarial strings, with random string-to-string args dicts; run through `run_scenario(enforce=True, driver=ScriptedDriver(script))`. Assert the final `spent` is at most the allowance of the final permit and `reduce_events` of the log equals the engine state. Tag with a comment `Feature: scenario-drivers-replays, Property 5`.
    - Docstring: "Property P4.5: an enforced run never spends beyond the allowance of its final permit. Validates: Requirements 4.3".
    - Witness test `test_p4_5_witness_unenforced_exceeds_allowance` (existential half, decision k): Run A ends with spent 120 against the allowance 60.
    - Run `uv --directory backend run pytest -q tests/properties/test_scenario_properties.py`
    - Expected red: `ModuleNotFoundError: No module named 'telepermit.scenarios'`. Do not run ruff in this state.
    - Acceptance check: collection error with exactly that message.
    - **Property 5: P4.5 Enforced runs never spend beyond the allowance**
    - **Validates: Requirements 4.3**

  - [x] 2.4 Implement the scenario module and make the tests pass
    - Files: `backend/src/telepermit/scenarios/__init__.py` (new, one-line docstring), `backend/src/telepermit/scenarios/poisoned_briefing.py` (new).
    - Docstring naming CONTRACTS section 8 and stating that the seed is DEMO ONLY. Constants each defined once: `SCENARIO_NAME`, `TASK`, `DEMO_SEED`, `AUTHORITY_NAME`, `AGENT_ID`, `AGENT_CLASS`, `HOME_PERMIT`, `LIBRARY_CEILING`, `VAULT_CEILING`, `SCRIPT`, `TOOL_COSTS` (four tools, built from the constants in `tools.py`). `GO_COST` and `HARNESS_CAP` are imported from `engine.py`. No replay helpers, no replay ids and no `GENERATED_BY_*` constants in this task.
    - `LabeledDriver` protocol, frozen slotted `World` and `ScenarioRun` (with `max_turns`), `build_world(forged=False)` (fresh places from `library_tools()` and `vault_tools()`, identity from `Authority.from_seed(AUTHORITY_NAME, DEMO_SEED).issue(AGENT_ID, AGENT_CLASS, 0.0)`, signature replaced by 64 zero bytes when forged, fresh `TickClock(0.0)`, the Authority stays local), `run_scenario(*, enforce, driver=None, forged=False, max_turns=HARNESS_CAP)` (default `ScriptedDriver(SCRIPT)`, label read from `driver.label`, `TypeError` for a missing label, `ValueError` for a bad label and for forged with enforcement off, Engine built with `scenario`, `driver` and `task` keywords).
    - Run `uv --directory backend run pytest -q tests/unit/test_scenario.py`
    - Run `uv --directory backend run pytest -q tests/properties/test_scenario_properties.py`
    - Expected: all tests in both files pass.
    - Run `uv --directory backend run ruff check .`
    - Run `uv --directory backend run ruff format --check .`
    - Run `git status --short`, stage the new files by name, commit `feat(scenario): poisoned briefing scenario and golden runs (task 2.4)`, print the DONE line.
    - Acceptance check: both files green including the golden traces and P4.5, ruff clean, commit made.
    - _Requirements: 4.3, 4.4, 4.9_

- [x] 3. T4.3 Observation text safety
  - Depends on T4.2. Tests only. This task is NOT expected to be red first: the behaviour was built in Spec 3 (the Engine run loop builds the Observation) and the scenario exists from task 2, so the first run is green. The scanner self-test is what shows that the scan can fail.
  - Acceptance: across Run A and Run B no observation text contains a forbidden word, the identity signature hex or the demo private-key hex, and the observation has exactly five fields.
  - _Requirements: 4.2_

  - [x] 3.1 Write and run the observation safety tests
    - Files: `backend/tests/properties/test_scenario_properties.py` (append; keep the earlier tests).
    - `test_p4_2_observations_hide_limits_and_keys`, parametrised over Run A and Run B, using an inline recording wrapper driver with label `scripted` that delegates to `ScriptedDriver(SCRIPT)` and records every observation. For each: exactly the five fields `task`, `turn`, `place`, `tools`, `last_result`; each tool entry has exactly the keys `name`, `description`, `args`; the JSON text of the observation contains none of `permit`, `allowance`, `teleclick` (compared in lower case), the identity signature hex, or `sha256(DEMO_SEED).digest().hex()`. Docstring: "Property P4.2: the agent never sees limits or keys in Run A and Run B. Validates: Requirements 4.2".
    - `test_observation_has_exactly_five_fields` (field names of the `Observation` type and of every recorded observation).
    - `test_forbidden_word_scan_detects_leaks` (scanner self-test): the inline scanner flags strings that contain each forbidden word in any case, the signature hex and the key hex, and passes clean strings.
    - No implementation is written in this task.
    - Run `uv --directory backend run pytest -q tests/properties/test_scenario_properties.py`
    - Expected: all tests in the file pass on the first run. A red result is a real defect: stop, paste the output and the diagnosis, and do not weaken a test.
    - Run `uv --directory backend run ruff check .`
    - Run `uv --directory backend run ruff format --check .`
    - Run `git status --short`, stage the file by name, commit `test(scenario): observation text safety (task 3.1)`, print the DONE line.
    - Acceptance check: the file is green including the self-test, ruff clean, commit made.
    - **Property 2: P4.2 The agent never sees limits or keys in Run A and Run B**
    - **Validates: Requirements 4.2**

- [x] 4. T4.4 LLM driver
  - Depends on T4.1. Builds `drivers/llm.py` (`LLMDriver`, `build_client`, `LLMUnavailableError`, constants) and the inline network guard (decision h). The mapping follows the documented Anthropic Messages API and is NOT exercised against the live service; tests use an inline fake client.
  - Acceptance: requests have the designed shape, responses map to proposals, and `anthropic` is imported only inside `build_client`.
  - Edge cases: several `tool_use` blocks (the first wins); a response with no `tool_use` finishes; an empty response is not appended to the history; request messages are snapshots; a blank model raises `ValueError`; the system prompt has no banned words.
  - _Requirements: 4.5, 4.6_

  - [x] 4.1 Write the LLM driver unit tests first, with the inline network guard
    - Files: `backend/tests/unit/test_llm_driver.py` (new).
    - The guard (decision h), defined inline: an autouse fixture `network_calls` that replaces `socket.socket.connect`, `socket.socket.connect_ex`, `socket.create_connection` and `socket.getaddrinfo` with functions that raise a local `NetworkBlockedError` and append the attempt to a list the fixture yields. Its TEARDOWN FAILS the test if the list is not empty.
    - The proving test `test_network_guard_blocks_connections` triggers a connect, a name lookup and `create_connection` on purpose, asserts each raised `NetworkBlockedError` and was recorded, and CLEARS the list in a `finally` block (`try: ...` the triggers and assertions, `finally: network_calls.clear()`) so the teardown check passes on purpose and does not fail the file, even when one of the proving test's own assertions fails (the report then shows only that real failure).
    - The fake client is an inline class that records deep copies of the request keyword arguments.
    - Tests: `test_request_shape`, `test_go_places_collapse_to_one_tool`, `test_no_go_tool_with_single_place`, `test_first_message_has_task_and_place`, `test_tool_results_come_first`, `test_extra_tool_use_ids_get_fixed_text`, `test_go_response_maps_to_prefixed_action`, `test_finish_response`, `test_unknown_tool_passes_through`, `test_text_only_response_finishes`, `test_empty_content_finishes`, `test_request_messages_are_snapshots`, `test_build_client_without_package` (`monkeypatch.setitem(sys.modules, "anthropic", None)`), `test_system_prompt_has_no_banned_words`, `test_no_top_level_anthropic_import` (parse `llm.py` with `ast`), `test_blank_model_rejected`, `test_label_is_llm`, `test_network_guard_blocks_connections`.
    - Run `uv --directory backend run pytest -q tests/unit/test_llm_driver.py`
    - Expected red: `ModuleNotFoundError: No module named 'telepermit.drivers.llm'` at collection. Do not run ruff in this state.
    - Acceptance check: collection error with exactly that message.
    - _Requirements: 4.5, 4.6_

  - [x] 4.2 Write property test P4.6 (the LLM driver maps responses to proposals and never touches the engine)
    - Files: `backend/tests/properties/test_llm_driver_properties.py` (new). No guard fixture in this file (Hypothesis rejects function-scoped fixtures); the inline fake client makes no socket calls.
    - Test function `test_p4_6_mapping_history_and_no_engine_calls`. Observations from a small place pool with random string arg names, `go:<place>` entries for the other places, `finish` and any `last_result`; fake responses drawn from: a `tool_use` for a place tool with random string args; a `go` tool_use with a place; `finish`; text-only; empty content; several `tool_use` blocks; an unknown tool name; sequences of 1 to 6 turns. Assert the mapped proposal (first `tool_use` wins, `go` gives `go:<place>`, unknown names pass through, args coerced to strings, `finish` when there is no `tool_use`); the request has exactly one `go` tool whose enum equals the other places (none when there are none), plus place tools and `finish`, the fixed `tool_choice`, the model and `max_tokens`; no sent text contains `permit`, `allowance`, `teleclick` or the demo key hex; roles alternate and every later user message starts with a `tool_result` for every `tool_use` id of the previous assistant message. `Engine.step`, `Engine.run` and `Place.execute` are monkeypatched to fail the test if called. Tag with a comment `Feature: scenario-drivers-replays, Property 6`.
    - Docstring: "Property P4.6: the LLM driver maps responses to proposals, keeps a well-formed history and never touches the engine. Validates: Requirements 4.5".
    - Run `uv --directory backend run pytest -q tests/properties/test_llm_driver_properties.py`
    - Expected red: `ModuleNotFoundError: No module named 'telepermit.drivers.llm'`. Do not run ruff in this state.
    - Acceptance check: collection error with exactly that message.
    - **Property 6: P4.6 The LLM driver maps responses to proposals and never touches the engine**
    - **Validates: Requirements 4.5**

  - [x] 4.3 Implement drivers/llm.py and make the tests pass
    - Files: `backend/src/telepermit/drivers/llm.py` (new).
    - Docstring naming CONTRACTS section 7. Imports only `__future__`, `copy`, `json` if needed, `collections.abc`, `typing`, `telepermit.drivers` and `telepermit.drivers.base`; never `engine`, `identity`, `place` or `tools`. Constants `ENV_MODEL`, `ENV_API_KEY`, `MAX_TOKENS` (1024), `GO_TOOL` (`"go"`) and `SYSTEM_PROMPT` (neutral, none of the banned words). `LLMUnavailableError`. `build_client(api_key)` does `import anthropic` INSIDE the function, turns `ImportError` into `LLMUnavailableError("the llm extra is not installed: run uv sync --extra llm")`. `LLMDriver(client, model, *, max_tokens=MAX_TOKENS)` with `label: Final = "llm"`, `ValueError` for a blank model, request and response mapping and history exactly as in design.md, blocks read with `getattr`, a deep copy of the history sent on each request.
    - Run `uv --directory backend run pytest -q tests/unit/test_llm_driver.py`
    - Run `uv --directory backend run pytest -q tests/properties/test_llm_driver_properties.py`
    - Expected: all tests in both files pass.
    - Run `uv --directory backend run ruff check .`
    - Run `uv --directory backend run ruff format --check .`
    - Run `git status --short`, stage the new files by name, commit `feat(drivers): llm driver behind an injected client (task 4.3)`, print the DONE line.
    - Acceptance check: both files green, ruff clean, commit made.
    - _Requirements: 4.5, 4.6_

- [x] 5. T4.5 CLI core
  - Depends on T4.2 and T4.4. Builds `cli.py` with `main`, `format_timeline`, exit codes 0, 1 and 2, the environment check before any import of `anthropic`, and sanitised ASCII one-line summaries. The `--out` option is NOT added in this task (it is gated, task 11): the parser has no `--out`.
  - Acceptance: `--enforce on` ends `status: KILLED` with `outbox: 0`; `--enforce off` ends `status: HARNESS_CAP` with `outbox: 2`; a missing `AGENT_MODEL` or `ANTHROPIC_API_KEY` names the variable only and builds no client.
  - Edge cases: a blank variable counts as missing; the scripted driver never reads the environment; a scripted run exception is not caught; an llm abort prints the exception type name only and never the API key; the model name comes only from `AGENT_MODEL`.
  - _Requirements: 4.6, 4.7, 4.9_

  - [x] 5.1 Write the CLI unit tests first, with their own inline network guard
    - Files: `backend/tests/unit/test_cli.py` (new).
    - The inline autouse guard `network_calls` and the proving test `test_network_guard_blocks_connections` are defined exactly as in sub-task 4.1 (teardown fails the test if the list is not empty; the proving test clears the list in a `finally` block, as in sub-task 4.1).
    - Tests call `main()` with injected `env`, `out` and `err` (no subprocess). Names: `test_enforce_on_ends_killed`, `test_enforce_off_ends_harness_cap`, `test_timeline_header_and_columns`, `test_summary_is_one_line` (hostile text with newlines and non-ASCII), `test_summary_truncated` (at most 72 characters ending `...`), `test_usage_errors_return_2`, `test_scripted_run_exception_is_not_caught`, `test_llm_missing_env_names_only`, `test_llm_blank_env_counts_as_missing`, `test_llm_missing_env_builds_no_client` (monkeypatch `telepermit.cli.build_client` to fail the test if called), `test_llm_extra_missing_returns_1`, `test_model_comes_from_env_only`, `test_scripted_driver_ignores_env`, `test_llm_run_with_fake_client_is_labelled_llm` (a fake client whose first response is a `finish` tool_use; the timeline shows driver `llm`), `test_llm_abort_prints_type_only` (a fake client that raises an error whose message contains the API key value; the key must not appear in out or err), `test_output_has_no_key_material` (private-key hex of the demo seed and the API key value), `test_network_guard_blocks_connections`.
    - Run `uv --directory backend run pytest -q tests/unit/test_cli.py`
    - Expected red: `ModuleNotFoundError: No module named 'telepermit.cli'` at collection. Do not run ruff in this state.
    - Acceptance check: collection error with exactly that message.
    - _Requirements: 4.6, 4.7, 4.9_

  - [x] 5.2 Implement cli.py and make the tests pass
    - Files: `backend/src/telepermit/cli.py` (new).
    - Docstring naming CONTRACTS section 10. `main(argv=None, *, env=None, out=None, err=None) -> int` and `format_timeline(events) -> list[str]`, argparse with `prog="telepermit"`, subcommand `run`, positional scenario with choices `["poisoned_briefing"]`, `--enforce` (required, `on|off`), `--driver` (`scripted|llm`, default `scripted`) and NO `--out`. A `SystemExit` from argparse is turned into the return value. Exit codes: 0 for a final status, 1 for configuration or runtime problems, 2 for usage errors. For `--driver llm`: read `AGENT_MODEL` and `ANTHROPIC_API_KEY` from `env`, list missing or blank ones by name only, return 1 before any import of `anthropic`; then `build_client` (imported by name so tests can replace `telepermit.cli.build_client`), then `LLMDriver`. A scripted run exception is not caught; any `Exception` from an llm run gives `error: run aborted: <ExceptionType> (details withheld; see docs)` and return 1. Timeline header and line formats and per-type summaries as in design.md, each summary sanitised to one ASCII line and truncated to 72 characters with `...`. After the timeline print `status: <STATUS>` and `outbox: <n>`. `print` is allowed here only.
    - Run `uv --directory backend run pytest -q tests/unit/test_cli.py`
    - Expected: all tests in the file pass.
    - Run `uv --directory backend run ruff check .`
    - Run `uv --directory backend run ruff format --check .`
    - Human acceptance command: `uv --directory backend run python -m telepermit.cli run poisoned_briefing --enforce on`. Expected last lines `status: KILLED` and `outbox: 0`.
    - Human acceptance command: `uv --directory backend run python -m telepermit.cli run poisoned_briefing --enforce off`. Expected last lines `status: HARNESS_CAP` and `outbox: 2`.
    - Run `git status --short`, stage the new files by name, commit `feat(cli): run command with timeline output (task 5.2)`, print the DONE line.
    - Acceptance check: `test_cli.py` green, both acceptance commands end as stated, ruff clean, commit made.
    - _Requirements: 4.6, 4.7, 4.9_

- [ ] 6. T4.6 part 1: replay format
  - Depends on T4.2. Adds to `audit.py` (additions only) `SCHEMA_VERSION`, `ReplayMeta`, `IndexEntry`, `replay_document`, `index_document`, `dumps_json` and `write_json`, and adds to the scenario module `GENERATED_BY_RECORDER`, the replay ids and titles, `replay_identity` and `replay_meta`. `GENERATED_BY_CLI` is NOT added here (Group B). Acceptance: replay documents have the CONTRACTS section 9 keys, JSON output is sorted, indented, ASCII, LF only and ends with exactly one newline, and a hostile tool result stays on one JSONL line per event.
  - Edge cases: `SCHEMA_VERSION` is defined once; `write_json` never writes CR on Windows; the llm label gives the `-llm` id suffix and a title ending `(live LLM)`.
  - _Requirements: 4.8, 4.9_

  - [ ] 6.1 Write the replay format and replay helper tests first
    - Files: `backend/tests/unit/test_replay_format.py` (new), `backend/tests/unit/test_scenario_replay.py` (new).
    - `test_replay_format.py`: `test_schema_version_is_one`, `test_dumps_json_is_sorted_indented_ascii`, `test_write_json_uses_lf` (read the bytes: no `b"\r"`, ends with exactly one `b"\n"`), `test_replay_json_round_trip` (`json.loads(dumps_json(doc)) == doc`), `test_replay_document_keys`, `test_index_document_keys`, `test_hostile_tool_result_stays_one_line_per_event` (an inline tool whose result has newlines, carriage returns, quotes, backslashes and the text `{"type":"KILLED"}`, run through a small Engine; `to_jsonl` gives exactly one line per event and each line parses back to the event).
    - `test_scenario_replay.py`: `test_replay_identity_ids_and_titles`, `test_replay_meta_fields` (exactly the CONTRACTS section 9 meta keys; `home_permit`, `ceilings`, `tool_costs` 1/5/3/20, `document_text` equals `BRIEFING_Q3_TEXT`, `harness_cap` equals the run's `max_turns`, `generated_by` passed through), `test_title_ends_with_label`, `test_llm_label_gives_suffix_and_title`.
    - Run `uv --directory backend run pytest -q tests/unit/test_replay_format.py`
    - Run `uv --directory backend run pytest -q tests/unit/test_scenario_replay.py`
    - Expected red: a collection `ImportError: cannot import name '<name>' from '<module>'` in each of the two NEW files, where `<name>` is the FIRST new name in that file's import list (Python reports only the first missing name): `'SCHEMA_VERSION' from 'telepermit.audit'` for the first file when the test imports it (ruff sorts constants first), and for the second file the first new name of its import from `telepermit.scenarios.poisoned_briefing` (`GENERATED_BY_RECORDER` if the test imports it, otherwise `replay_identity`). These are whole-file collection errors in the two NEW files only; every existing file stays green. Do not run ruff in this state.
    - Acceptance check: exactly those two collection errors.
    - _Requirements: 4.8, 4.9_

  - [ ] 6.2 Implement the audit additions and the replay helpers and make the tests pass
    - Files: `backend/src/telepermit/audit.py` (additions only), `backend/src/telepermit/scenarios/poisoned_briefing.py`.
    - `audit.py`: `SCHEMA_VERSION: Final = 1`, `ReplayMeta` and `IndexEntry` TypedDicts, `replay_document`, `index_document`, `dumps_json` (`json.dumps(document, sort_keys=True, indent=2) + "\n"`, default `ensure_ascii`), `write_json` (`open(path, "w", encoding="utf-8", newline="\n")`). `audit.py` does not import `engine`. Keep two blank lines between top-level definitions.
    - Scenario: `GENERATED_BY_RECORDER: Final = "scripts/record_replays.py"`, the three replay ids and titles of decision (f), `replay_identity(run)` returning `(id, title)` (`-llm` suffix and `(live LLM)` for the llm label, `(scripted)` otherwise), `replay_meta(run, generated_by)` building the meta from the constants and the run. No `GENERATED_BY_CLI`.
    - Run `uv --directory backend run pytest -q tests/unit/test_replay_format.py`
    - Run `uv --directory backend run pytest -q tests/unit/test_scenario_replay.py`
    - Run `uv --directory backend run pytest -q tests/unit/test_audit.py`
    - Expected: all tests in the three files pass.
    - Run `uv --directory backend run ruff check .`
    - Run `uv --directory backend run ruff format --check .`
    - Run `git status --short`, stage the changed and new files by name, commit `feat(audit): replay format and replay helpers (task 6.2)`, print the DONE line.
    - Acceptance check: the three files green, ruff clean, commit made.
    - _Requirements: 4.8, 4.9_

- [ ] 7. T4.6 part 2: recorder and the two Milestone M1 replays
  - Depends on task 6. Builds `scripts/record_replays.py` and `tests/test_replays.py`, and commits the generated files `index.json`, `poisoned-briefing-enforced.json` and `poisoned-briefing-unenforced.json`. In this task the recorder writes ONLY the enforced (Run B) and unenforced (Run A) replays and then `index.json` LAST; the forged replay is task 8. Milestone M1 is recorded over THESE two replays.
  - Acceptance: recording twice gives byte-identical files and `git status --short -- frontend/public/replays` prints nothing after the second run.
  - Edge cases: no CR byte, exactly one trailing LF, pure ASCII; no key hex in any file; the labels in the files and the index equal the driver actually used; `generated_by` is the recorder literal.
  - _Requirements: 4.8, 4.9_

  - [ ] 7.1 Write the replay file tests first
    - Files: `backend/tests/test_replays.py` (new).
    - A helper inside the test file loads `scripts/record_replays.py` with `importlib.util.spec_from_file_location` AT CALL TIME (inside each test), so the red state is a per-test `FileNotFoundError` and not a collection error. Paths come from the test file location.
    - Tests: `test_m1_replays_present` (reads `index.json` and the two M1 files with `read_bytes()`), `test_committed_files_match_fresh_recording`, `test_p4_4_recording_twice_is_byte_identical` (two temporary directories; the same file names in the same order; identical bytes; no CR byte; ends with exactly one LF; pure ASCII; docstring "Property P4.4: recording twice gives byte-identical files. Validates: Requirements 4.8"), `test_every_replay_schema_and_contiguous_seq` (loops over the entries of the committed index INSIDE the test, so a missing index fails the test and not the collection), `test_reduce_events_equals_last_snapshot`, `test_golden_facts_run_b` and `test_golden_facts_run_a` (written independently in the test), `test_index_matches_files` (no exact entry count: the ids start with the two M1 ids in order and every entry has a file that exists), `test_labels_match_driver_in_files_and_index`, `test_generated_by_is_recorder_literal`, `test_no_key_hex_in_any_file` (`sha256(DEMO_SEED).digest().hex()`; it reads `index.json` first, scans the index and every file the index lists, and asserts that the two M1 files are among them, so it can never pass on an empty folder).
    - Run `uv --directory backend run pytest -q tests/test_replays.py`
    - Every test in this file begins by loading the recorder script or reading a committed file, so none can pass on an empty replay folder. Expected red: `FileNotFoundError: [Errno 2] No such file or directory: '<repo>\scripts\record_replays.py'` for the tests that load the script, and `FileNotFoundError: [Errno 2] No such file or directory: '<repo>\frontend\public\replays\index.json'` for the tests that read replay files (the path prefix depends on the machine). Do not run ruff in this state.
    - Acceptance check: every test fails with FileNotFoundError and none fails at collection.
    - **Property 4: P4.4 Recording twice gives byte-identical files**
    - **Validates: Requirements 4.8**
    - _Requirements: 4.8, 4.9_

  - [ ] 7.2 Implement the recorder
    - Files: `scripts/record_replays.py` (new).
    - Docstring naming CONTRACTS section 10. `REPO_ROOT = Path(__file__).resolve().parents[1]`, `REPLAY_DIR = REPO_ROOT / "frontend" / "public" / "replays"`. `record_all(output_dir) -> list[Path]` runs the scripted recordings enforced (Run B) then unenforced (Run A), writes `<id>.json` for each and `index.json` LAST, creates the directory if missing, deletes nothing, and returns the paths in that order. Metas use `generated_by = GENERATED_BY_RECORDER`; index entries are `{id, title, file, driver, enforce}` taken from the metas. `main(argv=None) -> int` with an optional `--output-dir` (default `REPLAY_DIR`) prints one `wrote <path>` line per file and returns 0. Files are written with `write_json` (UTF-8, LF). No network, clock or randomness.
    - Acceptance check: the module imports without side effects; the next sub-task generates the files.
    - _Requirements: 4.8, 4.9_

  - [ ] 7.3 Generate the replays and make the tests pass
    - Files: `frontend/public/replays/index.json`, `frontend/public/replays/poisoned-briefing-enforced.json`, `frontend/public/replays/poisoned-briefing-unenforced.json` (generated).
    - Run `uv --directory backend run python ../scripts/record_replays.py`
    - Expected: three `wrote ...` lines, the index last.
    - Run `uv --directory backend run pytest -q tests/test_replays.py`
    - Expected: all tests in the file pass.
    - Run `uv --directory backend run ruff check --config pyproject.toml . ../scripts`
    - Run `uv --directory backend run ruff format --check --config pyproject.toml . ../scripts`
    - Acceptance check: the replay tests are green and ruff is clean with the scripts form.
    - _Requirements: 4.8, 4.9_

  - [ ] 7.4 Commit the recorder, its tests and the generated data files
    - Run `git status --short`
    - Run `git add scripts/record_replays.py backend/tests/test_replays.py`
    - Run `git add frontend/public/replays/index.json frontend/public/replays/poisoned-briefing-enforced.json frontend/public/replays/poisoned-briefing-unenforced.json`
    - Run `git commit -m "feat(replays): recorder and the two M1 replays (task 7.4)"`
    - Acceptance check: the commit contains exactly those five files.
    - _Requirements: 4.8_

  - [ ] 7.5 Confirm that recording is deterministic
    - Run `uv --directory backend run python ../scripts/record_replays.py`
    - Run `git status --short -- frontend/public/replays`
    - Expected: the second command prints nothing. Print the DONE line for task 7. State in the report that Milestone M1 is recorded over the enforced and unenforced replays.
    - Acceptance check: empty git status for the replay folder.
    - _Requirements: 4.8_

- [ ] 8. T4.7 Forged-identity replay
  - Depends on task 7. Optional for acceptance and NOT counted toward Milestone M1, but still a required task of this spec. Its tests carry `forged` in their names so `uv --directory backend run pytest -q tests/test_replays.py -k forged` is its own check. The recorder gains a third recording; the order stays enforced, unenforced, forged, with the index last.
  - Acceptance: the forged replay has exactly the three Run C events and the index lists it after the two M1 replays.
  - _Requirements: 4.4, 4.8, 4.9_

  - [ ] 8.1 Write the forged replay tests first
    - Files: `backend/tests/test_replays.py` (append; keep earlier tests).
    - Tests: `test_forged_replay_golden` (3 events `RUN_STARTED`, `BORDER_CHECK` at library with decision `REFUSE` and reason `BAD_SIGNATURE`, `RUN_ENDED` with status `REFUSED`; `signature_hex` is 128 zeros; meta `enforce` true, `driver` scripted, id `forged-identity-refused`), `test_forged_replay_in_index_after_the_m1_replays` (reads the committed `index.json` and asserts `[entry["id"] for entry in index["replays"]] == ["poisoned-briefing-enforced", "poisoned-briefing-unenforced", "forged-identity-refused"]`), `test_forged_replay_is_written_before_the_index` (asserts `[path.name for path in record_all(tmp_path)] == ["poisoned-briefing-enforced.json", "poisoned-briefing-unenforced.json", "forged-identity-refused.json", "index.json"]`), `test_forged_replay_labels`.
    - Run `uv --directory backend run pytest -q tests/test_replays.py -k forged`
    - Expected red, one reason per test: `test_forged_replay_golden` and `test_forged_replay_labels` fail with `FileNotFoundError: [Errno 2] No such file or directory: '<repo>\frontend\public\replays\forged-identity-refused.json'`; `test_forged_replay_in_index_after_the_m1_replays` fails with `AssertionError: assert ['poisoned-briefing-enforced', 'poisoned-briefing-unenforced'] == ['poisoned-briefing-enforced', 'poisoned-briefing-unenforced', 'forged-identity-refused']`; `test_forged_replay_is_written_before_the_index` fails with `AssertionError: assert ['poisoned-briefing-enforced.json', 'poisoned-briefing-unenforced.json', 'index.json'] == [...]` (pytest may abbreviate the right-hand list on that first line; the left-hand list is exact). Do not run ruff in this state.
    - Acceptance check: the four forged tests fail for those two reasons and the other tests stay green.
    - _Requirements: 4.4, 4.8, 4.9_

  - [ ] 8.2 Extend the recorder with the third recording
    - Files: `scripts/record_replays.py`.
    - Add the forged recording (`run_scenario(enforce=True, forged=True)`) after the two M1 recordings and before `index.json`, with its index entry after the two M1 entries.
    - Acceptance check: the module still imports; the next sub-task generates the file.
    - _Requirements: 4.4, 4.8_

  - [ ] 8.3 Generate, verify and commit the forged replay
    - Files: `frontend/public/replays/forged-identity-refused.json` (generated), `frontend/public/replays/index.json` (changed).
    - Run `uv --directory backend run python ../scripts/record_replays.py`
    - Run `uv --directory backend run pytest -q tests/test_replays.py -k forged`
    - Run `uv --directory backend run pytest -q tests/test_replays.py`
    - Expected: all selected tests pass in both runs.
    - Run `uv --directory backend run ruff check --config pyproject.toml . ../scripts`
    - Run `uv --directory backend run ruff format --check --config pyproject.toml . ../scripts`
    - Run `git status --short`
    - Run `git add scripts/record_replays.py backend/tests/test_replays.py frontend/public/replays/forged-identity-refused.json frontend/public/replays/index.json`
    - Run `git commit -m "feat(replays): forged identity replay (task 8.3)"`
    - Run `uv --directory backend run python ../scripts/record_replays.py`
    - Run `git status --short -- frontend/public/replays`
    - Expected: the last command prints nothing. Print the DONE line.
    - Acceptance check: forged tests and the full replay file green, ruff clean, commit made, clean replay folder after re-recording.
    - _Requirements: 4.4, 4.8, 4.9_

- [ ] 9. Group A final checkpoint
  - Run `uv --directory backend run pytest -q`
  - Report the final total as a difference from the count recorded before sub-task 1.1 (baseline expected 210), all passing.
  - Run `uv --directory backend run ruff check --config pyproject.toml . ../scripts`
  - Run `uv --directory backend run ruff format --check --config pyproject.toml . ../scripts`
  - Inspection: run `git grep -n "\.execute(" -- backend/src`. Expected hits only in `engine.py`; any other hit (even in a docstring) is reported.
  - Inspection: run `git grep -n -E "^\s*(from|import) " -- backend/src/telepermit/drivers`. Expected: only `__future__`, `dataclasses`, `typing`, `collections.abc`, `copy`, `json` and `telepermit.drivers...` modules; no `engine`, `identity`, `place` or `tools`; `anthropic` appears only inside a function.
  - Inspection: run `git grep -n "GENERATED_BY_CLI" -- backend`. Expected: prints nothing (the gate has not been crossed).
  - Run the CLI commands of task 5 and confirm `status: KILLED` with `outbox: 0` and `status: HARNESS_CAP` with `outbox: 2`.
  - Run the recorder twice and confirm `git status --short -- frontend/public/replays` prints nothing; run the optional `uv --directory backend run pytest -q tests/test_replays.py -k forged`.
  - Inspection: run `git diff --stat main -- backend/pyproject.toml backend/uv.lock`. Expected: empty (no dependency change).
  - Update docs/PROGRESS.md: spec folder `.kiro/specs/scenario-drivers-replays`, branch `spec/04-scenario-drivers-replays`, Group A done, Group B gated by the owner's CONTRACTS amendment; Milestone M1 is stated over the enforced and unenforced replays.
  - Print the DONE line with the real counts. Ensure all tests pass, ask the user if questions arise.
  - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 4.8, 4.9_

### Group B

**Do not start any Group B task until the owner confirms in chat that task 10 is done.**

Group B implements the CLI `--out` option of approved decision (b). It needs the CONTRACTS amendment first, because the value `"telepermit.cli"` for `generated_by` is not yet in CONTRACTS.

- [ ] 10. Owner applies the CONTRACTS amendment
  - Owner-only task. The agent does not edit docs/CONTRACTS.md and does not stage it.
  - Test command: none (owner action), then read-only confirmation.
  - _Requirements: 4.7, 4.8_

  - [ ] 10.1 Owner edits docs/CONTRACTS.md and confirms in chat
    - Files: `docs/CONTRACTS.md` (owner edit).
    - Section 9, after the sentence that lists the replay ids, add: "`generated_by` is `"scripts/record_replays.py"` for files written by the recorder and `"telepermit.cli"` for a file written by the CLI `--out` option."
    - Section 10, in the CLI bullet, after "`--out` writes a replay JSON" add "(section 9, with `generated_by` `"telepermit.cli"`)".
    - Acceptance check: the owner confirms in chat that both edits are applied.
    - _Requirements: 4.7, 4.8_

  - [ ] 10.2 Agent confirms the amendment with read-only searches
    - Files: none changed.
    - Run `git grep -n "telepermit.cli" -- docs/CONTRACTS.md`
    - Run `git grep -n "generated_by" -- docs/CONTRACTS.md`
    - Expected: both wordings are present, one in section 9 and one in section 10. If either is missing, stop and tell the owner; do not edit CONTRACTS.md.
    - Acceptance check: both searches show the stated wordings in sections 9 and 10.
    - _Requirements: 4.7, 4.8_

- [ ] 11. T4.5 continued: CLI --out
  - Blocked until the owner confirms task 10.
  - Adds the `--out` option to `cli.py` and `GENERATED_BY_CLI` to the scenario module. This is the ONLY task in which the value `"telepermit.cli"` is written as `generated_by`. Acceptance: `--out` writes a replay that equals the recorded replay apart from `generated_by`.
  - Edge cases: an unwritable path gives exit 1; the CLI never writes `index.json`; an llm run is labelled `llm` with the `-llm` id suffix.
  - _Requirements: 4.7, 4.9_

  - [ ] 11.1 Write the --out tests first
    - Blocked until the owner confirms task 10.
    - Files: `backend/tests/unit/test_cli.py` (append; keep the guard and earlier tests).
    - Tests: `test_out_writes_replay`, `test_out_replay_generated_by_cli`, `test_out_unwritable_returns_1`, `test_cli_does_not_write_index`, `test_llm_out_replay_is_labelled_llm` (id with the `-llm` suffix, title ending `(live LLM)`, meta `driver` llm, fake client), `test_out_replay_matches_recorder_apart_from_generated_by` (scripted, enforce on and off: the CLI file equals the recorded replay with only `generated_by` different), `test_out_replay_has_schema_and_contiguous_seq`. Each test asserts the return code of `main(...)` FIRST (0 in every test except `test_out_unwritable_returns_1`, which expects 1), before any file check.
    - Run `uv --directory backend run pytest -q tests/unit/test_cli.py`
    - Expected red: the parser rejects `--out` with exit code 2, so the first assertion of each new test fails: `AssertionError: assert 2 == 0` for the six tests that expect exit code 0 (`test_out_writes_replay`, `test_out_replay_generated_by_cli`, `test_cli_does_not_write_index`, `test_llm_out_replay_is_labelled_llm`, `test_out_replay_matches_recorder_apart_from_generated_by`, `test_out_replay_has_schema_and_contiguous_seq`) and `AssertionError: assert 2 == 1` for `test_out_unwritable_returns_1` (pytest adds a `+ where 2 = main(...)` line). Earlier tests stay green. Do not run ruff in this state.
    - Acceptance check: only the new tests fail, each with AssertionError.
    - _Requirements: 4.7, 4.9_

  - [ ] 11.2 Implement --out and make the tests pass
    - Blocked until the owner confirms task 10.
    - Files: `backend/src/telepermit/cli.py`, `backend/src/telepermit/scenarios/poisoned_briefing.py`.
    - Scenario: add `GENERATED_BY_CLI: Final = "telepermit.cli"`. CLI: optional `--out PATH`; after the timeline, build `replay_document(replay_meta(run, GENERATED_BY_CLI), run.result.events)`, write it with `write_json`, print `replay written: <path>`; an `OSError` gives an `error:` line on stderr and exit 1. The CLI never writes `index.json`.
    - Run `uv --directory backend run pytest -q tests/unit/test_cli.py`
    - Expected: all tests in the file pass.
    - Run `uv --directory backend run ruff check --config pyproject.toml . ../scripts`
    - Run `uv --directory backend run ruff format --check --config pyproject.toml . ../scripts`
    - Run `git status --short`, stage the changed files by name, commit `feat(cli): out option writes a replay (task 11.2)`, print the DONE line.
    - Acceptance check: `test_cli.py` green, ruff clean, commit made.
    - _Requirements: 4.7, 4.9_

- [ ] 12. Group B final checkpoint
  - Blocked until the owner confirms task 10.
  - Run all the checks of task 9 again, with this difference: `git grep -n "GENERATED_BY_CLI" -- backend` now finds only the constant and its uses.
  - Run `uv --directory backend run pytest -q` and report the total as a difference from the recorded baseline, all passing.
  - Run `uv --directory backend run ruff check --config pyproject.toml . ../scripts` and `uv --directory backend run ruff format --check --config pyproject.toml . ../scripts` (one per call).
  - Run all the exit-criteria commands: both CLI commands of task 5, the recorder twice with a clean `git status --short -- frontend/public/replays`, and the optional `-k forged` check.
  - Update docs/PROGRESS.md: Spec 4 done, branch ready for `MERGE`, tag `spec-04-done` after the merge, and the human tags `m1-core`.
  - Print the DONE line with the real counts. Ensure all tests pass, ask the user if questions arise.
  - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 4.8, 4.9_

## Notes

- No task is optional. Property tests P4.1 to P4.6 are required, each in its own sub-task.
- Group B is gated: nothing in it starts until the owner confirms in chat that task 10 is done. Group A writes no `generated_by` value other than the recorder literal.
- Deviation from the design: the design lists `test_title_ends_with_label` in `test_scenario.py`. The tasks put the replay-helper tests (`replay_identity`, `replay_meta`, the title and label tests) in the new file `test_scenario_replay.py`, so that their red state in task 6 does not break the already green `test_scenario.py`.
- Task 3 is tests only and is not expected to be red first; the scanner self-test shows that the scan can fail.
- Milestone M1 is recorded over the `poisoned-briefing-enforced` and `poisoned-briefing-unenforced` replays (task 7). The forged-identity replay (task 8) is not counted toward M1 and has its own check: `uv --directory backend run pytest -q tests/test_replays.py -k forged`.
- The LLM request and response mapping is not exercised against the live service in this spec. Every test uses an inline fake client and no network. The first live run is a manual owner step.
- Exit criteria commands: `uv --directory backend run pytest -q`, the two ruff commands of the scripts form, `uv --directory backend run python -m telepermit.cli run poisoned_briefing --enforce on` (ends `status: KILLED`), the same with `--enforce off` (ends `status: HARNESS_CAP`), and `uv --directory backend run python ../scripts/record_replays.py` run twice with an empty `git status --short -- frontend/public/replays`.
- Property tests carry a docstring `Property P<n>.<m>: <statement>. Validates: Requirements 4.x`.

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["1.2"] },
    { "id": 2, "tasks": ["1.3"] },
    { "id": 3, "tasks": ["2.1"] },
    { "id": 4, "tasks": ["2.2"] },
    { "id": 5, "tasks": ["2.3"] },
    { "id": 6, "tasks": ["2.4"] },
    { "id": 7, "tasks": ["3.1"] },
    { "id": 8, "tasks": ["4.1"] },
    { "id": 9, "tasks": ["4.2"] },
    { "id": 10, "tasks": ["4.3"] },
    { "id": 11, "tasks": ["5.1"] },
    { "id": 12, "tasks": ["5.2"] },
    { "id": 13, "tasks": ["6.1"] },
    { "id": 14, "tasks": ["6.2"] },
    { "id": 15, "tasks": ["7.1"] },
    { "id": 16, "tasks": ["7.2"] },
    { "id": 17, "tasks": ["7.3"] },
    { "id": 18, "tasks": ["7.4"] },
    { "id": 19, "tasks": ["7.5"] },
    { "id": 20, "tasks": ["8.1"] },
    { "id": 21, "tasks": ["8.2"] },
    { "id": 22, "tasks": ["8.3"] },
    { "id": 23, "tasks": ["10.1"] },
    { "id": 24, "tasks": ["10.2"] },
    { "id": 25, "tasks": ["11.1"] },
    { "id": 26, "tasks": ["11.2"] }
  ]
}
```
