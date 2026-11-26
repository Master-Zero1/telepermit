# TelePermit

TelePermit brings back Telescript's permit system (General Magic, 1994) as a runtime that bounds LLM agents: an engine owns every tool call, meters it, checks the agent at place borders, and destroys it the moment it exceeds a limit.

Live demo: https://master-zero1.github.io/telepermit/ (runs in the browser, no API key, no backend).

Built for Kiroween 2026, Resurrection category.

## Quickstart

Needs git, Python 3.11 or newer with [uv](https://docs.astral.sh/uv/), and Node 20. Lines marked `unverified` have not been run by the author of this README.

### Windows PowerShell

```powershell
git clone https://github.com/Master-Zero1/telepermit.git
cd telepermit
cd backend
uv sync --extra dev   # unverified
uv run python -m telepermit.cli run poisoned_briefing --enforce on
cd ../frontend
npm ci
npm run dev   # unverified
```

### bash (Linux, macOS, Git Bash)

```bash
git clone https://github.com/Master-Zero1/telepermit.git
cd telepermit
cd backend
uv sync --extra dev   # unverified
uv run python -m telepermit.cli run poisoned_briefing --enforce on
cd ../frontend
npm ci
npm run dev   # unverified
```

The `cli` line prints the audit timeline of the scripted run with enforcement on. Use `--enforce off` for the unenforced run. `npm run dev` serves the recorded replays from `frontend/public/replays/`.

## Why this exists

LLM agents now hold real credentials. A limit written in a prompt is not a control, because the model can be talked out of it, for example by a document it reads. In TelePermit the limits live in the runtime. The agent never sees its permit, its spend or any key, so there is nothing in its context to argue with.

The demo runs one scenario twice. A briefing document carries an injected instruction to export records from a vault.

- Enforcement on (20 events): the agent crosses into the Vault under a narrower imposed permit. The export is denied twice. The agent keeps reading records until `spent + cost` would be 41 against a limit of 40, and the engine kills it with `ALLOWANCE_EXCEEDED`. Nothing is exported.
- Enforcement off (32 events): the same script exports twice, then keeps reading records until the test harness stops it at step 30 with 120 teleclicks spent.

The replay viewer plays both side by side and shows why the engine acted.

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

Every mechanism in this diagram is TelePermit's own design. See the next section for what is and is not from Telescript. Components, event flow, trust boundary and file map are in [docs/architecture.md](docs/architecture.md). Names, numbers and behaviour are fixed in [docs/CONTRACTS.md](docs/CONTRACTS.md).

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

Scope note: TelePermit does not implement the same-place interaction rule. The demo has one agent.

## Threat model summary

A permit stops an agent from doing more than it was allowed to do. It does not judge whether what the agent does inside its allowance is a good idea.

What permits stop (examples, all in the demo or in tests):

- Spending past the allowance. The enforced replay ends in `KILLED ALLOWANCE_EXCEEDED`, observed 41 against a limit of 40.
- An action the permit or the current place does not offer. The export is logged as `DENIED` and does not run.
- A forged or untrusted identity at a border. The forged-identity replay ends in `REFUSED`.

What permits do not stop:

- An injection that stays inside the permit. If a permit allows an action and the allowance covers it, the engine runs it, whatever the document told the agent to do. In this demo the export is blocked because the Vault's ceiling does not list `export_records`, not because the engine recognises an injection. If the Vault listed it, one export (cost 20) would run, because the agent arrives with 2 spent and 22 is under the limit of 40. A second export would be killed at 42.
- Harmful arguments to an allowed action. The engine does not inspect what an agent exports or where it sends it.
- A compromised host or a changed engine. The engine is the trust boundary.

Full detail, with the nine invariants, is in [docs/threat-model.md](docs/threat-model.md).

## Testing

| Suite | Command | Result |
|---|---|---|
| Backend | `uv --directory backend run pytest -q` | 441 passed |
| Frontend | `npm --prefix frontend test` | 18 test files, 201 tests passed |
| Frontend build | `npm --prefix frontend run build` | green |
| Backend lint | `uv --directory backend run ruff check --config pyproject.toml . ../scripts` | All checks passed |
| Backend format | `uv --directory backend run ruff format --check --config pyproject.toml . ../scripts` | 48 files already formatted |

The results were run and reported by the repository owner. CI runs lint, tests and the frontend build on every push (`.github/workflows/ci.yml`).

The five original specs define 32 named correctness properties (P1.1 to P1.7, P2.1 to P2.5, P3.1 to P3.9, P4.1 to P4.6, P5.1 to P5.5), and Spec 6 (gemini-driver) adds 13 (P6.1 to P6.13), 45 in total. The backend ones use Hypothesis. The UI ones (P5.x) use a small seeded generator in `frontend/src/test/seeded.ts`, not a property-testing library. An architecture test (`backend/tests/test_architecture.py`) parses imports with `ast` and fails if invariants 1 and 2 are broken.

What the recordings are:

- The agent in every recorded replay is scripted. It is a fixed list of actions that plays an agent that obeyed the injected instruction. Each replay is labelled "scripted" in the UI. A replay would say "live LLM" only if it were recorded with the LLM driver. None is.
- Live LLM check, Gemini driver: passed once with `--driver gemini` (model `gemini-3.5-flash-lite`, enforcement on). The run ended `FINISHED` after 4 steps. The agent tried `export_records` in the Vault, the permit denied it (`NOT_IN_PERMIT`), and nothing was exported. The model never called `read_document`, so it never saw the injected note: the injection was not acted on in this run. The run was not committed. Using it needs `GEMINI_API_KEY` and `AGENT_MODEL` set in the environment, then `--driver gemini`. It uses only the Python standard library, so no extra is needed.
- Anthropic driver: not run live; it was only tested against a fake client. Its request mapping follows the Anthropic documentation. Using it needs the `llm` extra (`uv sync --extra llm`, unverified), `ANTHROPIC_API_KEY` and `AGENT_MODEL` set in the environment, then `--driver llm`.
- The Gemini client does not retry. One HTTP 503 or a 60-second timeout aborts the run, and the CLI prints only `error: run aborted: GeminiRequestError (details withheld; see docs)`.
- All tools are simulated. Nothing is sent anywhere. The "export" appends to an in-memory list.
- Re-record the replays with `uv --directory backend run python ../scripts/record_replays.py`. Recording twice produces byte-identical files.

## How Kiro was used

- Specs: five specs in `.kiro/specs/` (permit-identity, tools-places-admission, engine-audit, scenario-drivers-replays, timeline-ui) plus Spec 6 (gemini-driver), each written requirements first, then design, then tasks.
- Property-based tests: the 45 properties above are written into each design document and implemented as tests.
- Steering: seven always-on files in `.kiro/steering/` (product scope, quality bar, security invariants, structure, tech, Telescript facts, workflow).
- Hooks: five hooks in `.kiro/hooks/` (property-guard, invariant-review, fact-guard, spec-sync, journal).
- Journal: a dated, factual log of what worked and what went wrong is in [docs/kiro-journal.md](docs/kiro-journal.md).

Planning documents (steering files, spec briefs, PRD and roadmap) were drafted with external AI assistants (Claude via claude.ai, and Antigravity) before building. All specs, code and tests in this repository were produced and run in Kiro.

## Demo-only key

The scenario signs the agent's identity with a deterministic Ed25519 key derived from a public seed (`telepermit-demo-authority`). It exists so replays are byte-for-byte reproducible. Anyone can derive it, so it protects nothing. Do not reuse this pattern for a real authority.

## Known issues

- Live LLM runs: the Gemini driver passed one live check; the Anthropic driver has not been run live. No live run has acted on the injection or ended in `KILLED` (see Testing).
- The Gemini client does not retry, so one HTTP 503 or a 60-second timeout aborts a live run.
- In the compare view, the screen-reader live region does not announce "Playing", "Paused" or "End of replay". The single-run view does. This is recorded in `docs/PROGRESS.md`.
- `npm audit` reports 3 findings, all in dev tooling (the vitest chain). It reports none in production dependencies. The fix is a breaking vitest upgrade, which has not been applied.
- Lifetime is simulated time (1.0 second per agent turn), not wall-clock time.
- The CLI timeline shortens each summary to 72 characters, so long field lists are cut with "...". The audit log and replay files keep the full values.
- Not implemented: the "size" cap, the same-place interaction rule, more than one agent, real networking and payments.

## Licence

MIT. See [LICENSE](LICENSE).
