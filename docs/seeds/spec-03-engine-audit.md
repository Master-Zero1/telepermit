# Seed: spec 3, engine, metering, kill, audit log

Contract details: `docs/CONTRACTS.md` sections 5 and 6, plus the driver types in section 7. Depends on specs 1 and 2. Branch: `spec/03-engine-audit`.

## Goal
The `Engine` that is the only executor of tools: it meters every action, applies the step algorithm exactly as written, kills on breach, and emits one audit event per transition. Includes the clock, the event models, `reduce_events`, the JSONL writer, and the architecture test.

## Files
`backend/src/telepermit/clock.py`, `audit.py`, `engine.py`, `drivers/__init__.py`, `drivers/base.py` (only `Proposal`, `Observation`, `AgentDriver`); tests in `backend/tests/unit/`, `backend/tests/properties/`, `backend/tests/test_architecture.py`.

## Requirements to capture (EARS, number them 3.1, 3.2, ...)
1. WHEN an agent is not ALIVE, THE Engine SHALL raise AgentNotAlive on `step`.
2. WHEN the elapsed time since birth exceeds the permit lifetime, THE Engine SHALL destroy the agent with reason LIFETIME_EXCEEDED, and an elapsed time exactly equal to the lifetime SHALL be allowed.
3. WHEN the proposal is `finish`, THE Engine SHALL end the run as FINISHED at no cost and no step.
4. WHEN a further step would exceed the step limit, THE Engine SHALL destroy the agent with reason STEPS_EXCEEDED.
5. WHEN an action is not in the permit, THE Engine SHALL emit DENIED(NOT_IN_PERMIT), consume one step, charge nothing, and keep the agent alive.
6. WHEN an action is not available in the current place, THE Engine SHALL emit DENIED(NOT_IN_PLACE) in the same way.
7. WHEN an action would push cumulative spend above the allowance, THE Engine SHALL destroy the agent with reason ALLOWANCE_EXCEEDED WITHOUT running the action.
8. WHEN a `go:<place>` action is allowed, THE Engine SHALL charge GO_COST, ask the destination place to admit the agent, move it on admission, replace its permit with the imposed permit, and record the decision; on REFUSE the agent SHALL stay where it is.
9. WHEN the agent is created with enforcement on, THE Engine SHALL run the border check at the start place and end the run as REFUSED if refused.
10. WHEN enforcement is off, THE Engine SHALL apply no limit checks or kills, SHALL still meter spend and steps, and SHALL move the agent with BORDER_CHECK(ADMIT, UNENFORCED).
11. THE Engine SHALL emit exactly one event per state transition with contiguous `seq`, each carrying the post-transition snapshot (place, step, spent), plus a final RUN_ENDED.
12. THE Engine's `run` SHALL stop with HARNESS_CAP after `max_turns` if the agent is still alive, advancing the clock by TICK_S per turn.
13. THE Engine SHALL be the only module that calls `Place.execute`, and driver modules SHALL NOT import the engine, identity, place or tools modules.
14. THE audit module SHALL provide `reduce_events` and a JSONL writer as in CONTRACTS section 6.

## Correctness properties (Hypothesis, stateful action sequences from the pool in CONTRACTS section 5, with random valid permits that include `go:vault`)
- P3.1 While ALIVE, spent <= allowance and steps <= max_steps of the current permit. (Req 3.4 to 3.8)
- P3.2 After KILLED the only further event is RUN_ENDED, and `step` raises AgentNotAlive. (Req 3.1, 3.7)
- P3.3 `seq` is contiguous from 0 and every transition emits exactly one event. (Req 3.11)
- P3.4 Steps and spent never decrease, and permit fields never grow across any event. (Req 3.8)
- P3.5 `reduce_events(events)` equals the engine's final place, steps, spent, permit and status. (Req 3.11, 3.14)
- P3.6 TOOL_CALL events only name tools that exist in the place recorded on that event. (Req 3.6)
- P3.7 A loop of denied actions ends in KILLED(STEPS_EXCEEDED). (Req 3.4, 3.5)
- P3.8 With enforcement off there is never a KILLED event or a permit-reason DENIED, and spend may exceed the allowance. (Req 3.10)
- P3.9 A forged identity at spawn leads to exactly RUN_STARTED, BORDER_CHECK(REFUSE, BAD_SIGNATURE), RUN_ENDED(REFUSED). (Req 3.9)
Unit tests: lifetime boundary (60.0 allowed, 60.001 killed), the golden Run B event sequence from CONTRACTS section 8 built by hand-driving the engine, the `finish` path.

## Architecture test (`tests/test_architecture.py`)
Parse source with `ast`. Fail if (a) any module in `src/telepermit/drivers/` imports `engine`, `identity`, `place` or `tools`; (b) any module under `src/telepermit/` other than `engine.py` contains a call to an attribute named `execute` (definitions are fine; tests are not scanned). Include a self-test that feeds the checker a deliberately bad snippet and asserts it is caught.

## Exit criteria
In `backend/`: pytest, ruff check and ruff format --check all clean; nine properties plus the architecture test pass. Branch ready for `MERGE`.
