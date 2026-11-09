# Progress tracker (the agent updates this file; the human can read it)

Last updated: 2026-11-08. Phase 0 and Spec 1 done; main and tag spec-01-done pushed to origin. Spec 2 spec documents in progress on branch spec/02-tools-places-admission.

## Phases
- [x] Phase 0: scaffold (repo checks, backend, frontend, CI, README stub)
- [x] Hooks created (docs/HOOKS.md): property-guard, invariant-review, fact-guard, spec-sync, journal (not yet committed)
- [x] Spec 1: permit + identity            folder: .kiro/specs/permit-identity  branch: spec/01-permit-identity (all 6 tasks done, 49 tests green, ruff clean; merged to main with --no-ff, tagged spec-01-done, not pushed)
- [ ] Spec 2: tools + places + admission   folder: .kiro/specs/tools-places-admission  branch: spec/02-tools-places-admission (spec docs approved, tasks not started)
- [ ] Spec 3: engine + metering + kill + audit  folder: ____  branch: ____
- [ ] Spec 4: scenario + drivers + replays + CLI  folder: ____  branch: ____  (MILESTONE M1)
- [ ] Spec 5: timeline UI                  folder: ____  branch: ____
- [ ] Phase 6: CI, deploy, README, architecture, threat model
- [ ] Phase 7: submission assets (video, write-up, blog, social, Devpost form)
- [ ] FREEZE declared (target Dec 1)
- [ ] Submitted (target Dec 3)

## Current spec tasks
Spec 1 (permit-identity): [x] 1 T1.1 Permit | [x] 2 T1.2 narrowed_by | [x] 3 T1.3 JSON | [x] 4 T1.4 Authority+Identity | [x] 5 T1.5 verify_identity | [x] 6 final checkpoint

## Decisions and deviations
(agent logs any approved deviation from CONTRACTS.md or BUILD_PLAN.md, with date)

## Known issues
- npm audit: 3 vulnerabilities (1 moderate, 2 critical) in dev tooling only (vitest 3.2.7 via @vitest/mocker, tinypool). Production deps: 0. The fix is a breaking upgrade to vitest 5; not applied, awaiting owner decision.
