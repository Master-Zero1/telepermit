# TelePermit: quality bar (always on)

## Environment (Windows, PowerShell)
- Run ONE command per terminal call and check its result before the next. Never use `&&`. Do not use `;` to chain commands that depend on each other.
- Use `uv --directory backend run ...` and `npm --prefix frontend ...` so commands work from the repo root.
- Forward slashes; quote paths that contain spaces.
- Write text files as UTF-8 with LF line endings (in Python use `newline="\n"`). Replay files must have LF endings.
- Never start long-running processes (dev servers, watch mode). One-shot commands only.

## Code
- Python: type hints on every public function; `from __future__ import annotations`; a module docstring naming the CONTRACTS section it implements; no `print` in library code (only `cli.py`); no bare `except`; no mutable default arguments; no global mutable state.
- TypeScript: strict mode; no `any` in app code; no non-null assertions used to silence errors.
- Define every constant that CONTRACTS.md names (GO_COST, HARNESS_CAP, TICK_S, SCHEMA_VERSION) once and import it. Never repeat a literal.
- Small functions; no dead code; no commented-out code; no TODO without a task id.

## Tests
- `tests/conftest.py` registers and loads a Hypothesis profile: `deadline=None`, `max_examples=200`.
- Every property test has a docstring of the form `Property P<n>.<m>: <statement>. Validates: <requirement ids>`.
- When a task has both code and tests, write the test first, run it, and confirm it fails for the expected reason before implementing.
- Never weaken, skip, xfail or delete a test to make a run pass. If a test is wrong, say why and wait for my approval.
- Test boundaries explicitly: equal to the limit, one over the limit, zero limits.

## Reporting
- After each task print: `DONE T<id>: <one line>. Tests: <passed>/<total>. Ruff: clean. Files: <list>.`
- Never claim a task is done unless you ran its tests in this session and saw them pass. Give counts, not prose.
- If unsure, say "unsure" and name what you need. Keep replies under 15 lines unless I ask for more.

## Git
- Run `git status --short` before every commit. Stage files by name. Never stage unrelated files or generated junk.
- Conventional commits: `feat|fix|test|docs|chore|style|ci(scope): message (task id)`.
- Never push, force-push, rebase, `reset --hard` or delete branches unless I say so.

## Stop conditions (stop and report, do not improvise)
- A command fails twice for the same reason.
- A spec, my request or an existing file conflicts with docs/CONTRACTS.md.
- A change would touch security-invariants.md, the replay format, or add a dependency not listed in tech.md.
- You need something you do not have (a credential, a decision from me).
