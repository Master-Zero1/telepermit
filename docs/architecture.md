# Architecture

Names, numbers and behaviour are fixed in [CONTRACTS.md](CONTRACTS.md). This file explains how the parts fit together. Where this file and CONTRACTS.md differ, CONTRACTS.md wins.

Telescript facts used here are limited to the list in the README. Everything about how the engine, places and permits work below is TelePermit's own design.

## Components

| Component | File | Role |
|---|---|---|
| Permit | `permit.py` | Immutable limits: `lifetime_s`, `max_steps`, `allowance` (teleclicks), `allowed_actions`. `narrowed_by(ceiling)` takes the minimum of each number and the intersection of the actions. |
| Identity and Authority | `identity.py` | An `Authority` holds an Ed25519 private key and issues signed `Identity` values. `verify_identity` checks a signature against trusted public keys and never raises. |
| Tools | `tools.py` | Simulated tools with fixed costs: `read_document` 1, `search_archive` 5, `read_records` 3, `export_records` 20. `go:<place>` costs `GO_COST` (1). |
| Place | `place.py` | A named set of tools, a ceiling permit, trusted authorities and allowed agent classes. `admit()` decides ADMIT, ADMIT_IMPOSED or REFUSE. `execute()` runs a tool. |
| Clock | `clock.py` | `Clock` protocol and `TickClock`. The demo advances 1.0 simulated second per driver turn (`TICK_S`). |
| Engine | `engine.py` | Owns the run. Checks limits, meters, executes tools, moves the agent across borders, emits audit events, kills the agent on a breach. |
| Audit | `audit.py` | Event models, `reduce_events`, replay and index documents, JSON writer. |
| Drivers | `drivers/` | `base.py` defines `Observation`, `Proposal` and the `AgentDriver` protocol. `scripted.py` plays a fixed list of actions. `llm.py` maps an observation to a tool-calling request through an injected client. |
| Scenario | `scenarios/poisoned_briefing.py` | The demo: two places, one agent, one injected document. |
| CLI | `cli.py` | Runs the scenario, prints a timeline, optionally writes a replay file. |
| Recorder | `scripts/record_replays.py` | Writes the three replay files and `index.json`. |
| Timeline UI | `frontend/src/` | Loads the replay files, validates them, and plays them back. It never runs the engine. |

## Event flow

Each step of the engine does the following, in this order (CONTRACTS section 5, enforcement on):

1. The driver receives an `Observation` (task, turn, current place, available tools, last result) and returns a `Proposal` (action and arguments).
2. The engine checks lifetime. Past `lifetime_s` kills the agent.
3. `finish` ends the run. It costs nothing and uses no step.
4. The engine checks the step limit. One step over kills the agent.
5. The step is counted. Denied attempts also use a step.
6. An action not in the permit is logged as `DENIED` (`NOT_IN_PERMIT`). The agent stays alive.
7. A tool the current place does not have, or a `go` to an unknown place or the current place, is logged as `DENIED` (`NOT_IN_PLACE`).
8. The engine checks `spent + cost` against the allowance before anything runs. A breach kills the agent and the action never executes.
9. The cost is added to `spent`.
10. A tool call runs through `Place.execute` and is logged as `TOOL_CALL`.
11. A `go:<place>` call asks the destination place to admit the agent. On ADMIT or ADMIT_IMPOSED the agent moves and its permit becomes `permit_after`. On REFUSE it stays where it is. The cost of 1 is charged either way.

A kill emits `KILLED` then `RUN_ENDED` and nothing else ever runs. With enforcement off, steps and spend are still metered and logged, but nothing is denied for permit reasons, nothing is killed, and a border move is logged as `ADMIT` with reason `UNENFORCED`.

Every state change emits exactly one event, with `seq` counting up from 0 with no gaps. `reduce_events` rebuilds the final place, step, spend, permit and status from the events alone. The UI uses a TypeScript copy of the same function.

## Trust boundary

```
 untrusted: the agent (model or script), documents it reads, tool results it is shown
 -------------------------------------------------------------------------------
 trusted:   engine.py, place.py, permit.py, identity.py (Authority), audit.py
```

- The driver sees only an `Observation`. It never sees the permit, the spend, the costs, the step count or any key. The text a denied action returns does not mention permits or limits.
- Only `engine.py` calls `Place.execute`. No other module runs a tool.
- Modules under `drivers/` never import the engine, the signing code (`Authority`) or tool executors.
- The private key stays inside the `Authority` object. It does not appear in logs, observations, replays or error messages.
- `backend/tests/test_architecture.py` parses imports with `ast` and fails if the first two rules are broken. Property tests cover the counter, permit and event rules.

The demo key is derived from a public seed so replays are reproducible. It is for the demo only and protects nothing.

## Data flow to the browser

The backend writes replay files. The UI fetches them with relative URLs (`./replays/index.json`, then each replay file) and makes no other network request. The files are static JSON, so the demo runs on a static host with no backend and no API key. Recording twice produces byte-identical files.

## File map

```
.
├── .github/workflows/     ci.yml (backend lint and tests, frontend build and tests), pages.yml (deploy)
├── .kiro/                 steering/, specs/, hooks/
├── backend/
│   ├── pyproject.toml
│   ├── src/telepermit/    permit, identity, tools, place, audit, engine, clock, cli
│   │   ├── drivers/       base, scripted, llm
│   │   └── scenarios/     poisoned_briefing
│   └── tests/             unit/, properties/, test_architecture.py, test_replays.py
├── frontend/
│   ├── public/replays/    index.json and the three recorded runs
│   └── src/               loader, validate, reduce, playback, pair, meters and the other pure
│                          modules with their tests; components/ holds the React views
├── scripts/record_replays.py
├── docs/                  CONTRACTS, architecture, threat-model, BUILD_PLAN, PROGRESS, kiro-journal
├── LICENSE, README.md, .env.example
```
