# TelePermit: build plan (the agent reads this; the human types commands)

Deadline: submit by **Dec 3 2026**; hard deadline Dec 4 2026, 2:00 PM PT (Dec 5, 3:30 AM IST). Feature freeze **Dec 1**. Milestone M1 (CLI demo works, replays recorded) by **Nov 20**.

| Dates | Phase | Command(s) |
|---|---|---|
| Nov 2-3 | Phase 0 scaffold + hooks | `PHASE 0`, `HOOKS` |
| Nov 3-6 | Spec 1 permit + identity | `SPEC 1`, `RUN TASKS`, `MERGE` |
| Nov 7-10 | Spec 2 tools + places + admission | `SPEC 2` ... |
| Nov 11-14 | Spec 3 engine + audit | `SPEC 3` ... |
| Nov 15-20 | Spec 4 scenario + drivers + replays + CLI (M1) | `SPEC 4` ..., `RECORD` |
| Nov 21-26 | Spec 5 timeline UI | `SPEC 5` ... |
| Nov 27-29 | Phase 6 CI, deploy, docs | `DEPLOY`, `DOCS` |
| Nov 30-Dec 1 | Bug-bash, `FREEZE` | `TEST`, `FIX`, `FREEZE` |
| Dec 2 | Phase 7 submission assets | see SUBMISSION.md |
| Dec 3 | `AUDIT`, submit on Devpost | `AUDIT` |

If behind, cut in this order: compare mode in UI, event detail panel, live LLM driver (keep scripted), CI badge. Never cut: enforce on/off contrast, audit log, property tests.

## Standing rules for every phase
- Before every commit run `uv run ruff format .` and `uv run ruff check .` in `backend/`.
- Keep `docs/PROGRESS.md` current.
- Keep the shared contract in `docs/CONTRACTS.md`; code and tests must match it exactly.

---

## Phase 0: scaffold (vibe mode, command `PHASE 0`)

Precondition: the human has already created the GitHub repo, cloned it, copied this kit into the repo root and opened the folder in Kiro. If `git rev-parse --is-inside-work-tree` fails, stop and tell the human.

0.1 Repo checks (report results in one line each):
- `git remote -v` shows a GitHub remote.
- A `LICENSE` file exists and is MIT or Apache-2.0. If not, stop and tell the human to add it on GitHub.
- `git check-ignore -v .kiro` prints NOTHING. If it prints anything, remove the offending ignore rule and tell the human.

0.2 Backend (folder `backend/`):
- Create `pyproject.toml` exactly per `tech.md` (hatchling, src layout, extras `dev`, `llm`, `api`).
- Create `src/telepermit/__init__.py` with `__version__ = "0.1.0"`, and `tests/test_smoke.py` that imports the package and asserts the version.
- Python version: the machine's default Python may be too new for some dependency wheels. Run `uv python install 3.12`, create `backend/.python-version` containing `3.12`, and use Python 3.12 for every backend command (so `uv sync --extra dev` uses it). If uv is not available, create the venv with a Python 3.12 interpreter.
- Run `uv sync --extra dev`; if uv is missing use `python -m venv .venv` then `pip install -e ".[dev]"`. Run `pytest -q` (via `uv run` if available) and `ruff check .`. Both must pass.

0.3 Frontend (folder `frontend/`), written by hand (do NOT run an interactive scaffolder):
- `package.json` (name `telepermit-ui`, private, type module, scripts: `dev` = `vite`, `build` = `tsc -b && vite build`, `test` = `vitest run`), dependencies `react`, `react-dom`; devDependencies `vite`, `@vitejs/plugin-react`, `typescript`, `vitest`, `@types/react`, `@types/react-dom`.
- `index.html`, `tsconfig.json` (+ `tsconfig.node.json` if needed), `vite.config.ts` with the react plugin, `base: './'`, and vitest `environment: 'node'`.
- `src/main.tsx` and `src/App.tsx` rendering a placeholder "TelePermit" heading; `src/styles.css`; `src/smoke.test.ts` with one trivial passing test.
- Run `npm install`, then `npm run build` and `npm test`. Both must pass. Commit `package-lock.json`.

0.4 Repo files:
- `public/replays/` folder inside `frontend/` with a `.gitkeep`.
- `README.md` stub: title, one-line pitch (from product.md), "status: under construction", and the licence line. No Telescript claims beyond telescript-facts.md.
- `.github/workflows/ci.yml` exactly as below.

```yaml
name: ci
on:
  push:
    branches: [main]
  pull_request:
jobs:
  backend:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: backend
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install -e ".[dev]"
      - run: ruff check .
      - run: ruff format --check .
      - run: pytest -q
  frontend:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: frontend
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: "20"
          cache: npm
          cache-dependency-path: frontend/package-lock.json
      - run: npm ci
      - run: npm run build
      - run: npm test
```

0.5 Finish: tick Phase 0 in PROGRESS.md, add a journal line, commit `chore: scaffold backend, frontend, ci`, and tell the human: "Phase 0 done. Type `PUSH`, then `HOOKS`."

Exit criteria: backend pytest + ruff pass, frontend build + test pass, `git check-ignore -v .kiro` prints nothing.

---

## Specs 1 to 5 (Spec mode, command `SPEC <n>`)

For each spec n:
1. Create branch `spec/0<n>-<short-name>` from main.
2. Run the Kiro spec workflow using the seed file as the brief (requirements, then design, then tasks), stopping for approval after each document. Enable property-based tests for the spec. Property tasks are required, not optional.
3. After approval of tasks, wait for `RUN TASKS`.
4. Exit criteria are in each seed. Then wait for `MERGE`.

| n | Seed | Output |
|---|---|---|
| 1 | `docs/seeds/spec-01-permit-identity.md` | `permit.py`, `identity.py`, tests |
| 2 | `docs/seeds/spec-02-tools-places-admission.md` | `tools.py`, `place.py`, tests |
| 3 | `docs/seeds/spec-03-engine-audit.md` | `clock.py`, `audit.py`, `engine.py`, `test_architecture.py`, tests |
| 4 | `docs/seeds/spec-04-scenario-drivers-replays.md` | drivers, scenario, `cli.py`, `scripts/record_replays.py`, replays, `test_replays.py` |
| 5 | `docs/seeds/spec-05-timeline-ui.md` | frontend app, vitest tests |

---

## Phase 6: CI, deploy, docs (commands `DEPLOY`, `DOCS`)

6.1 `DEPLOY`: create `.github/workflows/pages.yml` exactly as below, make sure `npm run build` output (`frontend/dist`) loads replays via relative URLs, and tell the human to enable GitHub Pages (repo Settings -> Pages -> Source: GitHub Actions), then `PUSH`. After the workflow succeeds, the human pastes the live URL into the README top.

```yaml
name: pages
on:
  push:
    branches: [main]
  workflow_dispatch:
permissions:
  contents: read
  pages: write
  id-token: write
concurrency:
  group: pages
  cancel-in-progress: true
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: "20"
          cache: npm
          cache-dependency-path: frontend/package-lock.json
      - run: npm ci
        working-directory: frontend
      - run: npm run build
        working-directory: frontend
      - uses: actions/configure-pages@v5
      - uses: actions/upload-pages-artifact@v3
        with:
          path: frontend/dist
  deploy:
    needs: build
    runs-on: ubuntu-latest
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    steps:
      - id: deployment
        uses: actions/deploy-pages@v4
```
If GitHub reports a deprecated action version, bump to the current major.

6.2 `DOCS`: write
- `README.md`: title and one-line pitch; live demo link placeholder; 3-command quickstart (clone, `cd backend && uv sync --extra dev && uv run python -m telepermit.cli run poisoned_briefing --enforce on`, `cd frontend && npm ci && npm run dev`); "Why this exists"; architecture diagram (ASCII); Telescript facts split into verified / interpretation / our design choices copied from `telescript-facts.md`; threat model summary including "what permits do not stop"; honest note that the demo agent in recorded replays is scripted unless a replay says "live LLM"; how Kiro was used (link to `docs/kiro-journal.md` and `.kiro/`); disclosure that planning documents were drafted with an external AI assistant before the build and all specs, code and tests were produced in Kiro; DEMO-ONLY deterministic key note; licence.
- `docs/architecture.md`: components, event flow, trust boundary, file map.
- `docs/threat-model.md`: stopped / not stopped / out of scope, each with a one-line example, and the invariants list.

Exit criteria: pages workflow green, public URL loads both replays with no API key, README complete.

---

## Phase 7: submission assets
Follow `docs/SUBMISSION.md`.
