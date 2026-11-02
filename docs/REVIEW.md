# TelePermit — Spec Review

Cross-file contradictions, missing edge cases, ambiguous requirements, and anything that would make a spec-driven build fail. `docs/CONTRACTS.md` is the source of truth and is **not changed** — suspected errors in CONTRACTS are listed at the end under "Proposed changes to CONTRACTS.md".

---

## 1. Contradictions Between Files

### 1.1 Run A event count: 32 vs 30-turn harness cap

**Files:** `docs/CONTRACTS.md` §8 (line 130), §5 (line 76), §1 (line 9)

CONTRACTS says Run A has **32 events** and ends at **step 30** with `HARNESS_CAP`. The harness cap is 30 turns. The event count includes non-step events: `RUN_STARTED` (1) + `BORDER_CHECK` at library spawn (1) = 2 overhead events before any driver turn, plus the 30 turns produce 29 tool/border events (turn 1 = `TOOL_CALL`, turn 2 = `BORDER_CHECK vault`, turns 3–30 = 28 events), plus the `RUN_ENDED` = 32 total. This actually checks out, but builders must carefully count: **the 2 `export_records` calls (turns 3–4) + 26 `read_records` calls (turns 5–30) = 28, plus 1 `TOOL_CALL read_document` + 1 `BORDER_CHECK` = 30 driver-turn events + 2 bookkeeping = 32.** Not a contradiction, but easy to miscount.

### 1.2 `DENIED` step consumption wording (enforce=False)

**Files:** `docs/CONTRACTS.md` §5, line 73

The enforce=False section says "step 7 still applies (DENIED `NOT_IN_PLACE` still consumes a step)". But step 7 is the only denial source when enforce is off (step 6, permit checks, is skipped). This is consistent, but the parenthetical might confuse: in enforce=False, `NOT_IN_PERMIT` denials never happen at all. **Builders must not emit `DENIED NOT_IN_PERMIT` when enforcement is off.**

### 1.3 `tech.md` says pydantic ≥ 2.6 but CONTRACTS never mentions pydantic

**Files:** `.kiro/steering/tech.md` (line 5), `docs/CONTRACTS.md`

CONTRACTS says "immutable" and "frozen dataclasses" are fine. `tech.md` lists pydantic as a core dep. These are compatible (pydantic v2 frozen models satisfy immutability), but **the builder must choose one approach per module and be consistent**. The specs should clarify: use frozen dataclasses (simpler) or pydantic models.

### 1.4 `product.md` says "one border crossing"; CONTRACTS has two places and allows both `go:vault` and `go:library`

**Files:** `.kiro/steering/product.md` (line 13), `docs/CONTRACTS.md` §8

Product says "one border crossing" but the scenario involves crossings in both directions (library → vault, and vault → library is allowed). The golden traces only show one crossing (library → vault), but the permitted actions include `go:library`. **Not a real contradiction** — "one border crossing" describes the demo narrative, not a hard limit. But the builder should not hard-code a single crossing.

### 1.5 `workflow.md` SPEC command references `docs/ROADMAP.md` and `docs/PRD.md`

**Files:** `.kiro/steering/workflow.md` (line 15)

The SPEC command says "Also read `docs/ROADMAP.md` and `docs/PRD.md`." These files don't exist yet — they are being created now. **The builder must create them before running SPEC 1**, or the workflow instruction will fail. This is fine as long as Phase 0 includes creating these docs (it doesn't in BUILD_PLAN, but we're creating them now).

---

## 2. Missing Edge Cases

### 2.1 `go` to the current place

**Files:** `docs/CONTRACTS.md` §5 step 7 (line 65)

CONTRACTS says `go:<p>` where `<p>` equals the current place → `DENIED(NOT_IN_PLACE)`. This is covered, but **the observation's `tools` list includes "one `go` entry per other place"** (§7, line 107). So the agent should never see `go:current_place` as an available tool. Builders must ensure the observation excludes the current place from `go` options. If a proposal somehow names it anyway, the engine denies it.

### 2.2 What happens if the driver returns an action not in the observation's tool list?

**Files:** `docs/CONTRACTS.md` §5, §7

The engine checks against the permit (step 6) and the place (step 7), not against the observation. The observation is informational. A malicious or buggy driver can propose any string. This is fine — the engine handles it. But **the builder should test a "bogus" action** (CONTRACTS §5 line 78 lists `bogus` in the action pool, and it would be denied at step 6 or 7).

### 2.3 `export_records` outbox is in-memory; what if the place is re-created?

**Files:** `docs/CONTRACTS.md` §4 (line 31)

"Tool state lives on the Place instance, so each run builds fresh places." This means the outbox resets per run. **Builders must not share Place instances across runs.** The scenario module must build fresh places for each call.

### 2.4 Negative `cost` on a Tool

**Files:** `docs/CONTRACTS.md` §4 (line 29)

`Tool` has `cost: int >= 0`. The builder must validate this. A negative cost would cause `spent` to decrease, violating invariant 8.

### 2.5 `last_result` after a REFUSED border crossing

**Files:** `docs/CONTRACTS.md` §7 (line 108)

After a refused crossing, `last_result` is `"REFUSED at the border of <place>."` — no reason code is exposed. The agent stays in its current place. **The builder must not leak the REFUSE reason to the agent.**

### 2.6 Float precision in lifetime checks

**Files:** `docs/CONTRACTS.md` §5 step 2 (line 60)

"If `clock.now() - born > state.permit.lifetime_s` → KILL." Exactly equal is allowed. With floating-point arithmetic, `60.0 - 0.0 == 60.0` is safe, but accumulated `advance(1.0)` calls over 60 turns may drift. The `TickClock` should use exact arithmetic or the builder should test the boundary explicitly. Seed spec-03 already requires this unit test.

---

## 3. Ambiguous Requirements

### 3.1 `Admission.permit_after` when decision is REFUSE

**Files:** `docs/CONTRACTS.md` §4 (line 32), §6 (line 94)

§4 says `permit_after: Permit | None` with "None when REFUSE". But §6 (BORDER_CHECK event data) says `permit_after (PermitJSON; the unchanged permit on REFUSE)`. **These contradict**: the model field is `None`, but the event serialises it as the unchanged permit. The builder must:
- Store `None` on the `Admission` object when REFUSE.
- When emitting the `BORDER_CHECK` event, use the *current* permit (unchanged) for the `permit_after` data field.

This is a **potential source of bugs** if the builder naively serialises `Admission.permit_after`.

### 3.2 What does "contiguous from 0" mean for `seq` when the engine is REFUSED at spawn?

**Files:** `docs/CONTRACTS.md` §5 line 81, §8 line 131

Run C (forged identity) has 3 events: seq 0, 1, 2. The property says `seq` is contiguous from 0. This is clear. But does `reduce_events` on a REFUSED run return `status: REFUSED`? Yes — §6 line 102 says "status from RUN_ENDED (else ALIVE)." Run C's RUN_ENDED has status REFUSED. Clear, but builders should test it.

### 3.3 `narrowed_fields` in BORDER_CHECK event

**Files:** `docs/CONTRACTS.md` §6 (line 94)

The BORDER_CHECK event has `narrowed_fields` (list of field names that changed). But this is only meaningful for ADMIT_IMPOSED. For ADMIT (no change), it should be an empty list. For REFUSE, it's ambiguous — CONTRACTS doesn't specify. **Builders should emit an empty list for ADMIT and REFUSE**, and only populate it for ADMIT_IMPOSED.

### 3.4 `cost` field in BORDER_CHECK event

**Files:** `docs/CONTRACTS.md` §6 (line 94)

BORDER_CHECK event has `cost` described as "1 for `go`, else 0". The "else 0" case is the spawn border check (no `go` action, `via_action` is null). This is clear but easy to miss.

### 3.5 `KILLED` event's `observed` field for STEPS_EXCEEDED

**Files:** `docs/CONTRACTS.md` §6 (line 101)

"steps → `max_steps` / `steps + 1`". But by the time the KILLED event is emitted, `steps` has *not* been incremented yet (step 4 checks *before* step 5 increments). Wait — re-reading: step 4 says "If `steps + 1 > max_steps` → KILL". So the kill fires before incrementing. The `observed` value is `steps + 1` (the hypothetical next step count), and `limit` is `max_steps`. But on the event, the `step` snapshot field (post-transition) — what is it? The step was not incremented because the kill happened at step 4, before step 5. **The `step` field on the KILLED event should be the current `steps` value, not `steps + 1`.** The `observed` in `data` is `steps + 1`. This is subtle and must be tested.

### 3.6 `explain` strings

**Files:** `docs/CONTRACTS.md` §1 (line 3)

"Wording of human-readable `explain` strings is informative; codes, numbers and structure are binding." This means the builder has freedom in `explain` wording. Tests should not assert exact `explain` text, only structural fields.

---

## 4. Things That Would Make a Spec-Driven Build Fail

### 4.1 Missing `from __future__ import annotations`

**Files:** `.kiro/steering/tech.md` (line 9)

Tech.md requires this in every module. If a spec task doesn't include it, type annotations using `|` syntax (e.g., `str | None`) will fail on Python 3.11. Every generated module must start with this import.

### 4.2 `from_json` not specified as `@classmethod` or `@staticmethod`

**Files:** `docs/CONTRACTS.md` §2 (line 18)

CONTRACTS says `from_json` is the inverse of `to_json` but doesn't specify whether it's a classmethod or staticmethod. The builder should make it a classmethod (`Permit.from_json(data)`).

### 4.3 `Observation.tools` must include `finish`

**Files:** `docs/CONTRACTS.md` §7 (line 107)

"list of `{name, description, args}` for the current place, **plus one `go` entry per other place, plus `finish`**." The builder must synthesise `finish` and `go` entries in the observation, not just the place's tools.

### 4.4 The architecture test scans `src/telepermit/` but not `tests/`

**Files:** `docs/seeds/spec-03-engine-audit.md` (line 40)

"tests are not scanned." Tests legitimately call `execute` and import engine. The AST walker must exclude test files.

### 4.5 `record_replays.py` lives at repo root, not in `backend/`

**Files:** `.kiro/steering/structure.md` (line 24), `docs/CONTRACTS.md` §10 (line 140)

The script is at `scripts/record_replays.py` (repo root), but it imports from `telepermit` (a package in `backend/src/`). The runner command in BUILD_PLAN is `cd backend && uv run python ../scripts/record_replays.py`. The script must handle this path correctly, or the import will fail. **Builder should ensure the script works from the `backend/` working directory.**

### 4.6 Vitest environment is `node`, not `jsdom`

**Files:** `.kiro/steering/tech.md` (line 15), `docs/seeds/spec-05-timeline-ui.md`

Spec 5 tests should test pure logic (reduceEvents, meter math, index bounds) in a node environment. Component rendering tests that need DOM will fail without jsdom. **The builder should avoid DOM-dependent tests or add jsdom as a dev dependency.** CONTRACTS and tech.md only require `node` environment.

---

## 5. Proposed Changes to CONTRACTS.md

> `docs/CONTRACTS.md` is the source of truth and must not be changed. These are suspected errors or ambiguities that the human should review.

| # | Section | Issue | Suggested clarification |
|---|---|---|---|
| PC-1 | §4 line 32 vs §6 line 94 | `Admission.permit_after` is `None` on REFUSE, but the BORDER_CHECK event's `permit_after` is "the unchanged permit on REFUSE". | Add to §4: "When serialising a REFUSE border check as an event, use the agent's current permit as `permit_after`." |
| PC-2 | §6 line 94 | `narrowed_fields` is not defined for ADMIT (presumably `[]`) or REFUSE (presumably `[]`). | Add: "`narrowed_fields` is `[]` for ADMIT and REFUSE decisions." |
| PC-3 | §5 line 66 | Step 7 says `go:<p>` where `<p>` is "unknown or equals the current place" → DENIED NOT_IN_PLACE. But later (step 11, line 69), `go:<p>` triggers `admit()`. Between steps 7 and 11, should there be an explicit "action is `go:<p>` and `<p>` is a known, different place" guard, or is it implied? | Implied by surviving step 7. No change needed, but a comment would help. |
| PC-4 | §5 line 63 | Step 4: "If `steps + 1 > max_steps` → KILL." The `step` snapshot on the KILLED event: is it the pre-increment value (since step 5 never runs)? | Add: "The KILLED event's snapshot `step` is the value before the increment that was prevented." |
| PC-5 | §8 line 129 | Run B golden trace says "step 17, spent 38" for the KILLED event. Verify: 1 (read_doc) + 1 (go:vault) + 2 (denied × 2) + 12 (read_records) + 1 (attempted read_records) = 17 steps. Spent: 1 + 1 + 0 + 0 + 36 = 38. The kill is because the *next* read_records (cost 3) would make spent = 41 > 40. This checks out. But the KILLED event's `step` field should be 17 (after increment at step 5) because the kill happens at step 8 (allowance check), which is *after* step 5 (increment). | Actually, re-reading: step 4 checks `steps + 1 > max_steps` (this is the steps-exceeded kill). The allowance kill is at step 8, which is *after* step 5 increments. So for ALLOWANCE_EXCEEDED, steps *was* incremented. The event `step` = 17. Spent = 38 (not incremented because the action didn't run). `observed` = 38 + 3 = 41. This is consistent. No change needed. |

