# Progress tracker (the agent updates this file; the human can read it)

Last updated: 2026-11-08. Phase 0 and Spec 1 done; main and tag spec-01-done pushed to origin. Spec 2 spec documents in progress on branch spec/02-tools-places-admission.

## Phases
- [x] Phase 0: scaffold (repo checks, backend, frontend, CI, README stub)
- [x] Hooks created (docs/HOOKS.md): property-guard, invariant-review, fact-guard, spec-sync, journal (not yet committed)
- [x] Spec 1: permit + identity            folder: .kiro/specs/permit-identity  branch: spec/01-permit-identity (all 6 tasks done, 49 tests green, ruff clean; merged to main with --no-ff, tagged spec-01-done, not pushed)
- [x] Spec 2: tools + places + admission   folder: .kiro/specs/tools-places-admission  branch: spec/02-tools-places-admission (all 4 tasks done, 89 tests green (49 baseline + 40), ruff clean; merged to main with --no-ff, tagged spec-02-done, main pushed, tag not yet pushed)
- [ ] Spec 3: engine + metering + kill + audit  folder: .kiro/specs/engine-audit  branch: spec/03-engine-audit (spec docs approved; Group A in progress (tasks 1-2 done, baseline 89 tests); Group B blocked until the owner applies the CONTRACTS amendment and confirms)
- [ ] Spec 4: scenario + drivers + replays + CLI  folder: ____  branch: ____  (MILESTONE M1)
- [ ] Spec 5: timeline UI                  folder: ____  branch: ____
- [ ] Phase 6: CI, deploy, README, architecture, threat model
- [ ] Phase 7: submission assets (video, write-up, blog, social, Devpost form)
- [ ] FREEZE declared (target Dec 1)
- [ ] Submitted (target Dec 3)

## Current spec tasks
Spec 3 (engine-audit), Group A: [x] 1 T3.1 clock+events | [x] 2 T3.2 reduce+JSONL | [ ] 3 T3.3 driver types | [ ] 4 T3.4 construction+spawn | [ ] 5 T3.5 step enforced | [ ] 6 T3.6 step unenforced | [ ] 7 T3.7 run + 3.15 | [ ] 8 T3.8 architecture test | [ ] 9 checkpoint. Group B (blocked): [ ] 10 owner CONTRACTS amendment | [ ] 11 (a) tool errors | [ ] 12 (d) clock | [ ] 13 widen props | [ ] 14 checkpoint
Spec 2 (tools-places-admission): [x] 1 T2.1 models | [x] 2 T2.2 catalog | [x] 3 T2.3 admit | [x] 4 final checkpoint
Spec 1 (permit-identity): [x] 1 T1.1 Permit | [x] 2 T1.2 narrowed_by | [x] 3 T1.3 JSON | [x] 4 T1.4 Authority+Identity | [x] 5 T1.5 verify_identity | [x] 6 final checkpoint

## Decisions and deviations
(agent logs any approved deviation from CONTRACTS.md or BUILD_PLAN.md, with date)
- 2026-11-09 (owner approved, Spec 3): CONTRACTS section 5 Engine signature gains keyword-only scenario, driver and task (defaults "", "scripted", ""), because RUN_STARTED (section 6) needs them at construction and the old signature had no source for them.
- 2026-11-09 (owner approved, Spec 3, decision a): tool errors. The Engine logs ToolArgumentError as a TOOL_CALL with an "error:" result, and any other tool exception sets a new status ERROR, emits RUN_ENDED(ERROR) and re-raises. CONTRACTS change pending: the owner adds ERROR to the status lists in sections 5 and 6 and allows an "error:" TOOL_CALL result, after tasks.md is written. Details are in the engine-audit design.
- 2026-11-09 (owner approved, Spec 3, decision d): the Engine accepts any clock with now(), and run() calls advance(TICK_S) only if the clock provides advance. CONTRACTS change pending: the owner amends the run description in section 5, after tasks.md is written.

## Known issues
- npm audit: 3 vulnerabilities (1 moderate, 2 critical) in dev tooling only (vitest 3.2.7 via @vitest/mocker, tinypool). Production deps: 0. The fix is a breaking upgrade to vitest 5; not applied, awaiting owner decision.
