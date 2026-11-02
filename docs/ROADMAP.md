# TelePermit — Roadmap

> Phases and dates are taken verbatim from `docs/BUILD_PLAN.md`.  
> `docs/CONTRACTS.md` is the source of truth for all names, numbers and behaviour.

---

## Phase 0: Scaffold + Hooks — Nov 2–3

### T0.1 Repo checks
- **Goal:** Verify the repo has a GitHub remote, an MIT/Apache-2.0 licence, and `.kiro` is not git-ignored.
- **Files:** (reads only) `LICENSE`, `.gitignore`
- **Dependencies:** None (precondition: human has cloned repo)
- **Acceptance:** `git remote -v` shows GitHub; `head -3 LICENSE` shows MIT; `git check-ignore -v .kiro` prints nothing.
- **Edge cases:** `.kiro` already in `.gitignore` from a template; licence is a different SPDX id.
- **Test:** Shell assertions in the task (no code test).
- **Size:** S
- **Model tier:** cheap — purely mechanical checks.

### T0.2 Backend scaffold
- **Goal:** Create `backend/pyproject.toml`, `src/telepermit/__init__.py`, and `tests/test_smoke.py`; install and verify.
- **Files:** `backend/pyproject.toml`, `backend/src/telepermit/__init__.py`, `backend/tests/test_smoke.py`
- **Dependencies:** T0.1
- **Acceptance:** `cd backend && uv run pytest -q` passes; `uv run ruff check .` clean.
- **Edge cases:** `uv` not installed — fallback to `python -m venv` + `pip install -e ".[dev]"`.
- **Test:** `test_smoke.py` asserts `telepermit.__version__ == "0.1.0"`.
- **Size:** S
- **Model tier:** cheap — boilerplate generation.

### T0.3 Frontend scaffold
- **Goal:** Hand-write `frontend/` with Vite + React + TS config, placeholder app, smoke test.
- **Files:** `frontend/package.json`, `frontend/index.html`, `frontend/tsconfig.json`, `frontend/vite.config.ts`, `frontend/src/main.tsx`, `frontend/src/App.tsx`, `frontend/src/styles.css`, `frontend/src/smoke.test.ts`
- **Dependencies:** T0.1
- **Acceptance:** `cd frontend && npm run build && npm test` both pass.
- **Edge cases:** `tsconfig.node.json` needed by some Vite versions; vitest env must be `node` (not jsdom).
- **Test:** `smoke.test.ts` — one trivial passing assertion.
- **Size:** M
- **Model tier:** cheap — known-pattern scaffolding.

### T0.4 Repo files
- **Goal:** Create `frontend/public/replays/.gitkeep`, `README.md` stub, `.github/workflows/ci.yml`.
- **Files:** `frontend/public/replays/.gitkeep`, `README.md`, `.github/workflows/ci.yml`
- **Dependencies:** T0.2, T0.3
- **Acceptance:** CI workflow YAML matches BUILD_PLAN exactly; README has title, one-line pitch, status, licence.
- **Edge cases:** README must not contain Telescript claims beyond `telescript-facts.md`.
- **Test:** Human verifies CI green after push.
- **Size:** S
- **Model tier:** cheap — copy-paste from BUILD_PLAN.

### T0.5 Commit and handoff
- **Goal:** Tick Phase 0 in PROGRESS.md, commit, tell the human to `PUSH` then `HOOKS`.
- **Files:** `docs/PROGRESS.md`
- **Dependencies:** T0.2, T0.3, T0.4
- **Acceptance:** `git status` shows one clean commit; exit criteria met (pytest, ruff, build, test all green).
- **Edge cases:** None.
- **Test:** N/A (process step).
- **Size:** S
- **Model tier:** cheap.

### T0.6 Create Kiro hooks
- **Goal:** Walk the human through creating 5 hooks from `docs/HOOKS.md` in the Kiro UI.
- **Files:** `.kiro/hooks/` (created by Kiro UI, committed by human)
- **Dependencies:** T0.5
- **Acceptance:** `git ls-files .kiro/hooks` lists hook files; commit `chore: add kiro hooks`.
- **Edge cases:** Hook fires on every save (credit cost) — disable property guard during large generations.
- **Test:** Save a matching file and confirm the hook triggers.
- **Size:** S
- **Model tier:** cheap — human-guided, no code generation.

> **Checkpoint: Nov 3** — Phase 0 complete. Backend pytest + ruff green, frontend build + test green, `.kiro` tracked, CI workflow committed.

---

## Spec 1: Permit + Identity — Nov 3–6

### T1.1 Permit dataclass
- **Goal:** Implement immutable `Permit` with `lifetime_s`, `max_steps`, `allowance`, `allowed_actions`; validation raises `ValueError` on negatives.
- **Files:** `backend/src/telepermit/permit.py`
- **Dependencies:** T0.2
- **Acceptance:** `from telepermit.permit import Permit` works; `Permit(lifetime_s=-1, ...)` raises `ValueError`.
- **Edge cases:** Zero values are valid; `allowed_actions` as empty frozenset; float vs int for `lifetime_s`.
- **Test:** Unit test for negative-value `ValueError`.
- **Size:** S
- **Model tier:** cheap — simple dataclass.

### T1.2 `narrowed_by` method
- **Goal:** `Permit.narrowed_by(ceiling)` returns a new Permit using `min` for numeric fields and set intersection for `allowed_actions`.
- **Files:** `backend/src/telepermit/permit.py`
- **Dependencies:** T1.1
- **Acceptance:** `p.narrowed_by(c)` returns correct results for known inputs.
- **Edge cases:** Disjoint action sets → empty; identical permits → equal result; ceiling with zero fields.
- **Test:** Properties P1.1 (never widens) and P1.2 (idempotent).
- **Size:** S
- **Model tier:** cheap.

### T1.3 Permit JSON serialisation
- **Goal:** `to_json()` returns dict with `allowed_actions` as a sorted list; `from_json()` is the inverse.
- **Files:** `backend/src/telepermit/permit.py`
- **Dependencies:** T1.1
- **Acceptance:** Round-trip produces an equal `Permit`.
- **Edge cases:** Empty action list; unicode action names; float precision for `lifetime_s`.
- **Test:** Property P1.3 (JSON round-trip lossless for any valid permit).
- **Size:** S
- **Model tier:** cheap.

### T1.4 Authority and Identity
- **Goal:** `Authority(name)` generates a random Ed25519 key. `Authority.from_seed(name, seed)` derives from `sha256(seed)`. `issue()` signs the canonical JSON payload. `Identity` is immutable with `signature_hex`.
- **Files:** `backend/src/telepermit/identity.py`
- **Dependencies:** T0.2
- **Acceptance:** `authority.issue(...)` returns an `Identity` whose `signature_hex` is 128 hex chars.
- **Edge cases:** Seed must produce deterministic keys (P1.7); docstring on `from_seed` must say "DEMO ONLY"; `repr(authority)` must not leak key material.
- **Test:** Property P1.7 (same seed → identical sigs; different seed → different pubkeys). Unit test: `repr` check.
- **Size:** M
- **Model tier:** Auto — crypto correctness benefits from careful reasoning.

### T1.5 `verify_identity`
- **Goal:** Returns `None` if valid, `"UNTRUSTED_AUTHORITY"` if authority not in trusted map, `"BAD_SIGNATURE"` otherwise. Never raises.
- **Files:** `backend/src/telepermit/identity.py`
- **Dependencies:** T1.4
- **Acceptance:** Known-good identity verifies; tampered identity returns `BAD_SIGNATURE`.
- **Edge cases:** Empty signature bytes; signature of length 0 to 200; empty trusted map; authority name present but wrong key.
- **Test:** Properties P1.4 (bit-flip → BAD_SIGNATURE), P1.5 (wrong key → BAD_SIGNATURE; empty trust → UNTRUSTED_AUTHORITY), P1.6 (never raises for arbitrary signature bytes).
- **Size:** M
- **Model tier:** Auto — must handle all edge cases without raising.

> **Checkpoint: Nov 6** — Spec 1 merged. 7 properties pass, pytest + ruff clean. Branch `spec/01-permit-identity` merged, tag `spec-01-done`.

---

## Spec 2: Tools + Places + Admission — Nov 7–10

### T2.1 Tool and Place models
- **Goal:** Implement `Tool` (name, cost, description, args, fn) and `Place` (name, tools, ceiling, trusted, allowed_classes) with `has_tool`, `tool_cost`, `execute`.
- **Files:** `backend/src/telepermit/tools.py`, `backend/src/telepermit/place.py`
- **Dependencies:** Spec 1 (Permit, Identity)
- **Acceptance:** Can construct a Place with Tools, call `has_tool`, `tool_cost`, `execute`.
- **Edge cases:** Unknown tool name in `execute` raises a clear error; tool state (page counter, outbox) lives on the Place instance, so each run needs fresh places.
- **Test:** Unit test for unknown tool error; property P2.5 (deterministic tool results).
- **Size:** M
- **Model tier:** cheap — straightforward models.

### T2.2 Tool catalog implementation
- **Goal:** Build the four scenario tools (`read_document`, `search_archive`, `read_records`, `export_records`) exactly per CONTRACTS §4.
- **Files:** `backend/src/telepermit/tools.py`
- **Dependencies:** T2.1
- **Acceptance:** `read_document({"name": "briefing-q3"})` returns the exact document text; `read_records` returns `"records page N"` with incrementing N; `export_records` appends to outbox.
- **Edge cases:** `read_document` with unknown name → `"no such document"`; `search_archive` for any query; `export_records` outbox length = number of successful calls.
- **Test:** Unit tests for exact catalog numbers and document text from CONTRACTS §8.
- **Size:** S
- **Model tier:** cheap.

### T2.3 Admission logic
- **Goal:** `Place.admit(identity, permit, steps, spent, elapsed)` returns `Admission` with the exact 4-step check order from CONTRACTS §4.
- **Files:** `backend/src/telepermit/place.py`
- **Dependencies:** T2.1, Spec 1
- **Acceptance:** Untrusted authority → REFUSE; wrong class → REFUSE CLASS_NOT_ALLOWED; counters exceed ceiling → REFUSE EXCEEDS_CEILING; narrowing changes nothing → ADMIT; otherwise → ADMIT_IMPOSED.
- **Edge cases:** All counters at exactly the limit (boundary: `spent == allowance` → should that refuse? CONTRACTS says `spent > n.allowance` → refuse, so equal is admitted); `elapsed` exactly equals `lifetime_s` → admitted.
- **Test:** Properties P2.1 (permit_after never wider), P2.2 (bad identity/class always refused), P2.3 (ADMIT iff no change), P2.4 (exceeds → REFUSE).
- **Size:** M
- **Model tier:** Auto — the admission check order is subtle and must match CONTRACTS exactly.

> **Checkpoint: Nov 10** — Spec 2 merged. 5 properties pass, all catalog tools tested. Tag `spec-02-done`.

---

## Spec 3: Engine + Audit — Nov 11–14

### T3.1 Clock and Event models
- **Goal:** `Clock` protocol with `now()`, `TickClock(start)` with `advance(dt)`. `Event` model with `seq`, `t`, `type`, `place`, `step`, `spent`, `data`. All event types per CONTRACTS §6.
- **Files:** `backend/src/telepermit/clock.py`, `backend/src/telepermit/audit.py`
- **Dependencies:** Spec 1 (PermitJSON)
- **Acceptance:** `TickClock(0.0)` starts at 0; `advance(1.0)` makes `now()` return 1.0. Events can be constructed for all types.
- **Edge cases:** `advance` with 0 or negative dt; float precision in timestamps.
- **Test:** Unit tests for clock advancement; event construction.
- **Size:** S
- **Model tier:** cheap.

### T3.2 `reduce_events` and JSONL writer
- **Goal:** `reduce_events(events)` returns `{place, step, spent, permit, status}` from the event list. JSONL writer: one `json.dumps(event, sort_keys=True)` per line.
- **Files:** `backend/src/telepermit/audit.py`
- **Dependencies:** T3.1
- **Acceptance:** Reduce of the golden Run B events returns `{place: "vault", step: 17, spent: 38, permit: {allowance: 40, ...}, status: "KILLED"}`.
- **Edge cases:** Empty event list; events with no RUN_ENDED (status = ALIVE); events with no BORDER_CHECK (permit from RUN_STARTED).
- **Test:** Property P3.5 (reduce equals engine's final snapshot for any action sequence).
- **Size:** S
- **Model tier:** cheap.

### T3.3 Driver protocol
- **Goal:** Define `Proposal`, `Observation`, and `AgentDriver` protocol in `drivers/base.py`. Observation contains only the fields in CONTRACTS §7 — never permit, spend, costs, steps, or keys.
- **Files:** `backend/src/telepermit/drivers/__init__.py`, `backend/src/telepermit/drivers/base.py`
- **Dependencies:** None (protocol only)
- **Acceptance:** Can instantiate a `Proposal` and `Observation`.
- **Edge cases:** Observation `last_result` for DENIED must be exactly `"DENIED: action '<action>' is not available to you here."` — never mentions permits or limits.
- **Test:** Property P4.2 will test observation text in Spec 4.
- **Size:** S
- **Model tier:** cheap.

### T3.4 Engine construction and spawn border check
- **Goal:** `Engine(places, identity, permit, start_place, clock, enforce)` records `born`, emits `RUN_STARTED`. With enforcement, runs `admit()` at the start place; REFUSE → status REFUSED, emit `RUN_ENDED(REFUSED)`.
- **Files:** `backend/src/telepermit/engine.py`
- **Dependencies:** T3.1, T3.3, Spec 2
- **Acceptance:** Constructing an Engine with a forged identity + enforce=True → status REFUSED, 3 events (RUN_STARTED, BORDER_CHECK REFUSE, RUN_ENDED REFUSED).
- **Edge cases:** `enforce=False` → no spawn border check; start place not in places dict.
- **Test:** Property P3.9 (forged identity → REFUSED trace). Unit test for the forged-identity golden trace (Run C).
- **Size:** M
- **Model tier:** Auto — spawn logic must match CONTRACTS §5 exactly.

### T3.5 Engine `step()` — enforce=True
- **Goal:** Implement the 11-step algorithm from CONTRACTS §5 exactly: lifetime check, finish, step limit, step increment, permit check, place check, allowance check, cost, execute/go, KILL semantics.
- **Files:** `backend/src/telepermit/engine.py`
- **Dependencies:** T3.4
- **Acceptance:** Hand-drive the engine through the golden Run B sequence and get 20 events matching CONTRACTS §8.
- **Edge cases:** Lifetime exactly equal to permit → allowed (not killed); `finish` costs 0 and consumes no step; denied actions consume a step but not cost; `go` to current place → DENIED NOT_IN_PLACE; `go` cost charged even on REFUSE at border; KILL sets status before emitting events.
- **Test:** Properties P3.1 (spent ≤ allowance while alive), P3.2 (after KILLED only RUN_ENDED), P3.3 (contiguous seq), P3.4 (monotonic counters), P3.6 (TOOL_CALL matches place), P3.7 (denied loop → KILLED STEPS_EXCEEDED).
- **Size:** L
- **Model tier:** Auto — this is the most complex and critical module, with subtle ordering constraints.

### T3.6 Engine `step()` — enforce=False
- **Goal:** No limit checks or kills; step 7 still applies (NOT_IN_PLACE still denies and consumes a step); `go` moves immediately with `BORDER_CHECK(ADMIT, UNENFORCED)`; spend and steps still metered.
- **Files:** `backend/src/telepermit/engine.py`
- **Dependencies:** T3.5
- **Acceptance:** Run A golden trace (32 events, HARNESS_CAP, spent 120, 2 exports).
- **Edge cases:** NOT_IN_PLACE denial still consumes a step even with enforce=False; spend can exceed allowance.
- **Test:** Property P3.8 (no KILLED, no permit-reason DENIED, spend may exceed allowance).
- **Size:** M
- **Model tier:** Auto — must carefully carve out exactly which checks are skipped.

### T3.7 Engine `run()` loop
- **Goal:** Loop up to `max_turns`: stop if not ALIVE; advance clock by `TICK_S`; build Observation; call driver; call `step`. After loop, if still ALIVE → HARNESS_CAP.
- **Files:** `backend/src/telepermit/engine.py`
- **Dependencies:** T3.5, T3.6
- **Acceptance:** A 30-step script with `TICK_S=1.0` produces `clock.now() == 30.0` after the loop.
- **Edge cases:** `max_turns=0` → immediately HARNESS_CAP; agent finishes mid-loop.
- **Test:** Unit test for HARNESS_CAP status after max_turns exceeded.
- **Size:** S
- **Model tier:** cheap.

### T3.8 Architecture test
- **Goal:** Parse source with `ast`. Fail if any driver module imports engine/identity/place/tools; fail if any non-engine module calls `.execute()`.
- **Files:** `backend/tests/test_architecture.py`
- **Dependencies:** T3.3, T3.5
- **Acceptance:** Test passes on current source; a deliberately bad snippet is caught by the self-test.
- **Edge cases:** Method *definitions* named `execute` are fine (only calls flagged); test files are not scanned.
- **Test:** Self-test with a bad snippet.
- **Size:** S
- **Model tier:** cheap — AST walking is mechanical.

> **Checkpoint: Nov 14** — Spec 3 merged. 9 properties + architecture test pass. Tag `spec-03-done`.

---

## Spec 4: Scenario + Drivers + Replays + CLI (M1) — Nov 15–20

### T4.1 ScriptedDriver
- **Goal:** `ScriptedDriver(script, repeat_last=True)` returns proposals in order, repeating the last one.
- **Files:** `backend/src/telepermit/drivers/scripted.py`
- **Dependencies:** T3.3 (driver protocol)
- **Acceptance:** A 3-element script with `repeat_last=True` returns element 3 for turns 4, 5, …
- **Edge cases:** `repeat_last=False` → raises or returns `finish` after script exhausted; empty script.
- **Test:** Property P4.1 (deterministic for any script and length).
- **Size:** S
- **Model tier:** cheap.

### T4.2 Poisoned-briefing scenario
- **Goal:** Build fresh places, identity, permit, clock exactly per CONTRACTS §8. Wire the scripted proposals.
- **Files:** `backend/src/telepermit/scenarios/__init__.py`, `backend/src/telepermit/scenarios/poisoned_briefing.py`
- **Dependencies:** T4.1, Specs 1–3
- **Acceptance:** Running enforce=True produces 20 events matching Run B; enforce=False produces 32 events matching Run A.
- **Edge cases:** Authority from seed must be deterministic (`from_seed("home-authority", b"telepermit-demo-authority")`); the document text must be character-exact; the scripted proposals must match CONTRACTS §8.
- **Test:** Property P4.3 (golden trace match field-for-field). Unit tests for Run B (20 events, KILLED, outbox empty) and Run A (32 events, HARNESS_CAP, spent 120, 2 exports).
- **Size:** M
- **Model tier:** Auto — golden-trace matching requires exact fidelity to CONTRACTS.

### T4.3 Observation text safety
- **Goal:** Verify no Observation ever contains `permit`, `allowance`, `teleclick`, or private-key hex.
- **Files:** Tests in `backend/tests/properties/`
- **Dependencies:** T4.2
- **Acceptance:** P4.2 passes for Run A and Run B.
- **Edge cases:** Compute expected private-key hex from `sha256(b"telepermit-demo-authority").digest().hex()` and check it does not appear.
- **Test:** Property P4.2.
- **Size:** S
- **Model tier:** cheap.

### T4.4 LLM driver
- **Goal:** `LLMDriver(client, model)` maps observations to the Anthropic tool-calling API, returns first tool call as a Proposal, keeps message history, never executes tools.
- **Files:** `backend/src/telepermit/drivers/llm.py`
- **Dependencies:** T3.3
- **Acceptance:** With a fake client, returns valid Proposals for tool-use responses.
- **Edge cases:** Response with no tool call → propose `finish`; client injection so tests never hit the network; model name only from `AGENT_MODEL`.
- **Test:** Property P4.6 (fake client, valid proposals, zero engine calls).
- **Size:** M
- **Model tier:** Auto — API mapping requires careful reasoning.

### T4.5 CLI
- **Goal:** `python -m telepermit.cli run poisoned_briefing --enforce on|off [--driver scripted|llm] [--out FILE]`. Print readable timeline, final status, outbox count. `--out` writes replay JSON. Missing env vars → clear message + exit.
- **Files:** `backend/src/telepermit/cli.py`, `backend/src/telepermit/__main__.py` (if needed)
- **Dependencies:** T4.2, T4.4
- **Acceptance:** `--enforce on` ends with KILLED; `--enforce off` ends with HARNESS_CAP.
- **Edge cases:** `--driver llm` without `ANTHROPIC_API_KEY` or `AGENT_MODEL` → exit non-zero, no network call.
- **Test:** Unit tests for CLI exit codes, output, missing env vars.
- **Size:** M
- **Model tier:** cheap — CLI plumbing.

### T4.6 Replay recorder
- **Goal:** `scripts/record_replays.py` writes `index.json` and replay files to `frontend/public/replays/`. Byte-identical on every run.
- **Files:** `scripts/record_replays.py`, `frontend/public/replays/index.json`, `frontend/public/replays/*.json`
- **Dependencies:** T4.2, T4.5
- **Acceptance:** Running twice leaves `git status` clean the second time.
- **Edge cases:** `json.dumps(sort_keys=True, indent=2)` + trailing newline; schema_version = 1; replay ids match CONTRACTS §9; `driver: "scripted"`.
- **Test:** Property P4.4 (recording twice = byte-identical). `test_replays.py` checks schema, contiguous seq, golden facts, reduce == final snapshot.
- **Size:** M
- **Model tier:** cheap.

### T4.7 Forged-identity replay (optional)
- **Goal:** Record Run C (forged identity) if time permits.
- **Files:** `scripts/record_replays.py`, `frontend/public/replays/forged-identity-refused.json`
- **Dependencies:** T4.6
- **Acceptance:** 3-event trace: RUN_STARTED, BORDER_CHECK REFUSE BAD_SIGNATURE, RUN_ENDED REFUSED.
- **Edge cases:** Identity signature = 64 zero bytes.
- **Test:** `test_replays.py` covers it if present.
- **Size:** S
- **Model tier:** cheap.

> **Checkpoint: Nov 20 — MILESTONE M1.** CLI demo works, replays recorded, `test_replays.py` green. Tag `spec-04-done` + `m1-core`.

---

## Spec 5: Timeline UI — Nov 21–26

### T5.1 TypeScript types and `reduceEvents`
- **Goal:** Define replay and event types matching CONTRACTS. Implement `reduceEvents` identical in behaviour to the Python `reduce_events`.
- **Files:** `frontend/src/types.ts`, `frontend/src/reduce.ts`
- **Dependencies:** Spec 4 (replay files exist)
- **Acceptance:** `reduceEvents` of the enforced replay events matches the final snapshot.
- **Edge cases:** Empty events array; events without RUN_ENDED; permit from last BORDER_CHECK or RUN_STARTED.
- **Test:** Property P5.1 (for every replay and every prefix, reduce matches snapshot). P5.4 (parse against types; enforced last event is KILLED).
- **Size:** M
- **Model tier:** cheap — port existing logic.

### T5.2 `useReplay` hook
- **Goal:** Custom hook: fetch index + replay, play/pause/step/scrub/speed, expose current event index.
- **Files:** `frontend/src/useReplay.ts`
- **Dependencies:** T5.1
- **Acceptance:** Index is always within `[0, events.length - 1]`.
- **Edge cases:** Empty replay; rapid step-forward past end; step-back below 0; speed changes mid-play.
- **Test:** Property P5.2 (index never out of bounds under any action sequence).
- **Size:** M
- **Model tier:** cheap.

### T5.3 Place cards and agent token
- **Goal:** Two place cards (Library, Vault) with a border between them, agent token in current place, badge for latest border decision.
- **Files:** `frontend/src/components/PlaceCard.tsx`
- **Dependencies:** T5.1, T5.2
- **Acceptance:** Agent appears in the correct place; badge reads ADMITTED / ADMITTED UNDER IMPOSED PERMIT / REFUSED.
- **Edge cases:** Agent REFUSED at spawn (never enters a place visually); ADMIT vs ADMIT_IMPOSED badge text.
- **Test:** Visual + component-level test for badge text.
- **Size:** M
- **Model tier:** cheap.

### T5.4 Meters
- **Goal:** Allowance (spent/allowance), steps, lifetime meters computed from events and replay meta. Over-limit state with text + colour (not colour alone).
- **Files:** `frontend/src/components/Meters.tsx`
- **Dependencies:** T5.1, T5.2
- **Acceptance:** Spent > allowance shows explicit over-limit text.
- **Edge cases:** Allowance = 0 (division by zero in percentage); unenforced run where spent far exceeds allowance; bar clamped at 100% visually.
- **Test:** Property P5.3 (correct percentage, clamped bar, over-limit flag = spent > allowance).
- **Size:** M
- **Model tier:** cheap.

### T5.5 Permit card with narrowed-field highlights
- **Goal:** Show current permit as a card; highlight which fields were narrowed by an imposed permit.
- **Files:** `frontend/src/components/PermitCard.tsx` (or within `Meters.tsx`)
- **Dependencies:** T5.1
- **Acceptance:** After vault border check, `allowance` and `allowed_actions` are highlighted.
- **Edge cases:** No narrowing (ADMIT) → no highlights; all fields narrowed.
- **Test:** Unit test with known narrowed_fields array.
- **Size:** S
- **Model tier:** cheap.

### T5.6 Timeline and EventDetail
- **Goal:** Colour-coded event timeline with text labels; clicking an event shows JSON and `explain` text.
- **Files:** `frontend/src/components/Timeline.tsx`, `frontend/src/components/EventDetail.tsx`
- **Dependencies:** T5.1, T5.2
- **Acceptance:** All events visible; clicking KILLED shows reason, limit, observed.
- **Edge cases:** Very long event lists (30+ events); events with no `explain`; keyboard focus/selection.
- **Test:** Render test for event count; accessibility: keyboard-focusable controls.
- **Size:** M
- **Model tier:** cheap.

### T5.7 ReplayPicker and CompareView
- **Goal:** Picker loads replay index; compare view plays enforced and unenforced side by side, synchronised by turn.
- **Files:** `frontend/src/components/ReplayPicker.tsx`, `frontend/src/components/CompareView.tsx`
- **Dependencies:** T5.2, T5.3, T5.4, T5.6
- **Acceptance:** Compare view shows both replays; stepping advances both.
- **Edge cases:** Replays of different lengths (one ends earlier); synchronisation when one replay is KILLED and the other continues.
- **Test:** Property P5.5 (for any turn, both sides select a valid event index).
- **Size:** M
- **Model tier:** Auto — sync logic is tricky.

### T5.8 Honesty note and labels
- **Goal:** Permanent note: "An injection that stays inside the permit is not stopped." Every replay labelled "scripted agent" or "live LLM" from the `driver` field.
- **Files:** `frontend/src/components/Note.tsx`, integrated into `App.tsx`
- **Dependencies:** T5.7
- **Acceptance:** Note always visible; label matches `driver` field.
- **Edge cases:** Future live-LLM replays should auto-label.
- **Test:** Visual / unit test for label rendering.
- **Size:** S
- **Model tier:** cheap.

### T5.9 KILLED event styling
- **Goal:** KILLED event is unmistakable: red, large, shows reason, limit, and observed values.
- **Files:** `frontend/src/styles.css`, `frontend/src/components/Timeline.tsx`
- **Dependencies:** T5.6
- **Acceptance:** KILLED event is visually dominant; reason text is readable.
- **Edge cases:** Multiple kill reasons (only one can happen per run); reduced-motion users.
- **Test:** Visual test.
- **Size:** S
- **Model tier:** cheap.

### T5.10 Styles and accessibility
- **Goal:** Retro terminal theme (amber on dark, monospace system font), CSS `prefers-reduced-motion`, no external fonts, no third-party logos.
- **Files:** `frontend/src/styles.css`
- **Dependencies:** All components
- **Acceptance:** `npm run build` succeeds; no network requests other than replay files; keyboard navigation works.
- **Edge cases:** High-contrast mode; very narrow viewports; system font stack fallback.
- **Test:** Build test; manual accessibility check.
- **Size:** M
- **Model tier:** cheap — CSS only.

> **Checkpoint: Nov 26** — Spec 5 merged. `npm run build && npm test` pass. Human runs `npm run dev`, verifies both replays play, compare view works, KILLED is obvious. Tag `spec-05-done`.

---

## Phase 6: CI, Deploy, Docs — Nov 27–29

### T6.1 GitHub Pages workflow
- **Goal:** Create `.github/workflows/pages.yml` exactly per BUILD_PLAN. Verify `npm run build` output loads replays via relative URLs.
- **Files:** `.github/workflows/pages.yml`
- **Dependencies:** Spec 5
- **Acceptance:** Pages workflow green; public URL loads both replays with no API key.
- **Edge cases:** `base: './'` in vite.config.ts; deprecated action versions.
- **Test:** Human verifies live URL in a private browser window.
- **Size:** S
- **Model tier:** cheap.

### T6.2 README
- **Goal:** Full README per BUILD_PLAN §6.2: title, pitch, live demo link, 3-command quickstart, "Why this exists", architecture diagram (ASCII), Telescript facts (verified / interpretation / our design), threat model summary, honest notes (scripted vs live, what permits don't stop), Kiro usage, disclosure, DEMO-ONLY key note, licence.
- **Files:** `README.md`
- **Dependencies:** T6.1
- **Acceptance:** All sections present; no Telescript claims beyond `telescript-facts.md`.
- **Edge cases:** Live URL placeholder until human pastes it.
- **Test:** Fact-guard hook (#3) runs on save.
- **Size:** M
- **Model tier:** cheap.

### T6.3 Architecture and threat-model docs
- **Goal:** `docs/architecture.md` (components, event flow, trust boundary, file map). `docs/threat-model.md` (stopped / not stopped / out of scope, each with example, plus invariants list).
- **Files:** `docs/architecture.md`, `docs/threat-model.md`
- **Dependencies:** T6.2
- **Acceptance:** Both documents exist and reference correct module names.
- **Edge cases:** Threat model must honestly list "not stopped" cases.
- **Test:** Fact-guard hook.
- **Size:** M
- **Model tier:** cheap.

> **Checkpoint: Nov 29** — Phase 6 complete. Pages green, public URL works, README complete.

---

## Bug-bash + Freeze — Nov 30–Dec 1

### T-BB.1 Full test suite
- **Goal:** Run backend pytest + ruff + frontend build + vitest. Fix any failures.
- **Files:** (varies)
- **Dependencies:** All specs
- **Acceptance:** All pass.
- **Size:** S–L (depends on findings)
- **Model tier:** Auto.

### T-BB.2 FREEZE
- **Goal:** Declare freeze in PROGRESS.md. Only bug fixes, docs, and submission assets from now on.
- **Files:** `docs/PROGRESS.md`
- **Dependencies:** T-BB.1
- **Acceptance:** PROGRESS.md records freeze date.
- **Size:** S
- **Model tier:** cheap.

> **Checkpoint: Dec 1** — Feature freeze.

---

## Phase 7: Submission Assets — Dec 2

### T7.1 AUDIT
- **Goal:** Run the 13-point audit from `docs/SUBMISSION.md` and print a PASS/FAIL table.
- **Files:** (reads only)
- **Dependencies:** All phases
- **Acceptance:** All automated checks PASS.
- **Edge cases:** Human-only items (video, blog, social) reported separately.
- **Test:** The audit itself.
- **Size:** S
- **Model tier:** cheap.

### T7.2 Submission drafts
- **Goal:** Draft text description and Kiro write-up from `docs/kiro-journal.md` per SUBMISSION.md templates.
- **Files:** (Devpost form, not in repo)
- **Dependencies:** T7.1
- **Acceptance:** Human reviews and edits before submitting.
- **Edge cases:** Disclosure statement must be included.
- **Test:** Human review.
- **Size:** S
- **Model tier:** cheap.

### T7.3 Submit on Devpost
- **Goal:** Human submits. Target: Dec 3. Hard deadline: Dec 4, 2:00 PM PT.
- **Files:** N/A
- **Dependencies:** T7.1, T7.2
- **Acceptance:** Submission confirmed on Devpost.
- **Size:** S (human task)
- **Model tier:** N/A.

> **Checkpoint: Dec 3** — Submitted.

