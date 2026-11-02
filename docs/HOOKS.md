# Kiro hooks to create (the human creates them in the Kiro UI; command `HOOKS` walks through them)

Kiro agents cannot create hooks for you. Open the Agent Hooks section in the Kiro panel, add a new hook, choose the trigger and file pattern, and paste the instruction text. Create them one by one and test each by saving a matching file. Hooks are stored under `.kiro/hooks/` and must be committed.

Credit warning: a hook that fires on every save costs credits. Keep instructions short, scope file patterns tightly, and disable the property guard while you are doing large generations.

| # | Name | Trigger (event, file pattern) | Instruction to paste |
|---|---|---|---|
| 1 | Property guard | File save, `backend/src/telepermit/**/*.py` | `Run only the tests for the module that changed (pytest -q -x on the matching test file or properties file). If a property test fails, show the shrunk counterexample in 5 lines or fewer and suggest the smallest fix. Do not edit tests to make them pass.` |
| 2 | Invariant review | File save, `backend/src/telepermit/engine.py`, `place.py`, `drivers/*.py` | `Check the saved file against .kiro/steering/security-invariants.md. Report any violation in one line each, or say OK. Do not change code.` |
| 3 | Fact guard | File save, `README.md`, `docs/*.md`, `frontend/src/**/*.tsx` | `List every Telescript claim in the saved file. Flag any claim that is not in .kiro/steering/telescript-facts.md, or an interpretation or design choice not labelled as such. Do not edit the file.` |
| 4 | Spec sync | File save, `.kiro/specs/**/requirements.md` | `Check that design.md and tasks.md in the same spec folder still cover every numbered requirement. Report gaps in a short list. Do not edit.` |
| 5 | Journal | Manual trigger (or file save of `docs/PROGRESS.md`) | `Append one dated factual entry to docs/kiro-journal.md about what was just completed, including any property-test failure found. If nothing notable happened, add nothing.` |

After creating them: run `git status`, confirm new files under `.kiro/hooks/`, commit (`chore: add kiro hooks`), and record the hook names in PROGRESS.md.

If a hook misbehaves, edit or disable it in the UI; do not hand-write hook files.
