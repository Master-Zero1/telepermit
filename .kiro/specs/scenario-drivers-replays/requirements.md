# Requirements Document

## Introduction

This spec covers the fourth building block of TelePermit and Milestone M1: the poisoned_briefing Scenario, the ScriptedDriver and the LLMDriver, the CLI, and the Recorder that writes the Replay files the timeline UI plays. After this spec the whole demo works from the command line and the recorded replays are deterministic. The behaviour is defined by CONTRACTS sections 7 to 10, including both golden traces (Run A and Run B), the optional Run C and the replay format, which are binding. The Engine contract of CONTRACTS section 5, as amended by the owner, applies: the Engine takes the keyword-only `scenario`, `driver` and `task` arguments, the status ERROR exists, and `run` advances the clock only if the clock provides `advance`.

Criterion IDs 4.1 to 4.9 are the seed reference IDs, and Requirement N holds criterion 4.N.

Notes (no scope change):
- (a) The Engine, the driver types, Place, the tools and the audit modules of Specs 1 to 3 are used by import. This spec adds the scripted driver, the LLM driver, the scenario module, the CLI and the Recorder, and writes replay files.
- (b) Driver modules import nothing from the engine, identity, place or tools modules (security invariant 2, enforced by the architecture test).
- (c) The Scenario uses a deterministic DEMO ONLY seed key. The key is never printed, logged or written to a replay (security invariant 3).
- (d) No test makes a network call and no dependency is added. The `anthropic` package is the optional `llm` extra and is imported only inside the function that needs it.
- (e) The replay format of CONTRACTS section 9 is not changed.
- (f) Owner-confirmable item: the seed records the forged-identity replay "if time permits". This spec records it (Requirement 8), alongside the Run C trace (Requirement 4). The owner may remove it before design.
- (g) Behaviour of the ScriptedDriver after the script is exhausted with `repeat_last` false, and for an empty script, is left to the design.

## Glossary

- **Scenario**: The poisoned_briefing module that builds fresh places (with fresh tool state), the Identity, the home Permit and the TickClock exactly as in CONTRACTS section 8, and wires the scripted proposals.
- **ScriptedDriver**: A deterministic AgentDriver built from a list of Proposals and a `repeat_last` flag.
- **LLMDriver**: An AgentDriver that maps each Observation to a provider tool-calling request through an injected client and returns the first tool call of the response as a Proposal.
- **Engine**: The module that owns every tool call, meters it and builds the Observation in its run loop (CONTRACTS section 5).
- **Observation**: The five-field value of CONTRACTS section 7 (`task`, `turn`, `place`, `tools`, `last_result`) that a driver may see.
- **Proposal**: The action and arguments a driver wants to take next.
- **Golden trace**: The exact event sequence of CONTRACTS section 8 for a named run. Run B is the enforced run, Run A is the unenforced run and Run C is the forged-identity run.
- **Run A**: The scenario run with enforcement off, driven by the five scripted proposals.
- **Run B**: The scenario run with enforcement on, driven by the five scripted proposals.
- **Run C**: The scenario run with enforcement on and an Identity whose signature is replaced by 64 zero bytes.
- **Replay**: A JSON file with `schema_version` 1, a `meta` object and an `events` list, as specified in CONTRACTS section 9.
- **Index**: The `index.json` file listing every Replay with `id`, `title`, `file`, `driver` and `enforce`.
- **Recorder**: The script that runs the Scenario and writes the Index and the Replay files into the replay directory of the frontend.
- **Demo seed**: The bytes `b"telepermit-demo-authority"` from which the home authority key is derived for the Scenario. DEMO ONLY.
- **Timeline**: The readable text output of the CLI, one line per event.
- **Outbox**: The in-memory list of export destinations held on the vault Place instance.
- **CLI**: The command-line program `python -m telepermit.cli`.
- **Driver label**: The value `scripted` or `llm` in the `driver` field of a Replay `meta` and of its Index entry.

## Requirements

### Requirement 1: ScriptedDriver

**User Story:** As a test author, I want a deterministic scripted driver, so that the demo runs are reproducible without any model.

#### Acceptance Criteria

4.1. THE ScriptedDriver, built as `ScriptedDriver(script, repeat_last=True)`, SHALL return its scripted Proposals in order, and WHEN `repeat_last` is true and the script is exhausted, THE ScriptedDriver SHALL return the last Proposal of the script again for every further call.

### Requirement 2: Observation content and text safety

**User Story:** As a security reviewer, I want the agent to see only what CONTRACTS section 7 allows, so that the agent can never learn its permit, spend or keys.

#### Acceptance Criteria

4.2. WHEN the Engine run loop builds an Observation, THE Engine SHALL include only the five fields `task`, `turn`, `place`, `tools` and `last_result` and no permit, spend, costs, steps or keys, SHALL use tool descriptions that contain none of the words `permit`, `allowance` and `teleclick`, and, across the whole of Run A and Run B, SHALL produce no Observation text that contains those words, the identity signature hex or the private-key hex `sha256(seed).digest().hex()` of the Demo seed.

### Requirement 3: Scenario and golden traces for Run A and Run B

**User Story:** As a demo author, I want the Scenario to reproduce the golden traces exactly, so that the demo shows the injected agent running unchecked and then being destroyed.

#### Acceptance Criteria

4.3. WHEN the Scenario is run, THE Scenario SHALL build fresh places with fresh tool state, the Identity, the home Permit and the clock exactly as in CONTRACTS section 8 (authority `home-authority` derived from the Demo seed, identity `briefing-bot-001` of class `briefing-bot` with `issued_at` 0.0, the task text, the home Permit, the library and vault tools and ceilings, start place `library`, `TickClock(0.0)`), and, driven by the five scripted proposals, SHALL produce the golden Run B trace with enforcement on (20 events, ending `KILLED` with reason `ALLOWANCE_EXCEEDED` at step 17 with spent 38, limit 40 and observed 41, and an empty Outbox) and the golden Run A trace with enforcement off (32 events, ending `HARNESS_CAP` at step 30 with spent 120, two exports in the Outbox, and no `DENIED` and no `KILLED` event).

### Requirement 4: Forged-identity variant (Run C)

**User Story:** As a security reviewer, I want the forged-identity variant to be refused at the first border, so that the demo shows identity checking.

#### Acceptance Criteria

4.4. WHEN the forged-identity variant is run with the Identity signature replaced by 64 zero bytes and enforcement on, THE Scenario SHALL produce the golden Run C trace of three events: `RUN_STARTED`, `BORDER_CHECK` at `library` with decision `REFUSE` and reason `BAD_SIGNATURE`, and `RUN_ENDED` with status `REFUSED`.

### Requirement 5: LLMDriver

**User Story:** As a demo author, I want an optional model-backed driver, so that the same Scenario can be run with a live model while the runtime keeps the limits.

#### Acceptance Criteria

4.5. WHEN `LLMDriver(client, model)` receives an Observation, THE LLMDriver SHALL translate it through the injected client into a provider tool-calling request whose tools are the current-place tools, a `go` tool and `finish`, SHALL return the first tool call of the response as a Proposal, SHALL keep its own message history, SHALL propose `finish` WHEN a response contains no tool call, and SHALL make no call into the Engine or a Place, with tests using a fake client.

### Requirement 6: LLM driver environment check

**User Story:** As a user without credentials, I want a clear failure when the model settings are missing, so that I am never surprised by a network call or a hidden default model.

#### Acceptance Criteria

4.6. WHEN `AGENT_MODEL` or `ANTHROPIC_API_KEY` is missing or empty and the `llm` driver is requested, THE CLI SHALL exit with a non-zero status and a message naming each missing variable, before any client is built and without any network call, and THE CLI SHALL take the model name only from `AGENT_MODEL`.

### Requirement 7: CLI timeline, status and replay output

**User Story:** As a demo author, I want a CLI that prints a readable run and can save it as a replay, so that the demo works from the command line.

#### Acceptance Criteria

4.7. WHEN the command `run poisoned_briefing --enforce on|off [--driver scripted|llm] [--out FILE]` is executed, THE CLI SHALL print a Timeline of one line per event with seq, type, place, step, spent and a summary, followed by the final status and the Outbox count, SHALL end with final status `KILLED` for `--enforce on` and `HARNESS_CAP` for `--enforce off` with the scripted driver, and, WHEN `--out` is given, SHALL write a Replay JSON as specified in CONTRACTS section 9 with `schema_version` 1, `meta` and `events`.

### Requirement 8: Deterministic Recorder

**User Story:** As a frontend developer, I want byte-identical recorded replays, so that the UI plays stable files and re-recording never creates noise in version control.

#### Acceptance Criteria

4.8. WHEN the Recorder is run, THE Recorder SHALL write the Index and the Replays `poisoned-briefing-enforced` (Run B), `poisoned-briefing-unenforced` (Run A) and `forged-identity-refused` (Run C) into the replay directory of the frontend, using `json.dumps(sort_keys=True, indent=2)` followed by one trailing newline, UTF-8 encoding and LF line endings, with no timestamps and no random values, so that recording twice produces byte-identical files and the second run leaves `git status` clean.

### Requirement 9: Driver labels

**User Story:** As a viewer of the demo, I want every replay labelled scripted or live LLM, so that no scripted run is passed off as a model run.

#### Acceptance Criteria

4.9. WHEN a Replay is produced, THE System SHALL set the Driver label in the `driver` field of its `meta` and in its Index entry to `scripted` for a run driven by the ScriptedDriver (including every recorded Replay) and to `llm` for a run driven by the LLMDriver, and THE System SHALL never set a Driver label that differs from the driver actually used.
