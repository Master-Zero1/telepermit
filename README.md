# TelePermit

TelePermit brings back Telescript's permit system (General Magic, 1994) as a runtime that bounds LLM agents: an engine owns every tool call, meters it, checks the agent at place borders, and destroys it the moment it exceeds a limit.

Live demo: LIVE_URL_HERE (runs in the browser, no API key, no backend).

Built for Kiroween 2026, Resurrection category.

## Why this exists

LLM agents now hold real credentials. A limit written in a prompt is not a control, because the model can be talked out of it, for example by a document it reads. In TelePermit the limits live in the runtime. The agent never sees its permit, its spend or any key, so there is nothing in its context to argue with.

The demo shows one run twice. A briefing document carries an injected instruction to export records from a vault. With enforcement on, the engine refuses the export and kills the agent when it exceeds its allowance, and the audit log shows why. With enforcement off, the same scripted run exports the records and keeps going until the test harness stops it.

## Quickstart

Needs git, Python 3.11 or newer with [uv](https://docs.astral.sh/uv/), and Node 20.

1. Clone:

```
git clone https://github.com/Master-Zero1/telepermit.git
```

2. Run the scenario from the command line (enforcement on, scripted agent):

```
cd telepermit/backend
uv sync --extra dev
uv run python -m telepermit.cli run poisoned_briefing --enforce on
```

3. Open the timeline UI:

```
cd telepermit/frontend
npm ci
npm run dev
```

Use `--enforce off` in step 2 to see the unenforced run. `npm run dev` starts a dev server and serves the recorded replays from `frontend/public/replays/`.

Command status: the CLI flags and npm scripts above were read from `backend/src/telepermit/cli.py` and `frontend/package.json`. I did not run the quickstart end to end when writing this file, so treat it as unverified until you do.

## Tests

| Suite | Command | Result |
|---|---|---|
| Backend | `uv --directory backend run pytest -q` | 329 passed |
| Frontend | `npm --prefix frontend test` | 18 test files passed, 201 tests passed |
| Frontend build | `npm --prefix frontend run build` | green |

These results were run and reported by the repository owner. Backend lint is `uv --directory backend run ruff check .` (unverified here). CI runs the same checks in `.github/workflows/ci.yml`.

`npm audit` reports 3 findings, all in dev tooling (vitest and its dependencies). It reports none in production dependencies. The fix is a breaking vitest upgrade, which has not been applied.

## What is real and what is scripted

- The agent in every recorded replay is scripted. It is a fixed list of actions that plays the part of an agent that obeyed the injected instruction. Each replay is labelled "scripted" in the UI. A replay would say "live LLM" only if it were recorded with the LLM driver. None is.
- Live LLM check: not run. The optional LLM driver (`--driver llm`) was only tested against a fake client. Its request mapping follows the Anthropic documentation and has not been exercised against the live service. The optional driver needs the `llm` extra, `ANTHROPIC_API_KEY` and `AGENT_MODEL` set in the environment (unverified: the exact install command, for example `uv sync --extra dev --extra llm`).
- All tools are simulated. Nothing is sent anywhere. The "export" appends to an in-memory list.
- Lifetime is simulated time: the demo clock advances 1.0 second per agent turn.

## Architecture

```
  driver (scripted or LLM)          sees only an Observation, returns a Proposal
        |   Observation / Proposal
        v
  +-----------------------------------------------------------+
  | Engine (the only module that executes tools)              |
  |   check lifetime -> steps -> permit -> place -> allowance |
  |   meter step and spend, then run the tool                 |
  |   emit exactly one audit event per state transition       |
  +-----------------------------------------------------------+
        |                       |
        | go:<place>            | tool call
        v                       v
  Place.admit()            Place.execute()
  verify Ed25519 identity  library: read_document, search_archive
  check agent class        vault:   read_records, export_records
  narrow the permit
  ADMIT / ADMIT_IMPOSED / REFUSE
        |
        v
  audit log (events) -> replay JSON -> timeline UI (browser)
```

Details are in [docs/architecture.md](docs/architecture.md). The names, numbers and behaviour are fixed in [docs/CONTRACTS.md](docs/CONTRACTS.md).

## Telescript facts

Only the claims below are made about Telescript.

### Verified

- Announced 1994 by General Magic.
- Agents "go" to "places" under permits and authorities.
- A permit capped lifetime, size and total spend ("allowance", counted in teleclicks). The engine destroyed an agent the instant it exceeded a limit.
- Identity carried an unforgeable cryptographic authority.
- A place inspected an arriving agent's identity, permit and class, then refused it, or admitted it only after imposing a permit.
- Agents interacted only inside the same place.

### Interpretation

- Interpretation: it died with its ecosystem (flopped devices, AT&T shut PersonaLink, its only place, in 1996, slow modems), not because permits failed.

### Our design choices (not Telescript behaviour)

- Step limit and the allowed-actions list.
- Ed25519 as the signature mechanism.
- Pre-flight limit checks.
- Denied actions are refused and logged without killing the agent.
- An imposed permit is the component-wise minimum of the requested permit and the place's ceiling.
- REFUSE when the agent's counters already exceed a ceiling.
- Tool costs.
- The "size" cap is not implemented.
- The same-place interaction rule is not implemented. The demo has one agent.

## Threat model summary

A permit stops an agent from doing more than it was allowed to do. It does not judge whether what the agent does inside its allowance is a good idea.

What permits stop (examples, all in the demo or in tests):

- Spending past the allowance. The enforced replay ends in `KILLED ALLOWANCE_EXCEEDED` at 41 against a limit of 40.
- Using an action the permit or the current place does not offer. The export is logged as `DENIED` and does not run.
- A forged or untrusted identity at a border. The forged-identity replay ends in `REFUSED`.

What permits do not stop:

- An injection that stays inside the permit. If a permit allows an action and the allowance covers it, the engine runs it, whatever the document told the agent to do. In this demo the export is blocked because the Vault's ceiling does not list `export_records`, not because the engine recognises an injection. If the Vault listed it, the first export (cost 20) would run, because the agent arrives with 2 spent and 22 is under the limit of 40. The second would be killed at 42.
- Harmful arguments to an allowed action. The engine does not inspect what an agent exports or where it sends it.
- A compromised host or a changed engine. The engine is the trust boundary.

Full detail, with the invariants list, is in [docs/threat-model.md](docs/threat-model.md).

## How Kiro was used

- Specs: five specs in `.kiro/specs/` (permit-identity, tools-places-admission, engine-audit, scenario-drivers-replays, timeline-ui), each written requirements first, then design, then tasks.
- Property-based tests: Hypothesis properties, named P<n>.<m> in the specs, cover the engine, permits, identity, places, drivers and replays. The UI has its own property tests under vitest.
- Steering: seven always-on files in `.kiro/steering/` (product scope, quality bar, security invariants, structure, tech, Telescript facts, workflow).
- Hooks: five hooks in `.kiro/hooks/` (property-guard, invariant-review, fact-guard, spec-sync, journal).
- Journal: a dated, factual log of what worked and what went wrong is in [docs/kiro-journal.md](docs/kiro-journal.md).

Planning documents (steering files, spec briefs, PRD and roadmap) were drafted with external AI assistants (Claude via claude.ai, and Antigravity) before building. All specs, code and tests in this repository were produced and run in Kiro.

## Demo-only key

The scenario signs the agent's identity with a deterministic Ed25519 key derived from a public seed (`telepermit-demo-authority`). It exists so replays are byte-for-byte reproducible. Anyone can derive it, so it protects nothing. Do not reuse this pattern for a real authority.

## Repository

- `backend/`: Python package `telepermit` (permit, identity, tools, place, engine, audit, drivers, scenario, CLI) and its tests.
- `frontend/`: Vite, React and TypeScript timeline UI. Plain CSS, no external network requests.
- `scripts/record_replays.py`: records the replay files in `frontend/public/replays/`.
- `docs/`: contracts, architecture, threat model, build plan and the Kiro journal.

## Licence

MIT. See [LICENSE](LICENSE).
