# Progress tracker (the agent updates this file; the human can read it)

Last updated: 2026-11-xx. Phase 0 and Specs 1 to 4 done, merged to main and pushed with their tags (spec-04-done, and m1-core on 0513077). Next: Spec 5.

## Phases
- [x] Phase 0: scaffold (repo checks, backend, frontend, CI, README stub)
- [x] Hooks created (docs/HOOKS.md): property-guard, invariant-review, fact-guard, spec-sync, journal (not yet committed)
- [x] Spec 1: permit + identity            folder: .kiro/specs/permit-identity  branch: spec/01-permit-identity (all 6 tasks done, 49 tests green, ruff clean; merged to main with --no-ff, tagged spec-01-done, pushed with its tag)
- [x] Spec 2: tools + places + admission   folder: .kiro/specs/tools-places-admission  branch: spec/02-tools-places-admission (all 4 tasks done, 89 tests green (49 baseline + 40), ruff clean; merged to main with --no-ff, tagged spec-02-done, pushed with its tag)
- [x] Spec 3: engine + metering + kill + audit  folder: .kiro/specs/engine-audit  branch: spec/03-engine-audit (all 14 tasks done, Groups A and B, 210 tests green = 89 baseline + 121, ruff clean; merged to main with --no-ff, tagged spec-03-done, pushed with its tag)
- [x] Spec 4: scenario + drivers + replays + CLI  folder: .kiro/specs/scenario-drivers-replays  branch: spec/04-scenario-drivers-replays  (MILESTONE M1) (merged to main as 17288b8, tag spec-04-done, 329 tests pass on main against baseline 210; M1 recorded over the enforced and unenforced replays, the forged replay is optional and also recorded; pushed to origin with spec-04-done and m1-core; the LLM mapping has not been run against the live service)
- [ ] Spec 5: timeline UI                  folder: ____  branch: ____
- [ ] Phase 6: CI, deploy, README, architecture, threat model
- [ ] Phase 7: submission assets (video, write-up, blog, social, Devpost form)
- [ ] FREEZE declared (target Dec 1)
- [ ] Submitted (target Dec 3)

## Current spec tasks
Spec 4 (scenario-drivers-replays): all 12 tasks done and merged (Group A tasks 1-9, Group B tasks 10-12 after the owner's CONTRACTS amendment, commit 44ebafd). Pushed. Next: Spec 5.
Spec 3 (engine-audit), Group A: [x] 1 T3.1 clock+events | [x] 2 T3.2 reduce+JSONL | [x] 3 T3.3 driver types | [x] 4 T3.4 construction+spawn | [x] 5 T3.5 step enforced | [x] 6 T3.6 step unenforced | [x] 7 T3.7 run + 3.15 | [x] 8 T3.8 architecture test | [x] 9 checkpoint. Group B (blocked): [x] 10 owner CONTRACTS amendment | [x] 11 (a) tool errors | [x] 12 (d) clock | [x] 13 widen props | [x] 14 checkpoint
Spec 2 (tools-places-admission): [x] 1 T2.1 models | [x] 2 T2.2 catalog | [x] 3 T2.3 admit | [x] 4 final checkpoint
Spec 1 (permit-identity): [x] 1 T1.1 Permit | [x] 2 T1.2 narrowed_by | [x] 3 T1.3 JSON | [x] 4 T1.4 Authority+Identity | [x] 5 T1.5 verify_identity | [x] 6 final checkpoint

## Decisions and deviations
(agent logs any approved deviation from CONTRACTS.md or BUILD_PLAN.md, with date)
- 2026-11-xx (owner approved, Spec 3): CONTRACTS section 5 Engine signature gains keyword-only scenario, driver and task (defaults "", "scripted", ""), because RUN_STARTED (section 6) needs them at construction and the old signature had no source for them.
- 2026-11-xx (owner approved, Spec 3, decision a): tool errors. The Engine logs ToolArgumentError as a TOOL_CALL with an "error:" result, and any other tool exception sets a new status ERROR, emits RUN_ENDED(ERROR) and re-raises. CONTRACTS change applied by the owner (commit 552298b). Details are in the engine-audit design.
- 2026-11-xx (owner approved, Spec 3, decision d): the Engine accepts any clock with now(), and run() calls advance(TICK_S) only if the clock provides advance. CONTRACTS change applied by the owner (commit 552298b).

## Known issues
- npm audit: 3 vulnerabilities (1 moderate, 2 critical) in dev tooling only (vitest 3.2.7 via @vitest/mocker, tinypool). Production deps: 0. The fix is a breaking upgrade to vitest 5; not applied, awaiting owner decision.
