# TelePermit: how you (the Kiro agent) work with me

I am the human owner. I will mostly type short COMMANDS. You do the work, keep state in `docs/PROGRESS.md`, and stay inside the scope in `product.md`.

## Session start (every new chat)
1. Read `docs/PROGRESS.md`. Read `docs/BUILD_PLAN.md` and `docs/CONTRACTS.md` only when the task needs them. Do not re-read everything every message (credits are limited).
2. Reply in at most 5 lines: current phase, last finished item, next command I should type.

## Commands
| Command | What you do |
|---|---|
| `STATUS` | Summarise PROGRESS.md in 5 lines and name the next command. |
| `NEXT` | Do the next unfinished step in PROGRESS.md that does not need me in Spec mode. If it needs Spec mode, tell me the exact command to paste. |
| `PHASE 0` | Run Phase 0 of BUILD_PLAN.md (scaffold). Vibe/chat mode. |
| `SPEC <n>` | (I run this in Spec mode.) Create spec n from `docs/seeds/spec-0<n>-*.md` and `docs/CONTRACTS.md` using the Kiro spec workflow. Requirements in EARS with numbered IDs; design.md must contain a "Correctness Properties" section listing EVERY property in the seed, each tagged with the requirement IDs it validates; tasks.md must include a property-based test task for every property (not optional). Stop after each of the three documents and wait for my approval. Record the spec folder name in PROGRESS.md. |
| `RUN TASKS` | Execute the current spec's tasks one at a time, in order. After each task: run backend tests and ruff (and frontend build/test if touched), fix failures, tick the task, commit locally. |
| `TEST` | Run the full suite (backend pytest + ruff, frontend build + vitest) and report pass/fail counts only. |
| `FIX <problem>` | Smallest possible fix plus a regression test. No refactors, no new features. |
| `MERGE` | If tests are green: merge the spec branch into main with `--no-ff`, tag `spec-0<n>-done`, update PROGRESS.md. Do not push. |
| `PUSH` | `git push` the current branch (and tags). |
| `JOURNAL` | Append a dated entry to `docs/kiro-journal.md` covering what Kiro did well or badly since the last entry, any bug property tests found (include the shrunk counterexample), and any hook/steering effect. Be factual; never invent. |
| `HOOKS` | Walk me through `docs/HOOKS.md` one hook at a time. You cannot create hooks yourself; show me the exact text to paste into the Kiro hooks UI. |
| `RECORD` | Run `cd backend && uv run python ../scripts/record_replays.py`, then run the replay validation tests, then list the files written. |
| `DEPLOY` | Do Phase 6 deployment steps from BUILD_PLAN.md. |
| `DOCS` | Write or update README.md and docs/architecture.md, docs/threat-model.md exactly as BUILD_PLAN.md Phase 6 says. |
| `AUDIT` | Run the submission audit in `docs/SUBMISSION.md` and print a pass/fail table. |
| `FREEZE` | From now on only bug fixes, docs and submission assets. Record this in PROGRESS.md. |

## Rules
- `docs/CONTRACTS.md` is the source of truth for names, numbers and behaviour. If a spec or my request conflicts with it, stop and ask. If CONTRACTS.md itself looks wrong, stop and tell me; do not silently change it.
- Stay in scope. Anything on the cut list in `product.md` needs my explicit approval.
- Stop and ask before: changing any steering file, touching a security invariant, adding a dependency not listed in `tech.md`, deleting files, or changing the public replay format.
- Work on a branch per spec: `spec/0<n>-<short-name>`. Commit locally after each task with messages like `feat(engine): meter tool calls (task 3.2)`. Never push unless I say `PUSH`.
- Never put secrets in files. Never edit `.gitignore` to ignore `.kiro`. Never hand-write `.kiro/hooks` files.
- Never start long-running processes. One-shot commands only.
- Definition of done for any task: code written, tests pass, ruff clean, PROGRESS.md updated.
- Keep chat replies short. Do not paste whole files back to me. Do not regenerate files that already pass tests.
- If a command fails twice for the same reason, stop and show me the error and your diagnosis instead of looping.
- Be honest in every document: no unverified Telescript claims (see telescript-facts.md), no claims the code does not support.
