# Implementation Plan: Gemini driver (spec 6)

## Overview

Test-first, one task at a time, in order. Every test task writes tests only and states the expected red reason. Every implementation task follows its test task and states the green condition. No task is optional. All commands are one per line (Windows PowerShell, no `&&`). Commits are local only: run `git status --short`, stage files by name, then commit with the message given. Never push.

Conventions used by every task:

- Property test functions are named `test_p6_<n>_<slug>` and live in `backend/tests/properties/test_gemini_properties.py`, except P6.7 and P6.8, which live in `backend/tests/properties/test_gemini_client_properties.py`, so `-k "p6_<n>_"` selects exactly one. Each has the docstring `Property P6.<n>: <statement>. Validates: <ids>` and the tag comment `# Feature: gemini-driver, Property P6.<n>: <title>`. None lowers `max_examples` below the conftest profile (200).
- Lint commands for implementation tasks: `uv --directory backend run ruff check .` and `uv --directory backend run ruff format --check .`.
- Tests never import `urllib` and never touch the network. Every new test file has its own autouse network guard.

## Tasks

- [x] 1. Driver test scaffold (no implementation)
  - [x] 1.1 Create the branch, record the baseline and write `backend/tests/unit/test_gemini_driver.py`
    - **Stop after this task. Do not write implementation until the owner pastes a red run.**
    - Confirm `git branch --show-current` prints `spec/06-gemini-driver` (created from `main`; main HEAD is the Baseline_Commit). Stop and report if it does not.
    - Run `uv --directory backend run pytest -q` before writing anything and record the passed count as the baseline (used in task 11.1).
    - In the new file: a `FakeGeminiClient` that records `(model, deep copy of body)` per call and returns prepared replies in order; an autouse network guard that monkeypatches `socket.socket.connect`, `socket.socket.connect_ex`, `socket.create_connection` and `socket.getaddrinfo` with blockers raising `RuntimeError("network access blocked: <operation>")` and fails the test in teardown if any attempt was recorded; a guard self-test that calls `socket.getaddrinfo("example.invalid", 443)`, asserts the blocker raised and named `getaddrinfo`, then clears the record.
    - First driver tests: `GeminiDriver(client)` raises `TypeError`; `GeminiDriver(client, "  ")` raises `ValueError` with zero client calls; `GeminiDriver.label == "llm"` and `GeminiDriver.provider == "gemini"`; the constructor takes only `client, model` and no attribute holds an Engine, Place, Tool or Authority; turn 1 of the design's worked example sends exactly one call with the model and a body with keys `contents`, `systemInstruction`, `tools`, `toolConfig`, `contents == [{"role": "user", "parts": [{"text": "Task: T\nYou are in library."}]}]`, declarations `read_document`, `search_archive`, `go` (enum `["vault"]`), `finish` in that order, mode `AUTO`.
    - Expected red: `ImportError: cannot import name 'GeminiDriver' from 'telepermit.drivers.llm'` at collection.
    - Verify: `uv --directory backend run pytest -q tests/unit/test_gemini_driver.py`
    - Commit: `test(drivers): add gemini fake client, network guard and first driver tests (task 1.1)`
    - _Requirements: 6.1.1, 6.1.4, 6.1.6, 6.1.9, 6.4.3, 6.5.1, 6.5.2, 6.9.1, 6.9.6, 6.11.5, 6.12.1, 6.12.2, 6.12.6_

- [x] 2. Request mapping
  - [x] 2.1 Write property test P6.1 in `backend/tests/properties/test_gemini_properties.py`
    - **Property 1: P6.1 - The request declares exactly the Observation's actions.** Generators as in design P6.1 (0 to 6 Place_Tools, args mapping / empty / non-mapping, 0 to 3 `go:` entries, `finish` with or without description). The file also holds its own Fake_Client and autouse network guard.
    - Expected red: `ImportError: cannot import name 'GeminiDriver' from 'telepermit.drivers.llm'` at collection.
    - Verify: `uv --directory backend run pytest -q tests/properties/test_gemini_properties.py -k "p6_1_"`
    - Commit: `test(drivers): property P6.1 gemini request declarations (task 2.1)`
    - _Requirements: 6.1.1, 6.1.2, 6.1.3, 6.1.4, 6.1.5, 6.1.6, 6.1.7, 6.1.8, 6.1.9, 6.1.10_
  - [x] 2.2 Write property test P6.13 in the same file
    - **Property 13: P6.13 - A blank model is rejected at construction.** Whitespace-only strings including `""`; `ValueError`; zero Fake_Client calls.
    - Expected red: the same collection `ImportError`.
    - Verify: `uv --directory backend run pytest -q tests/properties/test_gemini_properties.py -k "p6_13_"`
    - Commit: `test(drivers): property P6.13 blank model rejected (task 2.2)`
    - _Requirements: 6.5.2_
  - [x] 2.3 Write property test P6.6 in the same file
    - **Property 6: P6.6 - Request bodies carry no key and no hidden run state.** 1 to 30 fake replies through `run_scenario(enforce=e, driver=GeminiDriver(fake, model))` for both `e`; the lower-cased JSON of every body contains no generated key (`"AIza"` + 20 to 40 chars, `assume` it is not a substring of fixed texts), no identity `signature_hex`, no `sha256(DEMO_SEED).hex()` and no Banned_Word.
    - Expected red: the same collection `ImportError`.
    - Verify: `uv --directory backend run pytest -q tests/properties/test_gemini_properties.py -k "p6_6_"`
    - Commit: `test(drivers): property P6.6 request bodies hold no key or run state (task 2.3)`
    - _Requirements: 6.7.3, 6.11.2, 6.11.3_
  - [x] 2.4 Implement `GeminiDriver` construction and the request mapping in `backend/src/telepermit/drivers/llm.py`
    - Add constants `ENV_GEMINI_API_KEY`, `PROVIDER_ANTHROPIC`, `PROVIDER_GEMINI`, `_FUNCTION_MODE`, `_RESULT_KEY`; `GeminiClient` Protocol; `GeminiDriver` with `label: Final = "llm"`, `provider: Final = "gemini"`, required `model` (blank → `ValueError`), attributes `_client`, `_model`, `_history`, `_pending` only; helpers `_gemini_schema` and `_declarations`; the body of design "Request mapping".
    - `propose` appends the first-call User_Turn when the History is empty, calls the client once, and returns `Proposal("finish", {})` until task 3.3. The History list is passed as `contents` without a copy until task 4.5.
    - Keep the module docstring (CONTRACTS section 7) and `from __future__ import annotations`. `LLMDriver` is not changed in this task.
    - Green: all of `tests/unit/test_gemini_driver.py` passes, and P6.1, P6.6, P6.13 pass.
    - Verify: `uv --directory backend run pytest -q tests/unit/test_gemini_driver.py`
    - Verify: `uv --directory backend run pytest -q tests/properties/test_gemini_properties.py`
    - Verify: `uv --directory backend run ruff check .`
    - Verify: `uv --directory backend run ruff format --check .`
    - Commit: `feat(drivers): gemini driver construction and request mapping (task 2.4)`
    - _Requirements: 6.1.1, 6.1.2, 6.1.3, 6.1.4, 6.1.5, 6.1.6, 6.1.7, 6.1.8, 6.1.9, 6.1.10, 6.4.3, 6.5.1, 6.5.2, 6.7.3, 6.9.1, 6.9.6, 6.11.2, 6.11.3, 6.11.5, 6.11.6_

- [x] 3. Response mapping
  - [x] 3.1 Add response-mapping unit tests to `backend/tests/unit/test_gemini_driver.py`
    - Worked example proposals: reply 1 gives `Proposal("read_document", {"name": "briefing-q3"})`; blocked reply 2 gives finish; reply 3 (text then `finish` call) gives finish. Plus: `go` without `place` gives `Proposal("go:", {})`; `go` drops extra args; `finish` drops args; unknown name with int, bool, list and dict values gives their `str()` forms; missing or non-string name gives action `""`; `args` not an object gives `{}`; Function_Calls only in the second candidate give finish; `candidates` not a list, first candidate not a dict, content not a dict, parts not a list each give finish with no exception.
    - Expected red: `AssertionError: Proposal(action='finish', args={}) != Proposal(action='read_document', args={'name': 'briefing-q3'})`.
    - Verify: `uv --directory backend run pytest -q tests/unit/test_gemini_driver.py`
    - Commit: `test(drivers): gemini response mapping examples (task 3.1)`
    - _Requirements: 6.2.1, 6.2.2, 6.2.3, 6.2.4, 6.2.5, 6.3.1, 6.3.2, 6.3.3, 6.3.4, 6.3.5_
  - [x] 3.2 Write property test P6.2
    - **Property 2: P6.2 - Each turn yields the Proposal of the first Function_Call, else finish.** At least 200 cases of 1 to 6 turns; reply generators as in design P6.2; an independent model function computes the expected Proposal; the Fake_Client is called once per turn; stand-ins replacing `Engine.step`, `Engine.run` and `Place.execute` (monkeypatched by string path) record zero calls.
    - Expected red: `AssertionError` from a Hypothesis falsifying example whose reply holds a Function_Call (driver returns `Proposal(action='finish', args={})`).
    - Verify: `uv --directory backend run pytest -q tests/properties/test_gemini_properties.py -k "p6_2_"`
    - Commit: `test(drivers): property P6.2 first function call becomes the proposal (task 3.2)`
    - _Requirements: 6.2.1, 6.2.2, 6.2.3, 6.2.4, 6.2.5, 6.3.1, 6.3.2, 6.3.3, 6.3.4, 6.3.5, 6.11.4, 6.12.4_
  - [x] 3.3 Implement the response mapping in `drivers/llm.py`
    - `_reply_parts`, Function_Call detection (name `str` or `""`, args dict or `{}`, id `str` or `None`), and the Proposal table of design "Response mapping". `propose` sets `_pending` from the Reply_Parts.
    - Green: `tests/unit/test_gemini_driver.py` and P6.1, P6.2, P6.6, P6.13 pass.
    - Verify: `uv --directory backend run pytest -q tests/unit/test_gemini_driver.py`
    - Verify: `uv --directory backend run pytest -q tests/properties/test_gemini_properties.py`
    - Verify: `uv --directory backend run ruff check .`
    - Verify: `uv --directory backend run ruff format --check .`
    - Commit: `feat(drivers): map the first gemini function call to a proposal (task 3.3)`
    - _Requirements: 6.2.1, 6.2.2, 6.2.3, 6.2.4, 6.2.5, 6.3.1, 6.3.2, 6.3.3, 6.3.4, 6.3.5, 6.11.4_

- [x] 4. Conversation history
  - [x] 4.1 Add history unit tests to `backend/tests/unit/test_gemini_driver.py`
    - The worked example's turn 2 `contents` exactly as in the design (Model_Turn with `thoughtSignature` kept, two Function_Responses, `id: "c1"` on the first only, the "Not executed" text on the second, then `{"text": "You are now in library."}`); turn 3 after the blocked reply has three entries and the last User_Turn ends with two text parts; `last_result=None` gives `""`; mutating a body kept by the fake after the call does not change the next request.
    - Expected red: `AssertionError` on turn 2: `contents` has 1 entry, expected 3.
    - Verify: `uv --directory backend run pytest -q tests/unit/test_gemini_driver.py`
    - Commit: `test(drivers): gemini history examples (task 4.1)`
    - _Requirements: 6.4.1, 6.4.2, 6.4.4, 6.4.5, 6.4.6, 6.4.8, 6.4.10_
  - [x] 4.2 Write property test P6.3
    - **Property 3: P6.3 - The History stays well-formed and free of Banned_Words.** At least 200 cases of 1 to 6 turns with the P6.2 generators; checks of design P6.3 on every request.
    - Expected red: `AssertionError` (second request has no Model_Turn and no Function_Response).
    - Verify: `uv --directory backend run pytest -q tests/properties/test_gemini_properties.py -k "p6_3_"`
    - Commit: `test(drivers): property P6.3 well-formed gemini history (task 4.2)`
    - _Requirements: 6.4.1, 6.4.2, 6.4.3, 6.4.4, 6.4.5, 6.4.6, 6.4.9, 6.4.10, 6.1.10, 6.12.5_
  - [x] 4.3 Write property test P6.4
    - **Property 4: P6.4 - Reply parts are echoed back verbatim.** Arbitrary JSON part lists (dict parts with `text`, `functionCall`, `thought`, `thoughtSignature`, unknown keys, plus non-dict entries); the next request's Model_Turn equals `{"role": "model", "parts": <received list>}`. The docstring states that the live half of 6.4.11 is unverified.
    - Expected red: `AssertionError` (no Model_Turn in the next request).
    - Verify: `uv --directory backend run pytest -q tests/properties/test_gemini_properties.py -k "p6_4_"`
    - Commit: `test(drivers): property P6.4 reply parts echoed verbatim (task 4.3)`
    - _Requirements: 6.4.7, 6.4.11_
  - [x] 4.4 Write property test P6.5
    - **Property 5: P6.5 - Requests and History are isolated copies.** The Fake_Client snapshots each body, then mutates the received body and its own returned reply.
    - Expected red: `AssertionError`: a later request contains the client's mutation (the History list is sent without a copy since task 2.4).
    - Verify: `uv --directory backend run pytest -q tests/properties/test_gemini_properties.py -k "p6_5_"`
    - Commit: `test(drivers): property P6.5 isolated request copies (task 4.4)`
    - _Requirements: 6.4.8_
  - [x] 4.5 Implement the History in `drivers/llm.py`
    - Later-turn User_Turns (Function_Responses from `_pending` with `id` when the call had one, first carries `last_result` or `""`, later ones `_NOT_EXECUTED`, then the place text); the merge rule when the last entry is a User_Turn; the Model_Turn as a deep copy of non-empty Reply_Parts; `contents` as `copy.deepcopy(self._history)`.
    - Green: `tests/unit/test_gemini_driver.py` and P6.1 to P6.6 and P6.13 pass.
    - Verify: `uv --directory backend run pytest -q tests/unit/test_gemini_driver.py`
    - Verify: `uv --directory backend run pytest -q tests/properties/test_gemini_properties.py`
    - Verify: `uv --directory backend run ruff check .`
    - Verify: `uv --directory backend run ruff format --check .`
    - Commit: `feat(drivers): keep the gemini conversation history (task 4.5)`
    - _Requirements: 6.4.1, 6.4.2, 6.4.3, 6.4.4, 6.4.5, 6.4.6, 6.4.7, 6.4.8, 6.4.9, 6.4.10, 6.4.11_

- [x] 5. Checkpoint: driver complete
  - Run `uv --directory backend run pytest -q`, `uv --directory backend run ruff check .` and `uv --directory backend run ruff format --check .`. Ensure all tests pass, ask the user if questions arise.

- [x] 6. Provider labels
  - [x] 6.1 Write `backend/tests/unit/test_provider_labels.py`
    - `LLMDriver.provider == "anthropic"`; the twelve id and title pairs for the three variants and four drivers (scripted, llm without provider, llm `gemini`, llm `anthropic`) written out literally; scripted meta has no `provider` key and equals the Baseline_Commit meta; llm without provider keeps `<Base_Id>-llm` and `(live LLM)` with no `provider`; Gemini meta has `driver == "llm"` and `provider == "gemini"`; an llm driver with an unknown provider makes `run_scenario` raise `ValueError`. Includes its own network guard.
    - Expected red: `AttributeError: type object 'LLMDriver' has no attribute 'provider'`, and `AssertionError: id is poisoned-briefing-enforced-llm` for the provider cases.
    - Verify: `uv --directory backend run pytest -q tests/unit/test_provider_labels.py`
    - Commit: `test(scenario): provider labels for live replays (task 6.1)`
    - _Requirements: 6.9.6, 6.9.7, 6.9.8, 6.9.9, 6.9.10, 6.9.11, 6.9.12_
  - [x] 6.2 Write property test P6.12
    - **Property 12: P6.12 - Replay ids, titles and provider fields follow the provider.** All variants and the four drivers (stand-ins that finish at once, plus real `GeminiDriver` and `LLMDriver` with fake clients); `RUN_STARTED.data.driver == meta["driver"] == label`, never `scripted` for a Gemini run; id, title and `provider` follow the design table; four distinct ids and titles per variant.
    - Expected red: `AttributeError: type object 'LLMDriver' has no attribute 'provider'` or `AssertionError: id is poisoned-briefing-enforced-llm`.
    - Verify: `uv --directory backend run pytest -q tests/properties/test_gemini_properties.py -k "p6_12_"`
    - Commit: `test(scenario): property P6.12 provider-labelled replays (task 6.2)`
    - _Requirements: 6.9.1, 6.9.2, 6.9.3, 6.9.5, 6.9.7, 6.9.8, 6.9.9, 6.9.10, 6.9.11, 6.9.12, 6.13.5_
  - [x] 6.3 Apply the owner-approved assertion update in `backend/tests/unit/test_cli.py::test_llm_out_replay_is_labelled_llm`
    - Change exactly two assertions: `meta["id"] == "poisoned-briefing-enforced-llm"` becomes `meta["id"] == "poisoned-briefing-enforced-anthropic"`, and `str(meta["title"]).endswith("(live LLM)")` becomes `str(meta["title"]).endswith("(Anthropic live LLM)")`. Add one assertion `meta["provider"] == "anthropic"`. No other line of `test_cli.py` changes; the `driver` and `generated_by` assertions stay.
    - Expected red: `AssertionError: id is poisoned-briefing-enforced-llm` (shown as `assert 'poisoned-briefing-enforced-llm' == 'poisoned-briefing-enforced-anthropic'`).
    - Verify: `uv --directory backend run pytest -q tests/unit/test_cli.py`
    - Commit: `test(cli): expect the anthropic provider label on llm replays (task 6.3)`
    - _Requirements: 6.13.6, 6.9.7, 6.9.8, 6.9.9_
  - [x] 6.4 Implement provider labels
    - `drivers/llm.py`: `LLMDriver.provider: Final = PROVIDER_ANTHROPIC` (one added line; Anthropic request unchanged).
    - `scenarios/poisoned_briefing.py`: `PROVIDER_NAMES`, `LiveReplayMeta(ReplayMeta, total=False)` with a docstring stating that `provider` is an optional replay format addition, absent on scripted replays, pending an owner amendment to CONTRACTS section 9; `ScenarioRun.provider: str | None = None` as the last field; `_provider_of`; `run_scenario` stores the provider; `replay_identity` and `replay_meta` follow the design table. `docs/CONTRACTS.md` is not edited.
    - Green: `test_provider_labels.py`, P6.12, `test_cli.py`, `test_scenario_replay.py` and `test_replays.py` pass (existing `Finisher("llm")` tests keep `-llm` because `Finisher` has no `provider`).
    - Verify: `uv --directory backend run pytest -q tests/unit/test_provider_labels.py`
    - Verify: `uv --directory backend run pytest -q tests/properties/test_gemini_properties.py -k "p6_12_"`
    - Verify: `uv --directory backend run pytest -q tests/unit/test_cli.py tests/unit/test_scenario_replay.py tests/test_replays.py`
    - Verify: `uv --directory backend run ruff check .`
    - Verify: `uv --directory backend run ruff format --check .`
    - Commit: `feat(scenario): label live replays with their provider (task 6.4)`
    - _Requirements: 6.9.6, 6.9.7, 6.9.8, 6.9.9, 6.9.10, 6.9.11, 6.9.12, 6.9.13, 6.13.1, 6.13.5_

- [x] 7. Architecture checks
  - [x] 7.1 Add new checks to `backend/tests/test_architecture.py` (no existing check changed or removed)
    - `check_urllib_imports(source, filename)` with a self-test on bad snippets (module-level `import urllib.request`, `from urllib.parse import quote`, an import in another function); a test that no module under `tests/` imports urllib. The urllib-presence check (only package hit inside `build_gemini_client`) is written in task 8.1, not here.
    - `describe_banned_imports(source, filename)` reporting `"<file>:<line>: imports <module> (<names>)"` for absolute, relative, `from telepermit import engine` and in-function forms of `engine`, `identity`, `place`, `tools`; a self-test that `from telepermit.engine import Engine` names `telepermit.engine` and `Engine`; a test over `drivers/` (invariant 2 still holds for `drivers/llm.py`).
    - `drivers/llm.py` first statement is a docstring naming `CONTRACTS section 7` and it has `from __future__ import annotations`; every import in `drivers/llm.py` is stdlib (`sys.stdlib_module_names`), `telepermit.drivers`, or `anthropic` inside `build_client`.
    - Expected red: No red expected: these checks guard code that already complies; each self-test proves its checker fails on a bad snippet. This is stated in the commit body.
    - Verify: `uv --directory backend run pytest -q tests/test_architecture.py`
    - Commit: `test(arch): urllib confinement and driver import checks (task 7.1)`
    - _Requirements: 6.6.1, 6.11.1, 6.11.6, 6.11.7, 6.12.3, 6.13.4_

- [x] 8. Real Gemini client
  - [x] 8.1 Write `backend/tests/unit/test_gemini_client.py` and the urllib-presence check in `backend/tests/test_architecture.py`
    - The new file has its own autouse network guard. In `tests/test_architecture.py` (additions only), add a test using `check_urllib_imports` that the only package hit is inside `build_gemini_client` in `drivers/llm.py`, with at least one hit there.
    - All tests in `test_gemini_client.py` replace the opener factory with `monkeypatch.setattr("urllib.request.build_opener", fake_factory)` (string path; no urllib import in tests). `fake_factory(*handlers)` records handlers and returns a fake opener whose `open(request, timeout=...)` records calls and returns a fake response (`status`, `read()`, context manager). HTTP errors use a test-defined `OSError` subclass with an int `code`.
    - Examples: blank and whitespace key gives `ValueError` without the key in the message and without calling the factory; construction calls no `open`; one 200 call sends one `POST` to `GEMINI_BASE_URL + "fake-model:generateContent"` with `timeout=60`, `Content-Type: application/json`, `x-goog-api-key` equal to the key, UTF-8 JSON data, key not in URL or data, and returns the stub's object; a model holding `/`, `?`, `#` is percent-encoded; **302 reply raises** (one `open` call, message holds `302`, no key or `Location` URL in the message or chain); **the handler follows nothing** (the recorded handler's MRO holds a class named `HTTPRedirectHandler`, and `redirect_request(...)` returns `None` for 301, 302, 303, 307, 308); the timeout example with `timeout_s=0.05` and a fake opener blocked on a `threading.Event` raises `GeminiRequestError` within about 1 second, then sets the event; non-JSON body and non-object JSON raise `GeminiRequestError`; `repr` and `str` hide the key.
    - Expected red: `ImportError: cannot import name 'build_gemini_client' from 'telepermit.drivers.llm'` at collection of `test_gemini_client.py` only; in `tests/test_architecture.py` only the new test fails, with `AssertionError: no urllib import inside build_gemini_client in drivers/llm.py`.
    - Verify: `uv --directory backend run pytest -q tests/unit/test_gemini_client.py`
    - Verify: `uv --directory backend run pytest -q tests/test_architecture.py`
    - Commit: `test(drivers): real gemini client examples and urllib-presence check (task 8.1)`
    - _Requirements: 6.6.1, 6.6.2, 6.6.3, 6.6.4, 6.6.5, 6.6.6, 6.6.7, 6.6.8, 6.6.9, 6.7.4, 6.7.5, 6.12.1, 6.12.3_
  - [x] 8.2 Write property test P6.7
    - **Property 7: P6.7 - The real client sends one key-in-header POST to the encoded endpoint.** Any non-blank model (including `/`, `?`, `#`, `:`, spaces, non-ASCII), generated key and JSON-object body; checks of design P6.7 with a small percent-decoder written in the test. Written in the NEW file `backend/tests/properties/test_gemini_client_properties.py`, which has its own fake opener and autouse network guard.
    - Expected red: `ImportError: cannot import name 'build_gemini_client' from 'telepermit.drivers.llm'` at collection of `test_gemini_client_properties.py` only.
    - Verify: `uv --directory backend run pytest -q tests/properties/test_gemini_client_properties.py -k "p6_7_"`
    - Commit: `test(drivers): property P6.7 one key-in-header POST (task 8.2)`
    - _Requirements: 6.6.2, 6.6.4, 6.6.5, 6.6.6_
  - [x] 8.3 Write property test P6.8
    - **Property 8: P6.8 - Client failures raise key-free exceptions.** Failure modes of design P6.8 (int `code` 300 to 599, returned non-2xx status, `OSError` or other `Exception` holding the key, non-UTF-8-JSON body, non-object JSON); whitespace-only keys; `repr`/`str`. Written in `backend/tests/properties/test_gemini_client_properties.py`.
    - Expected red: the same collection `ImportError`, in `test_gemini_client_properties.py` only.
    - Verify: `uv --directory backend run pytest -q tests/properties/test_gemini_client_properties.py -k "p6_8_"`
    - Commit: `test(drivers): property P6.8 key-free client failures (task 8.3)`
    - _Requirements: 6.6.3, 6.6.8, 6.6.9, 6.7.4, 6.7.5_
  - [x] 8.4 Implement `build_gemini_client` and the real client in `drivers/llm.py`
    - Constants `GEMINI_BASE_URL`, `GEMINI_METHOD`, `GEMINI_KEY_HEADER`, `REQUEST_TIMEOUT_S`; `GeminiRequestError`; `build_gemini_client(api_key, *, timeout_s=REQUEST_TIMEOUT_S)` with blank-key `ValueError`, the only `import urllib.parse` / `import urllib.request` inside its body, the nested `_NoRedirectHandler` whose `redirect_request` returns `None`, and `urllib.request.build_opener(_NoRedirectHandler())` looked up at call time; module-level `_UrllibGeminiClient` with `__slots__`, redacted `__repr__`/`__str__`, `quote(model, safe="")`, one `opener.open` in a daemon worker joined with `timeout_s`, and raises placed after the `try` statement so no exception chain is kept.
    - Green: `tests/unit/test_gemini_client.py`, `tests/properties/test_gemini_client_properties.py` (P6.7, P6.8) and `tests/test_architecture.py` pass, and `tests/unit/test_gemini_driver.py` and `tests/properties/test_gemini_properties.py` stay green.
    - Verify: `uv --directory backend run pytest -q tests/unit/test_gemini_client.py`
    - Verify: `uv --directory backend run pytest -q tests/properties/test_gemini_client_properties.py`
    - Verify: `uv --directory backend run pytest -q tests/test_architecture.py`
    - Verify: `uv --directory backend run pytest -q tests/unit/test_gemini_driver.py`
    - Verify: `uv --directory backend run pytest -q tests/properties/test_gemini_properties.py`
    - Verify: `uv --directory backend run ruff check .`
    - Verify: `uv --directory backend run ruff format --check .`
    - Commit: `feat(drivers): stdlib gemini client with no redirects (task 8.4)`
    - _Requirements: 6.6.1, 6.6.2, 6.6.3, 6.6.4, 6.6.5, 6.6.6, 6.6.7, 6.6.8, 6.6.9, 6.7.4, 6.7.5, 6.13.3, 6.13.4_

- [x] 9. CLI `--driver gemini`
  - [x] 9.1 Write `backend/tests/unit/test_gemini_cli.py`
    - Own network guard and Fake_Client; factory replaced with `monkeypatch.setattr(cli, "build_gemini_client", fake)`; every test passes `env=` to `cli.main` except one that sets fake `AGENT_MODEL` and `GEMINI_API_KEY` with `monkeypatch.setenv` (restored by pytest).
    - Examples: parser accepts `gemini` and still defaults to `scripted`; missing `AGENT_MODEL`, missing `GEMINI_API_KEY`, both missing, and whitespace-only values each print one stderr line naming the variables in order, exit 1, empty stdout, factory not called, no `--out` file; factory raising prints exactly `error: <Type> while building the Gemini client`, exit 1; a run exception prints exactly `error: run aborted: <Type> (details withheld; see docs)`, exit 1, empty stdout, a pre-existing `--out` file unchanged; a full fake run with `--out` prints timeline, `status:` and `outbox:`, exits 0, writes id `poisoned-briefing-enforced-gemini`, `driver == "llm"`, `provider == "gemini"`; that replay passes a backend mirror of the frontend `META_SPECS` (required keys present and typed, `driver` in `{scripted, llm}`, extra keys allowed); an unwritable `--out` exits 1; `--driver llm` with a recording env never reads `GEMINI_API_KEY`.
    - Expected red: `argparse error: invalid choice: 'gemini'` (`SystemExit: 2`), and `AttributeError: <module 'telepermit.cli'> has no attribute 'build_gemini_client'` where the factory is replaced.
    - Verify: `uv --directory backend run pytest -q tests/unit/test_gemini_cli.py`
    - Commit: `test(cli): gemini driver path examples (task 9.1)`
    - _Requirements: 6.5.3, 6.5.4, 6.5.5, 6.8.1, 6.8.2, 6.8.3, 6.8.4, 6.8.5, 6.8.6, 6.9.4, 6.10.1, 6.10.2, 6.10.3, 6.10.4, 6.12.1, 6.12.2, 6.12.7_
  - [x] 9.2 Write property test P6.9
    - **Property 9: P6.9 - The gemini CLI path never prints or writes the key.** Generated key and model, enforce on/off, `--out` absent / new / pre-existing, outcomes: final status, Fake_Client raising with the key in its message, factory raising with the key in its message.
    - Expected red: `AttributeError: <module 'telepermit.cli'> has no attribute 'build_gemini_client'`.
    - Verify: `uv --directory backend run pytest -q tests/properties/test_gemini_properties.py -k "p6_9_"`
    - Commit: `test(cli): property P6.9 key never printed or written (task 9.2)`
    - _Requirements: 6.7.1, 6.7.2, 6.8.4, 6.8.5, 6.8.6, 6.10.1, 6.10.2, 6.10.3, 6.10.4_
  - [x] 9.3 Write property test P6.10
    - **Property 10: P6.10 - Missing variables stop the gemini path before any client exists.** Environments with either or both variables absent, empty or whitespace-only, plus random others including `ANTHROPIC_API_KEY`.
    - Expected red: `AttributeError: <module 'telepermit.cli'> has no attribute 'build_gemini_client'`.
    - Verify: `uv --directory backend run pytest -q tests/properties/test_gemini_properties.py -k "p6_10_"`
    - Commit: `test(cli): property P6.10 missing variables stop early (task 9.3)`
    - _Requirements: 6.8.3, 6.5.3_
  - [x] 9.4 Write property test P6.11
    - **Property 11: P6.11 - The CLI passes stripped values and reads only its own variables.** Model and key wrapped in random whitespace; a recording env; the factory gets the stripped key once; every Fake_Client call gets the stripped model; reads are a subset of `{AGENT_MODEL, GEMINI_API_KEY}`; no Observation holds the key.
    - Expected red: `AttributeError: <module 'telepermit.cli'> has no attribute 'build_gemini_client'`.
    - Verify: `uv --directory backend run pytest -q tests/properties/test_gemini_properties.py -k "p6_11_"`
    - Commit: `test(cli): property P6.11 stripped values and own variables only (task 9.4)`
    - _Requirements: 6.5.3, 6.5.4, 6.7.6, 6.8.2_
  - [x] 9.5 Implement the `--driver gemini` path in `backend/src/telepermit/cli.py`
    - `--driver` choices `scripted`, `llm`, `gemini` (default `scripted`); docstring usage line gains `gemini`; import `ENV_GEMINI_API_KEY`, `GeminiDriver`, `build_gemini_client`; extract `_run_live` from `_run_llm` with byte-identical `llm` output; add `_run_gemini` as in the design (missing-variable line, factory error line, key passed only to the factory, stripped model to the driver).
    - Green: `test_gemini_cli.py`, P6.9, P6.10, P6.11 and the unchanged-plus-task-6.3 `test_cli.py` pass.
    - Verify: `uv --directory backend run pytest -q tests/unit/test_gemini_cli.py`
    - Verify: `uv --directory backend run pytest -q tests/properties/test_gemini_properties.py`
    - Verify: `uv --directory backend run pytest -q tests/unit/test_cli.py`
    - Verify: `uv --directory backend run ruff check .`
    - Verify: `uv --directory backend run ruff format --check .`
    - Commit: `feat(cli): add --driver gemini (task 9.5)`
    - _Requirements: 6.5.3, 6.5.4, 6.5.5, 6.7.1, 6.7.2, 6.7.6, 6.8.1, 6.8.2, 6.8.3, 6.8.4, 6.8.5, 6.8.6, 6.10.1, 6.10.2, 6.10.3, 6.10.4, 6.13.5_

- [x] 10. Checkpoint: all new paths green
  - Run `uv --directory backend run pytest -q`, `uv --directory backend run ruff check .` and `uv --directory backend run ruff format --check .`. Ensure all tests pass, ask the user if questions arise.

- [x] 11. Final checkpoint and progress record
  - [x] 11.1 Run the full verification and the unchanged-files checks
    - `uv --directory backend run pytest -q` (passed count must be no lower than the task 1.1 baseline, no skip, xfail or deleted test)
    - `uv --directory backend run ruff check .`
    - `uv --directory backend run ruff format --check .`
    - `git diff --stat main -- backend/src/telepermit/engine.py backend/src/telepermit/place.py backend/src/telepermit/tools.py backend/src/telepermit/audit.py backend/src/telepermit/permit.py backend/src/telepermit/identity.py backend/src/telepermit/clock.py frontend` (expected: empty)
    - `git diff --stat main -- backend/pyproject.toml backend/uv.lock` (expected: empty)
    - `git diff --name-only main` (expected source files: only `drivers/llm.py`, `cli.py`, `scenarios/poisoned_briefing.py`; existing test files changed: only `tests/test_architecture.py` and `tests/unit/test_cli.py`; plus the new test files and docs; no new module under `src/`)
    - `git diff main -- backend/tests/test_architecture.py` (expected: additions only)
    - _Requirements: 6.12.1, 6.13.1, 6.13.2, 6.13.3, 6.13.4, 6.13.6, 6.13.7_
  - [x] 11.2 Update `docs/PROGRESS.md`
    - Record: spec folder `gemini-driver`, branch `spec/06-gemini-driver`, baseline and final passed counts, tasks done; pending owner-applied CONTRACTS amendments for section 9 (optional `meta.provider`, live ids `<Base_Id>-<provider>`, titles `<Base_Title> (<Provider_Name> live LLM)`) and section 10 (`--driver scripted|llm|gemini`, `GEMINI_API_KEY` and `AGENT_MODEL`); the first live Gemini run (6.4.11 live half, U1 to U5) is a manual owner step. `docs/CONTRACTS.md` and steering files are not edited.
    - Verify: `git status --short`
    - Commit: `docs(progress): record spec 06 gemini driver (task 11.2)`
    - _Requirements: 6.9.13_

## Notes

- No task is optional. Property tests P6.1 to P6.13 are each their own task and are written red before the implementation they check.
- Task 1.1 ends with a stop: the owner pastes the red run before task 2.1 starts.
- Task 6.3 is the only edit to an existing test file other than the additions to `tests/test_architecture.py` in tasks 7.1 and 8.1 (6.13.6). It was approved by the owner.
- Red is confined to the file a test task names, and only until its implementation task. Collection-level ImportErrors only hit new files (`test_gemini_driver.py` and `test_gemini_properties.py` until 2.4, `test_gemini_client.py` and `test_gemini_client_properties.py` until 8.4). In an already-green file, only the newly written test is red (the urllib-presence check in `tests/test_architecture.py` from 8.1 to 8.4), so a regression elsewhere in that file still shows.
- If any command fails twice for the same reason, stop and report the error and diagnosis.

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["2.1"] },
    { "id": 2, "tasks": ["2.2"] },
    { "id": 3, "tasks": ["2.3"] },
    { "id": 4, "tasks": ["2.4"] },
    { "id": 5, "tasks": ["3.1"] },
    { "id": 6, "tasks": ["3.2"] },
    { "id": 7, "tasks": ["3.3"] },
    { "id": 8, "tasks": ["4.1"] },
    { "id": 9, "tasks": ["4.2"] },
    { "id": 10, "tasks": ["4.3"] },
    { "id": 11, "tasks": ["4.4"] },
    { "id": 12, "tasks": ["4.5"] },
    { "id": 13, "tasks": ["6.1"] },
    { "id": 14, "tasks": ["6.2"] },
    { "id": 15, "tasks": ["6.3"] },
    { "id": 16, "tasks": ["6.4"] },
    { "id": 17, "tasks": ["7.1"] },
    { "id": 18, "tasks": ["8.1"] },
    { "id": 19, "tasks": ["8.2"] },
    { "id": 20, "tasks": ["8.3"] },
    { "id": 21, "tasks": ["8.4"] },
    { "id": 22, "tasks": ["9.1"] },
    { "id": 23, "tasks": ["9.2"] },
    { "id": 24, "tasks": ["9.3"] },
    { "id": 25, "tasks": ["9.4"] },
    { "id": 26, "tasks": ["9.5"] },
    { "id": 27, "tasks": ["11.1"] },
    { "id": 28, "tasks": ["11.2"] }
  ]
}
```
