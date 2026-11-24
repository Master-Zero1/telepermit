# Requirements Document

## Introduction

Spec 6 adds a second live driver, the Gemini_Driver, for Google's Gemini API. The operator selects it with `--driver gemini`. The Gemini_Driver behaves like the existing Anthropic LLMDriver (CONTRACTS section 7): it maps an Observation to a function-calling request, returns the first function call of the reply as a Proposal, keeps its own conversation history, never executes tools, and takes its model name from `AGENT_MODEL`. The Gemini_Driver and the Client_Factory live in `drivers/llm.py`, next to the Anthropic_Driver; no new module is created.

The Gemini_Driver talks to the Gemini `generateContent` REST endpoint through an injected Gemini_Client. The only real Gemini_Client is built by the Client_Factory `build_gemini_client`, which uses `urllib` from the standard library, imported inside the factory only. No new dependency is added. Tests use a Fake_Client and make no network call.

The Engine, places, tools, audit module and UI are not changed. Live replays keep the existing driver value `llm` and name their provider in their id, their title and a new optional `meta.provider` field (Requirement 6.9). That field is a replay format addition: it needs an owner-applied amendment to CONTRACTS section 9, which this spec does not write.

Honest scope: the request and response mapping follows the documented Gemini REST API. It is not exercised against the live service in this spec. The first live run is a manual step for the owner.

## Glossary

- **Gemini_Driver**: The new driver class (working name `GeminiDriver`) in `drivers/llm.py`. It implements the AgentDriver protocol of `drivers/base.py`.
- **Gemini_Client**: The injected interface the Gemini_Driver calls once per turn with a model name and a request body, and which returns the parsed JSON reply as a mapping.
- **Client_Factory**: The function `build_gemini_client(api_key)` in `drivers/llm.py`. It returns the real Gemini_Client and is the only code that imports `urllib`.
- **Anthropic_Driver**: The existing `LLMDriver` in `drivers/llm.py`.
- **Fake_Client**: A test double of the Gemini_Client that records each request and returns a prepared reply. It makes no network call.
- **CLI**: The command line in `backend/src/telepermit/cli.py` (CONTRACTS section 10).
- **Engine**: The run loop in `engine.py`, the only code that executes tools (security invariant 1).
- **Observation**: The five-field input of a driver: `task`, `turn`, `place`, `tools`, `last_result` (CONTRACTS section 7).
- **Proposal**: The `(action, args)` value a driver returns (CONTRACTS section 7).
- **Function_Declaration**: One entry of the `functionDeclarations` list of a Gemini request: a name, a description and a parameters schema.
- **Function_Call**: A reply part that holds a `functionCall` with a `name` and `args`. A `functionCall` with a missing or non-string `name` is still a Function_Call; its name is read as the empty string.
- **Function_Response**: A request part that holds a `functionResponse` carrying the result of one earlier Function_Call.
- **Reply_Parts**: the `parts` list of the content of the first candidate of a Gemini reply; empty when any of these is missing or malformed (see 6.3).
- **Model_Turn**: A history entry with role `model` holding the parts of one reply.
- **User_Turn**: A history entry with role `user` holding text and Function_Response parts.
- **History**: The ordered list of User_Turns and Model_Turns the Gemini_Driver keeps across turns of one run.
- **Go_Function**: The single Function_Declaration named `go` whose `place` parameter is an enum of the other places.
- **Place_Tool**: An Observation tool entry whose name is neither `finish` nor starts with `go:`.
- **Finish_Proposal**: `Proposal("finish", {})`.
- **Banned_Words**: `permit`, `allowance` and `teleclick`, compared in lower case.
- **API_Key**: The value of the environment variable `GEMINI_API_KEY`.
- **Replay**: A replay JSON file as defined in CONTRACTS section 9.
- **Scenario**: `scenarios/poisoned_briefing.py`, which builds the Replay id, title and meta.
- **Provider**: The live model provider a driver exposes: `gemini` for the Gemini_Driver, `anthropic` for the Anthropic_Driver.
- **Provider_Name**: `Gemini` for the Provider `gemini`, `Anthropic` for the Provider `anthropic`.
- **Provider_Field**: The optional `provider` key of the Replay meta.
- **Base_Id** and **Base_Title**: The Scenario's existing replay id and title for a run variant: `poisoned-briefing-enforced` and `Poisoned briefing: limits enforced`; `poisoned-briefing-unenforced` and `Poisoned briefing: no enforcement`; `forged-identity-refused` and `Forged identity refused at the border`.
- **Baseline_Commit**: The main-branch commit the spec branch was created from.

## Requirements

### Requirement 1: 6.1 Map the Observation to a Gemini request

**User Story:** As the owner, I want the Gemini_Driver to offer exactly the actions in the Observation as functions, so that Gemini can choose only actions the Engine knows.

#### Acceptance Criteria

6.1.1. WHEN the Gemini_Driver proposes, THE Gemini_Driver SHALL call the Gemini_Client exactly once per propose call, passing the model name given at construction and a request body that holds `contents`, `systemInstruction`, `tools` and `toolConfig`.
6.1.2. WHEN the Gemini_Driver proposes, THE Gemini_Driver SHALL declare each Observation tool entry whose name is neither `finish` nor starts with `go:` as one Place_Tool Function_Declaration, in Observation order. Each declaration SHALL carry the entry name, the entry description (an empty string when the entry has none) and an object parameters schema with one required string property per argument name, listed in the entry's argument order.
6.1.3. IF a Place_Tool entry lists no arguments, or its arguments are not a name-to-description mapping, THEN THE Gemini_Driver SHALL declare that Place_Tool with an object parameters schema that has zero properties and an empty required list.
6.1.4. IF the Observation lists one or more `go:<place>` entries, THEN THE Gemini_Driver SHALL declare exactly one Go_Function named `go`, with a fixed description and a required `place` parameter that is a string enum of the place names after the `go:` prefix, in Observation order.
6.1.5. IF the Observation lists no `go:<place>` entry, THEN THE Gemini_Driver SHALL declare no Go_Function.
6.1.6. WHEN the Gemini_Driver proposes, THE Gemini_Driver SHALL declare exactly one Function_Declaration named `finish` with an object parameters schema that has zero properties, placed after all Place_Tools and after the Go_Function when one is declared.
6.1.7. IF the Observation contains a `finish` entry that has a description, THEN THE Gemini_Driver SHALL use that description for the `finish` Function_Declaration; otherwise THE Gemini_Driver SHALL use a fixed default description.
6.1.8. WHEN the Gemini_Driver proposes, THE Gemini_Driver SHALL declare a total number of Function_Declarations equal to the number of Place_Tools, plus 1 when a Go_Function is declared, plus 1 for `finish`, with no other functions.
6.1.9. WHEN the Gemini_Driver proposes, THE Gemini_Driver SHALL set the function-calling mode of `toolConfig` to `AUTO`.
6.1.10. WHEN the Gemini_Driver proposes, THE Gemini_Driver SHALL send the same system instruction text on every call, and that text SHALL contain none of the Banned_Words.

### Requirement 2: 6.2 Map the first Function_Call to a Proposal

**User Story:** As the owner, I want the first function call of a reply to become the Proposal, so that the Engine receives one action per turn.

#### Acceptance Criteria

6.2.1. WHEN the first candidate of a reply holds one or more Function_Calls, THE Gemini_Driver SHALL return exactly one Proposal, built only from the first Function_Call in part order. Candidates after the first and Function_Calls after the first SHALL have no effect on the returned Proposal.
6.2.2. WHEN the first Function_Call is named `go`, THE Gemini_Driver SHALL return `Proposal("go:" + place, {})`, where `place` is the string form of the `place` argument. IF `place` is missing, THEN the action SHALL be `"go:"` alone. All other arguments of the `go` call SHALL be discarded.
6.2.3. WHEN the first Function_Call is named `finish`, THE Gemini_Driver SHALL return the Finish_Proposal with empty arguments, and SHALL discard any arguments the call holds.
6.2.4. WHEN the first Function_Call has any name other than `go` or `finish`, including a missing name read as the empty string, THE Gemini_Driver SHALL return a Proposal with that name unchanged. The Proposal SHALL hold the same number of arguments as the call, with each key and each value, including numbers, booleans, lists and nested objects, replaced by its string form. The Gemini_Driver SHALL NOT check whether the action is allowed, because the Engine decides that.
6.2.5. IF the `args` of the first Function_Call is missing or is not an object, THEN THE Gemini_Driver SHALL treat the arguments as empty and return the Proposal without raising an error.

### Requirement 3: 6.3 Propose finish when there is no Function_Call

**User Story:** As the owner, I want a reply without a function call to end the run cleanly, so that a text-only or blocked reply cannot stall the run.

#### Acceptance Criteria

6.3.1. IF the first candidate of a reply holds one or more content parts and none of them is a Function_Call, THEN THE Gemini_Driver SHALL return the Finish_Proposal, as the Anthropic_Driver does, without raising an exception, whatever the text or other non-Function_Call parts contain.
6.3.2. IF a reply has no `candidates` field or an empty candidates list, including a reply that was blocked before any candidate was produced, THEN THE Gemini_Driver SHALL return the Finish_Proposal without raising an exception.
6.3.3. IF the first candidate of a reply has no content, or its content has no parts field, or its parts list is empty, THEN THE Gemini_Driver SHALL return the Finish_Proposal, as the Anthropic_Driver does, without raising an exception.
6.3.4. IF a reply holds Function_Calls only in candidates after the first, THEN THE Gemini_Driver SHALL ignore those Function_Calls and return the Finish_Proposal.
6.3.5. IF the `candidates` value is not a list, or the first candidate is not an object, or its content is not an object, or its parts value is not a list, THEN THE Gemini_Driver SHALL return the Finish_Proposal without raising an exception.

### Requirement 4: 6.4 Keep the conversation history

**User Story:** As the owner, I want the Gemini_Driver to keep a well-formed history, so that Gemini sees the result of each action it chose.

#### Acceptance Criteria

6.4.1. WHEN the Gemini_Driver proposes and Reply_Parts is non-empty, THE Gemini_Driver SHALL grow the History by exactly two turns: one User_Turn followed by one Model_Turn, in that order, except that under 6.4.10 the new User_Turn content is merged into the last User_Turn and the History grows by the Model_Turn only.
6.4.2. WHEN the Gemini_Driver proposes and Reply_Parts is empty, THE Gemini_Driver SHALL return the Finish_Proposal, as the Anthropic_Driver does, SHALL add no Model_Turn, and SHALL grow the History by at most one User_Turn (none under 6.4.10).
6.4.3. WHEN the Gemini_Driver proposes for the first time, THE Gemini_Driver SHALL build a User_Turn that holds exactly one part: a text part containing the Observation task and the Observation place.
6.4.4. WHEN the Gemini_Driver proposes and the Reply_Parts of the immediately preceding reply held one or more Function_Calls, THE Gemini_Driver SHALL build a User_Turn that holds one Function_Response per Function_Call in those Reply_Parts, in the same order, each carrying the name of its matching Function_Call, followed by exactly one text part containing the Observation place.
6.4.5. IF the Reply_Parts of the immediately preceding reply held no Function_Call (Reply_Parts held only non-Function_Call parts or Reply_Parts was empty), THEN THE Gemini_Driver SHALL build a User_Turn that holds exactly one part: a text part containing the Observation place.
6.4.6. WHEN the Gemini_Driver builds the Function_Responses of a User_Turn, THE Gemini_Driver SHALL put the Observation `last_result` (or the empty string when `last_result` is null) in the first Function_Response and the fixed text "Not executed: only one action is taken per turn." in every later Function_Response.
6.4.7. WHEN Reply_Parts is non-empty, THE Gemini_Driver SHALL store the Model_Turn with every entry of Reply_Parts in the received order and with every field value equal to the received value, including fields the Gemini_Driver does not read.
6.4.8. THE Gemini_Driver SHALL send the Gemini_Client a copy of the History, so that a later change to the History leaves every request the Gemini_Client already received unchanged, and a change the Gemini_Client makes to its request leaves the History unchanged.
6.4.9. THE Gemini_Driver SHALL keep the History alternating between User_Turns and Model_Turns, starting with a User_Turn, so that no two User_Turns are adjacent in the History or in any request sent to the Gemini_Client.
6.4.10. IF the Gemini_Driver proposes again after a reply whose Reply_Parts was empty, THEN THE Gemini_Driver SHALL append the parts of the new User_Turn to the end of the last User_Turn instead of adding a second User_Turn.
6.4.11. UNVERIFIED: THE Gemini_Driver SHALL return every entry of Reply_Parts to the provider in later requests exactly as received, including the `thoughtSignature` field and every other field of each part. This behaviour is unverified against the live Gemini API until the first live run passes.

### Requirement 5: 6.5 Take the model and key from the environment

**User Story:** As the owner, I want the model and key to come only from the environment, so that no model name or secret is written in code.

#### Acceptance Criteria

6.5.1. THE Gemini_Driver SHALL take the model name as a required constructor argument that has no default value, so constructing a Gemini_Driver without a model name fails with `TypeError`.
6.5.2. IF the model name given to the Gemini_Driver is empty or contains only whitespace characters, THEN THE Gemini_Driver SHALL raise `ValueError` during construction and SHALL send no request to the model.
6.5.3. WHERE `--driver gemini` is selected, THE CLI SHALL read the model name only from `AGENT_MODEL` and the API_Key only from `GEMINI_API_KEY`, and SHALL remove leading and trailing whitespace from each value before using it.
6.5.4. WHERE `--driver gemini` is selected, THE CLI SHALL pass the whitespace-stripped `AGENT_MODEL` value to the Gemini_Driver unchanged as the model name, with no fallback or substitute model name, and SHALL leave `ANTHROPIC_API_KEY` unread.
6.5.5. WHERE `--driver llm` is selected, THE CLI SHALL keep the existing Anthropic behaviour (model name from `AGENT_MODEL`, key from `ANTHROPIC_API_KEY`), except for the Replay id, title and Provider_Field that Requirement 6.9 sets, and SHALL leave `GEMINI_API_KEY` unread.

### Requirement 6: 6.6 Build the real Gemini_Client with the standard library

**User Story:** As the owner, I want the real client to use only the standard library, so that no dependency is added and tests stay offline.

#### Acceptance Criteria

6.6.1. THE Client_Factory SHALL import `urllib` only inside the Client_Factory function body, and no other module of the `telepermit` package SHALL import `urllib` at module level or inside any function.
6.6.2. WHEN the Client_Factory is called with a non-blank API_Key, THE Client_Factory SHALL return a Gemini_Client without opening any network connection.
6.6.3. IF the Client_Factory is called with an API_Key that is empty or contains only whitespace, THEN THE Client_Factory SHALL raise `ValueError` without opening any network connection, and the exception message SHALL not contain the API_Key.
6.6.4. WHEN the real Gemini_Client is called with a model name and a request body, THE Gemini_Client SHALL send exactly one HTTPS POST request, with no retry, to the Gemini `generateContent` endpoint for that model. The request body SHALL be the UTF-8 JSON encoding of the request body and SHALL carry a JSON content-type header. The model name SHALL be percent-encoded in the URL path so that characters such as `/`, `?` and `#` cannot change the path or add a query.
6.6.5. WHEN the endpoint answers with an HTTP status from 200 to 299 and a body that parses as a JSON object, THE Gemini_Client SHALL return that object as a mapping.
6.6.6. THE Gemini_Client SHALL send the API_Key only as the value of one request header, and the API_Key SHALL not appear as a substring of the request URL or the request body.
6.6.7. IF a request has not completed within 60 seconds, counting connection and reading together, THEN THE Gemini_Client SHALL stop waiting and raise an exception without retrying.
6.6.8. IF the endpoint answers with an HTTP status outside 200 to 299, or with a body that is not valid JSON, or with JSON that is not an object, or IF the connection fails, THEN THE Gemini_Client SHALL raise an exception. For a non-2xx answer, the exception message SHALL include the HTTP status code. Neither that exception's message nor the message of any chained exception SHALL contain the API_Key as a substring.
6.6.9. IF the endpoint answers with an HTTP redirect (any 3xx status), THEN THE Gemini_Client SHALL follow no redirect, SHALL send no second request, and SHALL raise an exception that names the status code and contains no API_Key, so that the API_Key header is never sent to another address.

### Requirement 7: 6.7 Keep the API_Key secret

**User Story:** As the owner, I want the API_Key to stay out of every output, so that running the demo cannot leak a credential.

#### Acceptance Criteria

6.7.1. WHEN a CLI run with `--driver gemini` ends, with exit code 0 or non-zero, THE CLI SHALL write no stdout or stderr text that contains the API_Key as a substring. This includes runs ended by a missing variable, by an exception from the Gemini_Client (HTTP error, timeout or non-JSON body) or by an exception from the Gemini_Driver.
6.7.2. WHEN a CLI run with `--driver gemini` writes a Replay with `--out`, THE CLI SHALL write a Replay file whose full text contains no occurrence of the API_Key as a substring.
6.7.3. WHEN the Gemini_Driver calls the Gemini_Client, THE Gemini_Driver SHALL pass a request body whose JSON serialization contains no occurrence of the API_Key as a substring.
6.7.4. IF the Gemini_Driver, the Client_Factory or the Gemini_Client raises an exception, THEN the message of that exception and of every exception chained to it as its cause or context SHALL contain no occurrence of the API_Key as a substring.
6.7.5. THE Gemini_Client SHALL return a `repr` and a `str` that contain no occurrence of the API_Key as a substring.
6.7.6. WHERE `--driver gemini` is selected, THE CLI SHALL pass the API_Key only to the Client_Factory and SHALL NOT pass it to the Gemini_Driver constructor, the scenario or the Engine, so that no Observation given to the Gemini_Driver contains the API_Key as a substring.

### Requirement 8: 6.8 Select Gemini in the CLI

**User Story:** As the operator, I want `--driver gemini` to run the scenario with Gemini, so that I can record a live run with a Gemini key.

#### Acceptance Criteria

6.8.1. THE CLI SHALL accept `gemini` as a value of `--driver`, in addition to `scripted` and `llm`, and SHALL keep `scripted` as the default value.
6.8.2. WHEN `--driver gemini` is given and `AGENT_MODEL` and `GEMINI_API_KEY` both hold at least one non-whitespace character, THE CLI SHALL call the Client_Factory exactly once with the whitespace-stripped `GEMINI_API_KEY` value, build the Gemini_Driver with the returned Gemini_Client and the whitespace-stripped `AGENT_MODEL` value, and run the scenario once with the Gemini_Driver.
6.8.3. IF `--driver gemini` is given and `AGENT_MODEL` or `GEMINI_API_KEY` is absent, empty or whitespace-only, THEN THE CLI SHALL print exactly one stderr message that names each missing variable by name only, in the order `AGENT_MODEL` then `GEMINI_API_KEY`, and SHALL return exit code 1 without calling the Client_Factory, without calling any Gemini_Client, without running the scenario, without printing a timeline to stdout, and without writing a Replay.
6.8.4. WHEN a Gemini run reaches a final status, THE CLI SHALL print the timeline, the status line and the outbox count to stdout and SHALL return exit code 0. WHERE `--out PATH` is also given, the CLI SHALL write the Replay to PATH and keep the same exit codes it uses for the other drivers: 0 when the write succeeds, 1 when it fails.
6.8.5. IF the Client_Factory raises an exception, THEN THE CLI SHALL print exactly one stderr line, `error: <ExceptionType> while building the Gemini client`, where `<ExceptionType>` is the unqualified class name of the exception, so the line contains no API_Key, SHALL return exit code 1, and SHALL neither run the scenario nor write a Replay.
6.8.6. IF the scenario run with the Gemini_Driver raises an exception, THEN THE CLI SHALL behave as Requirement 6.10 states.

### Requirement 9: 6.9 Label live runs with their provider

**User Story:** As a judge, I want every live replay to name its provider, so that scripted runs, Gemini runs and Anthropic runs are never confused.

#### Acceptance Criteria

6.9.1. THE Gemini_Driver SHALL expose a driver label whose value is exactly the string `llm`, with no other value possible for any configuration of the Gemini_Driver.
6.9.2. WHEN the CLI writes a run driven by the Gemini_Driver as a Replay, THE CLI SHALL write exactly `llm` as the `driver` value in the data of the `RUN_STARTED` event.
6.9.3. WHEN the CLI writes a run driven by the Gemini_Driver as a Replay, THE CLI SHALL write exactly `llm` as the `driver` value of the Replay meta, equal to the `driver` value in the `RUN_STARTED` event of the same Replay.
6.9.4. WHEN a Replay of a run driven by the Gemini_Driver is loaded, THE existing replay validation SHALL accept it without any change to the validation code and without any driver value other than `scripted` or `llm`.
6.9.5. IF a run is driven by the Gemini_Driver, THEN THE CLI SHALL NOT write `scripted` as the `driver` value in either the `RUN_STARTED` event or the Replay meta of that run's Replay.
6.9.6. THE Gemini_Driver SHALL expose the Provider `gemini`, and THE Anthropic_Driver SHALL expose the Provider `anthropic`.
6.9.7. WHEN the Scenario builds a Replay for a run driven by a driver whose label is `llm` and whose Provider is `gemini` or `anthropic`, THE Scenario SHALL set the Replay id to `<Base_Id>-<Provider>`, for example `poisoned-briefing-enforced-gemini`, `poisoned-briefing-enforced-anthropic`, `poisoned-briefing-unenforced-gemini` and `poisoned-briefing-unenforced-anthropic`.
6.9.8. WHEN the Scenario builds a Replay for a run driven by a driver whose label is `llm` and whose Provider is `gemini` or `anthropic`, THE Scenario SHALL set the Replay title to `<Base_Title> (<Provider_Name> live LLM)`, for example `Poisoned briefing: limits enforced (Gemini live LLM)`.
6.9.9. WHEN the Scenario builds a Replay for a run driven by a driver whose label is `llm` and whose Provider is `gemini` or `anthropic`, THE Scenario SHALL write the Provider_Field with the value of that Provider, and `meta.driver` SHALL stay `llm`.
6.9.10. WHEN the Scenario builds a Replay for a run driven by a driver whose label is `scripted`, THE Scenario SHALL write no Provider_Field and SHALL keep the id and title equal to those at the Baseline_Commit, so that recorded scripted replays stay byte-identical.
6.9.11. IF a driver whose label is `llm` exposes no Provider, THEN THE Scenario SHALL keep the Baseline_Commit id `<Base_Id>-llm` and title `<Base_Title> (live LLM)` and SHALL write no Provider_Field.
6.9.12. THE Scenario SHALL give a Gemini run and an Anthropic run of the same run variant different Replay ids and different Replay titles.
6.9.13. THE Provider_Field SHALL be documented as an optional replay format addition, absent on scripted replays, that needs an owner-applied amendment to CONTRACTS section 9; this spec SHALL NOT edit `docs/CONTRACTS.md`.

### Requirement 10: 6.10 Report Gemini call failures safely

**User Story:** As the operator, I want a failed Gemini call to stop the run with a safe message, so that an error never prints a secret.

#### Acceptance Criteria

6.10.1. IF the scenario run with the Gemini_Driver raises an exception of type `Exception` or any subclass after the Client_Factory has returned, THEN THE CLI SHALL print exactly one line to stderr, `error: run aborted: <ExceptionType> (details withheld; see docs)`, where `<ExceptionType>` is the unqualified class name of the exception, and SHALL return exit code 1.
6.10.2. IF the scenario run with the Gemini_Driver raises an exception, THEN THE CLI SHALL write no Replay, including when `--out PATH` was given, and SHALL leave any file already at PATH unchanged.
6.10.3. IF the scenario run with the Gemini_Driver raises an exception, THEN THE CLI SHALL print nothing to stdout: no timeline header, no event lines, no `status:` line and no `outbox:` line.
6.10.4. IF the scenario run with the Gemini_Driver raises an exception, THEN THE CLI SHALL print no traceback and no part of the exception's message or arguments, so the API_Key never appears on stdout or stderr.

### Requirement 11: 6.11 Respect the driver isolation invariants

**User Story:** As the owner, I want the Gemini_Driver to be as isolated as the other drivers, so that the security invariants keep holding.

#### Acceptance Criteria

6.11.1. `drivers/llm.py`, which holds the Gemini_Driver and the Client_Factory, SHALL contain no import of the `engine`, `identity`, `place` or `tools` modules, or of any name defined in them, in any of these forms: absolute (`telepermit.engine`), relative (`..engine`), `from telepermit import engine`, or an import placed inside a function body (security invariant 2).
6.11.2. THE Gemini_Driver SHALL build every request body it passes to the Gemini_Client only from the fields of the current and earlier Observations, the earlier replies of the Gemini_Client, and fixed text: text that is defined as a constant in the Gemini_Driver module and does not change with run state.
6.11.3. THE Gemini_Driver SHALL send no request body that contains the permit or any permit field value, the spend, a tool cost, the step count, the step limit, the API_Key or any other key (security invariant 9).
6.11.4. WHEN the Gemini_Driver is asked for its next action, THE Gemini_Driver SHALL return exactly one Proposal and SHALL make no call to `Engine.step`, `Engine.run` or `Place.execute`.
6.11.5. THE Gemini_Driver SHALL hold no reference to an Engine, Place, Tool or Authority object, in its constructor arguments or in its attributes.
6.11.6. `drivers/llm.py` SHALL keep a module docstring, placed as the first statement, that names CONTRACTS section 7, and SHALL keep `from __future__ import annotations`.
6.11.7. IF `drivers/llm.py` contains an import that 6.11.1 forbids, THEN `tests/test_architecture.py` SHALL fail and name the offending module and the imported name.

### Requirement 12: 6.12 Test offline with a Fake_Client

**User Story:** As the owner, I want the tests to run without a network or a key, so that CI stays free and deterministic.

#### Acceptance Criteria

6.12.1. THE test suite SHALL exercise the Gemini_Driver and the `--driver gemini` CLI path only through a Fake_Client or a replaced Client_Factory, and SHALL test the real Gemini_Client returned by the Client_Factory only with its URL-opening call replaced by a test stand-in that returns a prepared reply.
6.12.2. WHILE any test that uses the Gemini_Driver, the Client_Factory or the `--driver gemini` CLI path runs, THE test suite SHALL fail that test with an error naming the blocked operation on any attempt to open a network connection or resolve a host name. The guard SHALL live in the new Gemini test files or in a new `conftest.py` under a new test sub-folder, so that existing test files stay unchanged (6.13.6).
6.12.3. THE test suite SHALL fail if any module of the `telepermit` package imports `urllib` or a `urllib` submodule anywhere except the Client_Factory function body (including at module level), if the Client_Factory body holds no such import, or if any test module imports `urllib` or a `urllib` submodule.
6.12.4. THE test suite SHALL include a property test that runs at least 200 generated cases of 1 to 6 turns each. The generated Observations and Fake_Client replies SHALL cover replies with no candidates, text-only parts, exactly one Function_Call, and 2 or more Function_Calls; Function_Call names `go`, `finish`, a Place_Tool name and an unknown name; and `args` that are present, missing, or not an object. The test SHALL check that each returned Proposal equals the Proposal defined by Requirements 6.2 and 6.3, that the Fake_Client is called exactly once per turn, and that stand-ins replacing `Engine.step`, `Engine.run` and `Place.execute` record zero calls.
6.12.5. THE test suite SHALL include a property test that runs at least 200 generated cases of 1 to 6 turns each. The test SHALL check that every request sent to the Fake_Client holds a History satisfying 6.4.1 to 6.4.5, 6.4.7, 6.4.9 and 6.4.10. For generated Observations whose text fields contain no Banned_Word, the test SHALL also check that no request body contains a Banned_Word when compared in lower case.
6.12.6. THE test suite SHALL include a test that attempts one host name lookup under the guard of 6.12.2 and passes only when the guard blocks that attempt.
6.12.7. WHEN a test runs the `--driver gemini` CLI path, THE test suite SHALL set `GEMINI_API_KEY` and `AGENT_MODEL` to fixed fake values for that test only and SHALL restore the previous environment after the test, so that the suite gets the same pass/fail result whether or not real values are set before it starts.

### Requirement 13: 6.13 Keep the rest of the system unchanged

**User Story:** As the owner, I want this add-on to touch only the driver and the CLI, so that the merged runtime and its tests stay as they are.

#### Acceptance Criteria

6.13.1. THE change SHALL leave `engine.py`, `place.py`, `tools.py`, `audit.py`, `permit.py`, `identity.py`, `clock.py` and every file under `frontend/` byte-identical to the Baseline_Commit, and SHALL change the Scenario only where Requirement 6.9 needs it: the Replay id, title and meta, and how a run records the Provider of its driver.
6.13.2. THE change SHALL limit modified source files to `drivers/llm.py`, `cli.py` and the Scenario within 6.13.1, plus new test files, test edits allowed by 6.13.6, and documentation, so that a diff against the Baseline_Commit lists no other source file, adds no new module under `src/`, and requires no edit to `tech.md` or `structure.md`.
6.13.3. THE change SHALL leave `pyproject.toml` and the lock file without any added, removed or re-versioned dependency, in core dependencies and in every optional extra.
6.13.4. THE change SHALL import only Python standard-library modules and packages already declared in `pyproject.toml` at the Baseline_Commit.
6.13.5. WHEN the CLI runs with `--driver scripted` or `--driver llm` and the same other arguments as at the Baseline_Commit, THE CLI SHALL produce the same audit events, the same exit code and the same Replay meta as at the Baseline_Commit, except for the `--driver llm` Replay id, title and Provider_Field that Requirement 6.9 sets.
6.13.6. THE change SHALL leave every test file that exists at the Baseline_Commit byte-identical, with two exceptions: `tests/test_architecture.py` MAY gain new checks for the new code without changing or removing any existing check; and the assertions of `tests/unit/test_cli.py::test_llm_out_replay_is_labelled_llm` that expect the id `poisoned-briefing-enforced-llm` and a title ending `(live LLM)` SHALL, only with owner approval, be changed to expect `poisoned-briefing-enforced-anthropic`, a title ending `(Anthropic live LLM)` and Provider_Field `anthropic`, keeping its other assertions. Every other test that passes at the Baseline_Commit SHALL still pass, with no test skipped, xfailed or deleted.
6.13.7. WHEN the full backend suite runs after the change, THE suite SHALL report a passed-test count no lower than the baseline count, `tests/test_architecture.py` SHALL pass, and `ruff check` and `ruff format --check` SHALL report no errors.
