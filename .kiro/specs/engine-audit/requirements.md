# Requirements Document

## Introduction

This spec covers the third building block of TelePermit: the Engine that is the only executor of tools. The Engine meters every action, applies the step algorithm of CONTRACTS section 5, destroys the agent when a limit is breached, and emits one audit event per state transition. The spec also covers the Clock, the Event models, `reduce_events`, the JSONL writer, the driver types in `drivers/base.py`, and the architecture test. The behaviour is defined by CONTRACTS sections 5, 6 and 7, which are binding. The spec depends on the merged Permit, Identity, Tool and Place modules and uses them only by import.

Criterion IDs 3.1 to 3.14 are the seed reference IDs, and Requirement N holds criterion 3.N. Criterion 3.15 is an owner-approved addition beyond the 14 seed items.

Notes for design (no scope change):

- (a) The step algorithm of CONTRACTS section 5 is applied in the order stated, and the first branch that matches decides the result of the call.
- (b) `drivers/base.py` holds only Proposal, Observation and AgentDriver. The Observation never contains the permit, spend, costs, steps or keys. The `last_result` strings follow CONTRACTS section 7.
- (c) Owner-approved CONTRACTS change: the Engine constructor takes the keyword-only arguments `scenario`, `driver` and `task`, and uses them only to fill the RUN_STARTED event.
- (d) This spec contains no scenario, no driver implementation and no CLI. It adds no new dependency. It changes no Spec 1 or Spec 2 module.
- (e) Criterion 3.15 (the task given to `run` must match a non-empty constructor task) is an owner-approved addition. CONTRACTS section 5 is not amended for it.

## Glossary

- **Engine**: The only component that executes tools. It holds the places, the identity, the current permit, the clock and the run state, and it emits the audit events.
- **Proposal**: Immutable value with fields `action` (str) and `args` (dict) that a driver returns to name the next action.
- **Observation**: Value built by the Engine for the driver, with fields `task`, `turn`, `place`, `tools` and `last_result`. It never carries the permit, spend, costs, steps or keys.
- **Event**: Audit record with fields `seq`, `t`, `type`, `place`, `step`, `spent` and `data`. The event types are RUN_STARTED, BORDER_CHECK, TOOL_CALL, DENIED, KILLED, FINISHED and RUN_ENDED.
- **Snapshot**: The values of `place`, `step` and `spent` recorded on an Event after the transition that the Event describes.
- **Kill**: The transition that sets the status to KILLED. It emits KILLED, then RUN_ENDED(KILLED), with one of the reasons LIFETIME_EXCEEDED, STEPS_EXCEEDED or ALLOWANCE_EXCEEDED.
- **Denial**: The transition that emits DENIED with the reason NOT_IN_PERMIT or NOT_IN_PLACE. It consumes a step, charges nothing and leaves the status ALIVE.
- **Border_Check**: The call to `Place.admit` for a start place or a `go:<place>` destination, and the BORDER_CHECK event that records the decision.
- **Enforcement**: The Engine mode set by the `enforce` constructor argument. With enforcement on, the Engine applies every limit check. With enforcement off, the Engine applies no limit check and no Kill.
- **Harness_Cap**: The limit `HARNESS_CAP` (30 driver turns per run), and also the status HARNESS_CAP that a run takes when the limit is reached while the agent is still ALIVE. It is a test-harness limit, not a permit feature.
- **Clock**: Object with a `now()` method that returns the current time in seconds. A TickClock also has `advance(dt)`.
- **Status**: One of ALIVE, KILLED, FINISHED, REFUSED or HARNESS_CAP.
- **AgentNotAlive**: The exception that `step` raises when the status is not ALIVE.
- **GO_COST**: The constant 1 teleclick, charged for every `go:<place>` attempt that reaches the cost check.
- **TICK_S**: The constant 1.0 simulated second that `run` advances the Clock per driver turn.

## Requirements

### Requirement 1: Refuse steps on a non-ALIVE agent

**User Story:** As a security reviewer, I want a finished, killed or refused agent to be unable to act again, so that no action can run after the run has ended.

#### Acceptance Criteria

3.1. WHEN `step` is called on an Engine whose status is not ALIVE, THE Engine SHALL raise AgentNotAlive and SHALL emit no event.

### Requirement 2: Lifetime limit

**User Story:** As a runtime operator, I want an agent destroyed when its lifetime is over, so that a permit lifetime bounds how long an agent can act.

#### Acceptance Criteria

3.2. WHEN `step` is called with enforcement on and `clock.now() - born` is greater than the lifetime_s of the current permit, THE Engine SHALL, before any other check of that call including the `finish` check, set the status to KILLED and emit KILLED(LIFETIME_EXCEEDED) with limit equal to lifetime_s and observed equal to the elapsed time, followed by RUN_ENDED(KILLED), with the Snapshot step equal to the step count before this attempt and with the attempt consuming no step, and an elapsed time exactly equal to lifetime_s SHALL be allowed.

### Requirement 3: Finish

**User Story:** As a driver author, I want a free way to end a run, so that an agent can stop without spending anything.

#### Acceptance Criteria

3.3. WHEN `step` is called with the action `finish` and the lifetime check of criterion 3.2 has not killed the agent, THE Engine SHALL set the status to FINISHED and emit FINISHED followed by RUN_ENDED(FINISHED), and the call SHALL leave `steps` and `spent` unchanged.

### Requirement 4: Step limit

**User Story:** As a runtime operator, I want an agent destroyed when it exceeds its step limit, so that a permit max_steps bounds how many actions an agent can attempt.

#### Acceptance Criteria

3.4. WHEN `step` is called with enforcement on, the action is not `finish`, and `steps + 1` is greater than the max_steps of the current permit, THE Engine SHALL set the status to KILLED and emit KILLED(STEPS_EXCEEDED) with limit equal to max_steps and observed equal to `steps + 1`, followed by RUN_ENDED(KILLED), with the Snapshot step not incremented, so that with max_steps equal to N the Nth step is allowed and the N+1th step is killed.

### Requirement 5: Denial for an action not in the permit

**User Story:** As a runtime operator, I want an action outside the permit refused without running, so that a permit allowed_actions list bounds what an agent can do.

#### Acceptance Criteria

3.5. WHEN `step` is called with enforcement on, the lifetime and step checks have passed, and the step counter has been incremented, and the action is not an exact string match for any member of the allowed_actions of the current permit, THE Engine SHALL emit DENIED(NOT_IN_PERMIT), consume the step, charge nothing and keep the status ALIVE.

### Requirement 6: Denial for an action not in the place

**User Story:** As a runtime operator, I want an action that the current place does not offer refused without running, so that an agent cannot use a tool or destination that is unavailable where it stands.

#### Acceptance Criteria

3.6. WHEN `step` is called and the permit check of criterion 3.5 has passed, and the action is a tool that the current place does not hold, or is `go:<p>` where `<p>` is not the name of a place of the Engine or equals the current place, THE Engine SHALL emit DENIED(NOT_IN_PLACE), consume the step, charge nothing and keep the status ALIVE.

### Requirement 7: Allowance limit

**User Story:** As a runtime operator, I want an agent destroyed before an action that would overspend, so that a breaching action never executes.

#### Acceptance Criteria

3.7. WHEN `step` is called with enforcement on and the denial checks of criteria 3.5 and 3.6 have passed, and `spent + cost` is greater than the allowance of the current permit, where cost is GO_COST for a `go:<place>` action and otherwise the cost of the tool, THE Engine SHALL set the status to KILLED without running the action and emit KILLED(ALLOWANCE_EXCEEDED) with limit equal to the allowance and observed equal to `spent + cost`, followed by RUN_ENDED(KILLED), with `spent` unchanged and with the Snapshot step including the attempt, and spend that reaches exactly the allowance SHALL be allowed.

### Requirement 8: Border crossing

**User Story:** As a runtime operator, I want every crossing to a new place checked and metered, so that a place can refuse an agent or impose a narrower permit.

#### Acceptance Criteria

3.8. WHEN `step` is called with an allowed `go:<place>` action that passes the checks of criteria 3.2 to 3.7, THE Engine SHALL charge GO_COST, call `admit` on the destination place with the agent's current permit, the current steps and spent after this action's increments, and elapsed equal to `clock.now() - born`, and SHALL emit BORDER_CHECK with cost 1, such that on ADMIT or ADMIT_IMPOSED the Engine moves the agent to the destination, replaces the permit with the admission permit_after and records the decision, and on REFUSE the agent stays at its place, keeps its permit, and the BORDER_CHECK carries the agent's current permit as permit_after, with the cost charged in both cases.

### Requirement 9: Spawn border check

**User Story:** As a runtime operator, I want an agent checked at its start place, so that a forged or unwanted agent never gets to run a tool.

#### Acceptance Criteria

3.9. WHEN an Engine is created with enforcement on, THE Engine SHALL emit RUN_STARTED carrying the scenario, driver, enforce, task, identity and permit from the constructor arguments, call `admit` on the start place with steps 0, spent 0 and elapsed 0.0, and emit BORDER_CHECK with step 0, via_action null and cost 0, such that on REFUSE the status becomes REFUSED and the Engine emits RUN_ENDED(REFUSED) so that no tool can ever run, and on admission the current permit becomes the admission permit_after.

### Requirement 10: Enforcement off

**User Story:** As a demo author, I want an unenforced mode that still meters, so that the same run can be shown with and without the permit system.

#### Acceptance Criteria

3.10. WHILE enforcement is off, THE Engine SHALL apply no lifetime, steps, permit or allowance check, perform no Kill, never emit DENIED(NOT_IN_PERMIT), perform no spawn Border_Check, still emit DENIED(NOT_IN_PLACE) and consume the step for an action that the current place does not offer, still end the run on `finish`, still meter `steps` and `spent`, and move the agent on `go:<place>` immediately with BORDER_CHECK(decision ADMIT, reason UNENFORCED, permit_after equal to the unchanged permit) and no identity or class check.

### Requirement 11: One event per transition

**User Story:** As an auditor, I want exactly one ordered event for every state transition, so that the log is a complete and replayable record.

#### Acceptance Criteria

3.11. THE Engine SHALL emit exactly one Event per state transition, with `seq` contiguous from 0, each Event carrying the post-transition Snapshot of place, step and spent, and SHALL emit a final RUN_ENDED when the run ends, so that a Kill and a `finish` each emit their cause Event followed by RUN_ENDED.

### Requirement 12: Run loop and harness cap

**User Story:** As a test author, I want a run loop with a hard turn limit, so that a driver that never finishes cannot run forever.

#### Acceptance Criteria

3.12. WHEN `run` is called with a driver, a task and `max_turns` (default HARNESS_CAP), THE Engine SHALL repeat up to `max_turns` times the sequence of stopping if the status is not ALIVE, advancing the Clock by TICK_S, building the Observation, calling `driver.propose` and calling `step`, and if the status is still ALIVE after the loop THE Engine SHALL set the status to HARNESS_CAP and emit RUN_ENDED(HARNESS_CAP), so that `max_turns` equal to 0 gives HARNESS_CAP immediately.

### Requirement 13: Single executor of tools

**User Story:** As a security reviewer, I want the Engine to be the only caller of `Place.execute` and the drivers kept apart from the runtime, so that no other module can run a tool or reach a key.

#### Acceptance Criteria

3.13. THE Engine SHALL be the only module that calls `Place.execute`, so that no other module under the package source calls an attribute named `execute` (including the place module itself), and no module under `drivers/` imports the engine, identity, place or tools modules, as checked by an architecture test that parses the source with `ast` and fails on a deliberately bad snippet in a self-test.

### Requirement 14: Audit reduction and JSONL writer

**User Story:** As an auditor, I want to rebuild the final state from the event list and write the log as JSONL, so that a recorded run can be verified and replayed.

#### Acceptance Criteria

3.14. THE audit module SHALL provide `reduce_events`, which returns place, step, spent, permit and status from an event list, taking the snapshot fields from the last event, the permit from the last RUN_STARTED or BORDER_CHECK event, and the status from RUN_ENDED and otherwise ALIVE, and SHALL provide a JSONL writer that writes one `json.dumps(event, sort_keys=True)` per line with LF line endings.

### Requirement 15: Task consistency between the constructor and run

**User Story:** As a test author, I want `run` to reject a task that contradicts the one the Engine was built with, so that the task recorded in RUN_STARTED and the task the driver sees cannot differ.

#### Acceptance Criteria

3.15. WHEN `run` is called with a `task` that differs from a non-empty `task` given to the Engine constructor, THE Engine SHALL raise ValueError before it advances the Clock, calls the driver or emits any event, and an empty constructor `task` SHALL mean that the task is unspecified, so that `run` SHALL accept any task.
