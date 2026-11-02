# TelePermit x Kiro: START HERE

This kit lets Kiro build the whole project from markdown files while you type short commands. It contains planning documents only (no source code). Kiro writes the specs, code and tests.

## What is in the kit
| Path | Purpose |
|---|---|
| `.kiro/steering/*.md` | Always-on rules Kiro loads automatically: product, tech, structure, security invariants, Telescript facts, and `workflow.md` (the command protocol) |
| `docs/PROGRESS.md` | State tracker Kiro updates, so any new chat can resume |
| `docs/BUILD_PLAN.md` | Phases, dates, exact scaffold steps, CI and Pages workflows |
| `docs/CONTRACTS.md` | Exact behaviour, numbers, event schema and golden traces (checked against a prototype) |
| `docs/seeds/spec-01..05` | Briefs Kiro turns into its own requirements, design and tasks |
| `docs/HOOKS.md` | Five hooks you create in the Kiro UI |
| `docs/SUBMISSION.md` | Video script, write-up template, blog and social guidance, final audit |
| `.gitignore`, `.env.example` | Safe defaults (the `.kiro` folder is NOT ignored) |

## Step 1: one-time setup (you, about 20 minutes)
1. Kiro account: request the 4,000 free credits from the Resources tab of the Devpost page now (needs your Kiro user ID; takes up to 48 business hours; closes Dec 1). Redeem when the code arrives.
2. Install Kiro IDE (kiro.dev) and sign in with the same account. Install Git, Node.js 20+, Python 3.11+ and `uv` (or just use `pip`).
3. On GitHub create a **public** repo `telepermit` with a README and an **MIT** licence (License dropdown).
4. In a terminal:
   ```
   git clone https://github.com/<you>/telepermit.git
   cd telepermit
   ```
5. Extract this kit's zip **into the repo folder** so `.kiro/`, `docs/`, `.gitignore` sit at the repo root (not inside a subfolder). Turn on "show hidden files" so you can see `.kiro`. If asked to overwrite `.gitignore`, say yes. Keep GitHub's `LICENSE` and `README.md`.
6. Open it in Kiro: `kiro .` (or File -> Open Folder).
7. First commit so the project history starts today:
   ```
   git add -A
   git commit -m "chore: add kiro steering and planning docs"
   git push
   ```
8. On github.com check that `.kiro/` is visible and the licence shows in the About sidebar.

## Step 2: the master prompt (paste once into a new Kiro chat, normal chat mode)
```
You are the build agent for the TelePermit project (Kiroween 2026, Resurrection category).
Your standing rules are in .kiro/steering/ and are already loaded.
Do this now, without building anything yet:
1. Read .kiro/steering/workflow.md, docs/PROGRESS.md, docs/BUILD_PLAN.md and docs/CONTRACTS.md completely.
2. Check that every file they reference exists (docs/seeds/spec-01..05, docs/HOOKS.md, docs/SUBMISSION.md, docs/kiro-journal.md). List anything missing or contradictory by file name.
3. Reply in at most 8 lines: what we are building, the phases, the commands you understand, and any problems found.
4. Then wait for my command. I will type PHASE 0 next.
```

## Step 3: run the project with commands
Type these in Kiro chat. Kiro's steering already knows what each means.

| When | You type | What happens |
|---|---|---|
| Right after the master prompt | `PHASE 0` | Scaffolds backend, frontend, CI, README stub, runs tests |
| Then | `PUSH` | Pushes |
| Then | `HOOKS` | Kiro shows each hook text; you paste each into the Kiro hooks UI (about 10 minutes) |
| Spec 1 (Spec mode) | the prompt below | Kiro writes requirements, design, tasks |
| After you approve tasks | `RUN TASKS` | Kiro implements task by task, testing and committing |
| End of spec | `TEST`, `JOURNAL`, `MERGE`, `PUSH` | Verify, log, merge, push |
| Repeat for specs 2 to 5 | the prompt for that spec | same loop |
| After spec 4 | `RECORD` | Writes the replay files (milestone M1) |
| After spec 5 | run `npm run dev` in `frontend/` yourself and look | then `FIX <what you saw>` |
| Late November | `DEPLOY`, `DOCS` | Pages workflow and README |
| Dec 1 | `FREEZE` | Bug fixes only |
| Dec 2 to 3 | `AUDIT`, then follow `docs/SUBMISSION.md` | Final checks, then you submit |
| Any time | `STATUS` or `NEXT` | Where we are, or do the next step |
| Something broke | `FIX <description>` | Smallest fix plus a regression test |

### Spec-mode prompts (switch the chat to Spec mode first, paste one)
Spec 1:
`SPEC 1. Create the spec from docs/seeds/spec-01-permit-identity.md and docs/CONTRACTS.md, following the SPEC protocol in .kiro/steering/workflow.md. Stop after each document for my approval.`
Spec 2:
`SPEC 2. Create the spec from docs/seeds/spec-02-tools-places-admission.md and docs/CONTRACTS.md, following the SPEC protocol in .kiro/steering/workflow.md. Stop after each document for my approval.`
Spec 3:
`SPEC 3. Create the spec from docs/seeds/spec-03-engine-audit.md and docs/CONTRACTS.md, following the SPEC protocol in .kiro/steering/workflow.md. Stop after each document for my approval.`
Spec 4:
`SPEC 4. Create the spec from docs/seeds/spec-04-scenario-drivers-replays.md and docs/CONTRACTS.md, following the SPEC protocol in .kiro/steering/workflow.md. Stop after each document for my approval.`
Spec 5:
`SPEC 5. Create the spec from docs/seeds/spec-05-timeline-ui.md and docs/CONTRACTS.md, following the SPEC protocol in .kiro/steering/workflow.md. Stop after each document for my approval.`

### What to check at each approval gate (two minutes)
- **Requirements:** numbered, in EARS form, covering every item in the seed. No extra features.
- **Design:** has a "Correctness Properties" section containing every property from the seed.
- **Tasks:** includes a property-test task for each property, not marked optional; tasks run tests.
If something is off, reply with what to change instead of "approved". If it still disagrees with CONTRACTS.md, CONTRACTS.md wins.

## Rules of thumb
- One spec per branch; commit locally per task; push only with `PUSH`.
- If Kiro stalls or loops, type `STATUS`; if it repeats the same failure twice it should stop and show you the error (that is in the workflow rules).
- Autopilot or Supervised, your choice: use Supervised at the approval gates and the first tasks, and switch to Autopilot if it is behaving.
- Credits: keep chat replies short, don't ask Kiro to regenerate files that pass tests, check kiro.dev/account/usage after spec 1 to learn your burn rate, and keep about a quarter in reserve for the UI and bug fixes.
- Keep `docs/kiro-journal.md` honest. It becomes your Devpost write-up.

## Honest notes
- The tech stack differs from the earlier chat guide in two places: **Tailwind is dropped** (plain CSS, one less failure point) and **specs are ordered tools/places (2) before engine (3)**, because the engine depends on places.
- Some Kiro details could not be fully verified: exact hook storage and the spec-mode UI wording. The kit avoids relying on them (hooks are made by you in the UI; spec flow uses Kiro's normal approval gates). If Kiro's UI differs, follow the UI and tell Kiro.
- The planning documents were drafted with an external AI assistant. Say so in your write-up (template in `docs/SUBMISSION.md`). The code, specs and tests must come from Kiro.
- Student bonus, blog and social posts need you personally (LinkedIn, student email, your own words).
