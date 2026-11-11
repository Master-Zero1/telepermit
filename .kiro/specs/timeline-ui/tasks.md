# Implementation Plan: Timeline UI

## Overview

Build the static React + TypeScript timeline UI in `frontend/` in one group. The order is: colour and style rules first (styles.css guarded by `styles.backgrounds`, then the contrast module), then the ROADMAP items T5.1 to T5.8 in ROADMAP order, then the remaining static guards, then a final checkpoint. Every top-level task follows write test, owner red, implement, owner green, commit. Requirement numbers are the integer numbers of requirements.md (for example 3.8). Property ids use the design numbering, for example "Property 3 (P5.3)".

## Execution rules

- Baseline measured by the owner: `npm --prefix frontend test` gives Test Files 1 passed (1), Tests 1 passed (1), vitest v3.2.7. The only existing test is `frontend/src/smoke.test.ts`; it must stay green throughout. Final counts are reported as baseline 1 plus the new tests, from real runs pasted by the owner.
- The agent sandbox cannot run vitest reliably (two runs hung with no output). EVERY test step is a hand-off: the agent writes the test, states the exact command and the expected red reason, the owner runs the command and pastes the summary, and only then does the agent implement. The green check after implementing is the same kind of hand-off. Build checks (`npm --prefix frontend run build`) are also owner-run hand-offs.
- Commands are exactly `npm --prefix frontend test -- <file>` (file path relative to frontend, for example `src/contrast.test.ts`) or `npm --prefix frontend run build`.
- Each top-level task is committed (local commit, conventional message with task id, files staged by name, `git status --short` first, never stage `.kiro/settings/mcp.json`) only when the owner's pasted run is green, and before the next task's tests are written.
- No task is optional: nothing is marked with `*`. Property-test sub-tasks are required.
- Red reasons marked 'to be confirmed from paste' are expectations, not facts. A red is confirmed only by the owner's pasted run. If the pasted run fails for any reason other than the stated one, or does not fail, stop and report; do not implement.
- Stop rule: if `tsc -b` rejects anything beyond `node:fs` typing, stop and ask the owner before adding `tsconfig.test.json`.
- No new dependency, no Tailwind, no external request, system fonts only, strict TypeScript, no `any`, no non-null assertion.
- Do not edit requirements.md, design.md or docs/PROGRESS.md in this plan. Do not push.

## Tasks

- [ ] 1. Colour rules and styling foundation (styling base for T5.3 to T5.7)
  - [x] 1.1 Create test scaffolding and the vitest include glob
    - No red step: this task creates scaffolding only (no new test file). Pre-check before any file is created: owner runs `npm --prefix frontend run build` to record a build baseline (the test baseline is already recorded: 1 file, 1 test).
    - Create `frontend/src/test-types/node-fs.d.ts` declaring only `node:fs` with `readFileSync(path: URL, encoding: 'utf8'): string` and `readdirSync(path: URL): string[]`. No app module imports it.
    - Create `frontend/src/test/seeded.ts`: the mulberry32 Seeded_Generator (seed in, deterministic `next()`, `int(min, max)`, `pick`).
    - Create `frontend/src/test/replays.ts`: reads the real files from `public/replays/` with `node:fs` and `new URL(..., import.meta.url)`; exports raw index, raw replay by file name, and the list of index entries.
    - Edit `frontend/vite.config.ts`: add `test.include: ['src/**/*.test.ts']`; `base: './'` and `environment: 'node'` stay unchanged.
    - Hand-off check 1: owner runs `npm --prefix frontend test`. Expected: still Test Files 1 passed (1), Tests 1 passed (1).
    - Hand-off check 2: owner runs `npm --prefix frontend run build`. Expected: green. If `tsc -b` rejects anything beyond `node:fs`, STOP and ask the owner.
    - Any result other than the expected one is a stop.
    - _Requirements: 10.4, 10.5, 10.6, 10.8_

  - [x] 1.2 Write `src/static.test.ts` with only the `styles.backgrounds` describe block
    - Read `src/styles.css` through the `node:fs` shim and parse rules into selector and declarations.
    - The FIRST assertion (first `it`) checks that the required tint rule exists: the rule for `.timeline-event.selected` sets `background` to `var(--amber-glow)`.
    - Remaining checks: every `background` / `background-color` value is `var(--bg)`, `var(--bg-surface)`, `var(--bg-inset)`, `transparent` or `none`, except the tint rules (`--red-glow` only in `.timeline-event.killed` / `.timeline-event.run-ended-killed`, `--amber-glow` only in `.timeline-event.selected`; each tint rule sets `color: var(--amber)`) and exactly three solid-fill selectors (`.meter-fill.ok` with `var(--green)`, `.meter-fill.over` with `var(--red)`, `.dot` with `var(--dot-color)`); every `--dot-color` assignment is one of `var(--red)`, `var(--green)`, `var(--blue)`, `var(--orange)`, `var(--purple)`, `var(--amber)`; no `rgba(`, `hsla(` or `#rrggbbaa`; no `opacity` below 1 on a rule that sets `color`; `--row-dim` is defined as `#c98500`.
    - Command: `npm --prefix frontend test -- src/static.test.ts`
    - Expected red (first failing assertion): `AssertionError: expected undefined to be 'var(--amber-glow)'` from the `.timeline-event.selected` check, because `styles.css` currently holds only the one comment line. To be confirmed from paste: the exact wording is not stated until the owner pastes a real red run. Any other failure (a different error, a passing run, or a hang) is a stop: report it to the owner and do not implement.
    - Owner pastes the summary; the agent does not implement before that.
    - _Requirements: 5.12, 6.18, 9.1, 11.1, 11.2_

  - [x] 1.3 Write `src/styles.css`
    - `:root` custom properties from docs/UI_BRIEF.md section 2 (including `--row-dim: #c98500`, `--amber-glow`, `--red-glow`, `--bg-inset`), the system monospace font stack of section 3, layout, components (place cards, border gate, badge, meters table, permit card, timeline, playback bar, note, status line, tabs), tint rows, `.dot` with `--dot-color`, tone classes that set only `--dot-color`, meter fills, `:focus-visible { outline: 2px solid var(--amber); outline-offset: 2px; }`, pressed and selected control states with a 1px `--border` outline and no tint, the `prefers-reduced-motion: reduce` block verbatim from UI_BRIEF section 6, decorative animations and cursor blink only inside `prefers-reduced-motion: no-preference`, and stacking below 768px.
    - No `@import`, no remote font, no image, no `rgba(`.
    - Green check: owner runs `npm --prefix frontend test -- src/static.test.ts`. Expected: all tests in the file pass and the smoke test stays green (run `npm --prefix frontend test` once to confirm).
    - _Requirements: 5.10, 5.12, 6.15, 6.18, 9.1, 9.7, 10.2, 10.3, 11.1, 11.2, 11.3, 11.6_

  - [x] 1.4 Commit task 1
    - Owner's pasted run is green. Run `git status --short`, stage by name `frontend/src/test-types/node-fs.d.ts`, `frontend/src/test/seeded.ts`, `frontend/src/test/replays.ts`, `frontend/vite.config.ts`, `frontend/src/static.test.ts`, `frontend/src/styles.css`, then commit `test(ui): scaffolding and styles with background guards (task 1)`.

- [x] 2. Contrast module (colour rules continued)
  - [x] 2.1 Write `src/contrast.test.ts`
    - Known values: black on white 21, identical colours 1.
    - Measured pairs from design section 16: `--row-dim` #c98500 and the amber, green, blue, orange, purple, red text colours at least 4.5 on `--bg` #0a0a0a and `--bg-surface` #111111; `--amber-dim` #a06800 below 4.5 on both.
    - `compositeOver`: `--red-glow` over `--bg` gives rgb(75,16,16) and over `--bg-surface` rgb(80,22,22); `--amber-glow` over `--bg` gives rgb(59,43,8) and over `--bg-surface` rgb(65,49,14).
    - `--amber` at least 4.5 on all four tints; marker and border colours (red, blue, purple, orange, green) at least 3 on both amber-glow tints; red on both red tints below 4.5 and at least 3.
    - `styles.css` checks: `.timeline-event.selected` and `.timeline-event.killed` set `color: var(--amber)` and never `var(--red)`; no coloured-text variable (`--red`, `--blue`, `--purple`, `--orange`, `--row-dim`, `--green`) is set as `color` in a tinted row rule; `--row-dim` defined as `#c98500`; no `opacity` on timeline row text.
    - Command: `npm --prefix frontend test -- src/contrast.test.ts`
    - Expected red: the file fails to load because `./contrast` does not exist; the first failing line is a vitest import-resolution error naming `./contrast` and src/contrast.test.ts. To be confirmed from paste: the exact wording is not stated until the owner pastes a real red run. Any other failure (a different error, a passing run, or a hang) is a stop: report it to the owner and do not implement.
    - _Requirements: 5.10, 5.12, 9.1, 11.1_

  - [x] 2.2 Implement `src/contrast.ts`
    - Export `relativeLuminance`, `contrastRatio` (WCAG 2.x, 0.03928 / 12.92 / 1.055 / 2.4) and `compositeOver` (per-channel linear mix, rounded to integers, `#rrggbbaa` over `#rrggbb`). No new constants beyond the colour literals the tests pass in.
    - Green check: owner runs `npm --prefix frontend test -- src/contrast.test.ts`. Expected: all tests in the file pass and smoke stays green. If a `styles.css` colour check fails, fix `styles.css` (not the test) and re-run.
    - _Requirements: 5.10, 5.12, 9.1_

  - [x] 2.3 Commit task 2
    - After the owner's green paste: `git status --short`, stage `frontend/src/contrast.ts`, `frontend/src/contrast.test.ts` (and `frontend/src/styles.css` if changed), commit `feat(ui): WCAG contrast helpers (task 2)`.

- [x] 3. Types, constants and reducer (T5.1)
  - [x] 3.1 Write `src/reduce.test.ts` unit tests (T5.1)
    - Edge cases: empty list throws; list without `RUN_STARTED` throws; `BORDER_CHECK` before the first `RUN_STARTED` is ignored; events without `RUN_ENDED` give status `ALIVE`; permit comes from the last `RUN_STARTED` or `BORDER_CHECK`; returned permit shares no data with the events; reduce of the full enforced replay equals the final snapshot (place, step 17, spent 38, allowance 40, status `KILLED`).
    - Command: `npm --prefix frontend test -- src/reduce.test.ts`
    - Expected red: the file fails to load because `./reduce` does not exist; the first failing line is a vitest import-resolution error naming `./reduce` and src/reduce.test.ts. To be confirmed from paste: the exact wording is not stated until the owner pastes a real red run. Any other failure (a different error, a passing run, or a hang) is a stop: report it to the owner and do not implement.
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

  - [x] 3.2 Write property test for reducer prefix consistency
    - **Property 1: Reducer matches the last event of every prefix (P5.1)**
    - For every replay in the index and every prefix containing `RUN_STARTED`, `reduceEvents(prefix)` equals the last event's place, step, spent; the permit of the last `RUN_STARTED` / `BORDER_CHECK`; the status of the last `RUN_ENDED` or `ALIVE`. Expected values come from an independent backward scan in the test. Mutating the result leaves the events unchanged. Docstring: `Property P5.1: ... Validates: ...`.
    - Same file and same command as 3.1: `npm --prefix frontend test -- src/reduce.test.ts`
    - Expected red: same as 3.1 (the file fails to load because `./reduce` does not exist; vitest import-resolution error naming `./reduce` and src/reduce.test.ts). To be confirmed from paste: the exact wording is not stated until the owner pastes a real red run. Any other failure (a different error, a passing run, or a hang) is a stop: report it to the owner and do not implement.
    - **Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5, 10.9**
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 10.9; Property 1 (P5.1)_

  - [x] 3.3 Implement `constants.ts`, `types.ts`, `reduce.ts` (T5.1)
    - `constants.ts`: every constant of design section 2, defined once. `types.ts`: design section 1, no `any`. `reduce.ts`: `reduceEvents` mirroring the Python `reduce_events` (copies, errors on empty or no `RUN_STARTED`).
    - Green check: owner runs `npm --prefix frontend test -- src/reduce.test.ts`. Expected: all tests in the file pass, smoke green. Then owner runs `npm --prefix frontend run build`. Expected: green.
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 10.5_

  - [x] 3.4 Commit task 3
    - After green pastes: `git status --short`, stage `frontend/src/constants.ts`, `frontend/src/types.ts`, `frontend/src/reduce.ts`, `frontend/src/reduce.test.ts`, commit `feat(ui): types, constants and reduceEvents (T5.1, task 3)`.

- [x] 4. Validation, loader and replay-file properties (T5.1)
  - [x] 4.1 Write `src/validate.test.ts` (T5.1)
    - Cases: valid real index and replays parse; `schema_version` other than 1 gives kind `schema_version`; missing `meta.home_permit.allowance` gives `missing_field` with that path; wrong type gives `invalid_field`; bad `driver`; unknown event type; unsafe `file` names (slash, `..`, scheme) rejected; first event not `RUN_STARTED` rejected; empty `events` array accepted.
    - Command: `npm --prefix frontend test -- src/validate.test.ts`
    - Expected red: the file fails to load because `./validate` does not exist; the first failing line is a vitest import-resolution error naming `./validate` and src/validate.test.ts. To be confirmed from paste: the exact wording is not stated until the owner pastes a real red run. Any other failure (a different error, a passing run, or a hang) is a stop: report it to the owner and do not implement.
    - _Requirements: 1.6, 1.7, 6.14, 10.1_

  - [x] 4.2 Write `src/loader.test.ts` (T5.1)
    - Injected stub fetch. Cases: URLs requested are `./replays/index.json` and `./replays/<file>` for every index entry; network rejection; HTTP 404 (message names file and status); invalid JSON; `schema_version` 2; missing field; unsafe file name never fetched; one failing replay leaves the other results `ok`; empty events array loads.
    - Command: `npm --prefix frontend test -- src/loader.test.ts`
    - Expected red: the file fails to load because `./loader` does not exist; the first failing line is a vitest import-resolution error naming `./loader` and src/loader.test.ts. To be confirmed from paste: the exact wording is not stated until the owner pastes a real red run. Any other failure (a different error, a passing run, or a hang) is a stop: report it to the owner and do not implement.
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.9, 10.1_

  - [x] 4.3 Write property test for replay files
    - **Property 4: Every replay file parses and tells the recorded story (P5.4)**
    - File `src/replays.test.ts`. For every entry of the real index: `parseReplay` succeeds; `parseIndex` succeeds; enforced replay's last non-terminal event is `KILLED` with `ALLOWANCE_EXCEEDED`, limit 40, observed 41; unenforced replay has no `KILLED`; the forged-identity replay still parses; deleting any one required key from a deep copy gives `missing_field` naming that key's path.
    - Command: `npm --prefix frontend test -- src/replays.test.ts`
    - Expected red: the file fails to load because `./validate` does not exist; the first failing line is a vitest import-resolution error naming `./validate` and src/replays.test.ts. To be confirmed from paste: the exact wording is not stated until the owner pastes a real red run. Any other failure (a different error, a passing run, or a hang) is a stop: report it to the owner and do not implement.
    - **Validates: Requirements 1.7, 10.10**
    - _Requirements: 1.7, 10.10; Property 4 (P5.4)_

  - [x] 4.4 Implement `validate.ts` and `loader.ts` (T5.1)
    - `validate.ts`: `parseIndex`, `parseReplay` with the check order of design section 5. `loader.ts`: `loadIndex`, `loadReplay` with an injected `FetchLike`, error kinds `network`, `http`, `invalid_json`, then validation.
    - Green check: owner runs each of `npm --prefix frontend test -- src/validate.test.ts`, `npm --prefix frontend test -- src/loader.test.ts`, `npm --prefix frontend test -- src/replays.test.ts`. Expected: all tests in each file pass. Then `npm --prefix frontend run build`. Expected: green.
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.9, 10.1, 10.10_

  - [x] 4.5 Commit task 4
    - After green pastes: `git status --short`, stage `frontend/src/validate.ts`, `frontend/src/loader.ts`, `frontend/src/validate.test.ts`, `frontend/src/loader.test.ts`, `frontend/src/replays.test.ts`, commit `feat(ui): replay validation and loader (T5.1, task 4)`.

- [x] 5. Playback reducer and hook (T5.2)
  - [x] 5.1 Write `src/playback.test.ts` unit tests (T5.2)
    - One example per action: fresh state paused at 0 speed 1; play, pause; step forward past end and step back below 0 do nothing; setSpeed mid-play keeps `pos` and `playing`; scrub clamps (below 0, above max) and ignores non-finite; tick when paused is a no-op; play at the last event restarts at 0; empty replay (`max = 0`) keeps `pos` 0 and play is a no-op; reaching the last event stops playback.
    - Command: `npm --prefix frontend test -- src/playback.test.ts`
    - Expected red: the file fails to load because `./playback` does not exist; the first failing line is a vitest import-resolution error naming `./playback` and src/playback.test.ts. To be confirmed from paste: the exact wording is not stated until the owner pastes a real red run. Any other failure (a different error, a passing run, or a hang) is a stop: report it to the owner and do not implement.
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 6.8, 6.10, 6.11, 6.12, 6.13, 6.14_

  - [x] 5.2 Write property test for playback range
    - **Property 2: Playback position never leaves its range (P5.2)**
    - Same file `src/playback.test.ts`. Seeds 1 to 200 from the Seeded_Generator; random `n >= 0` and random action sequences including scrub values negative, above `max` and non-finite. After every action: `0 <= pos <= max`, speed in 1, 2, 4, `playing` implies `pos < max`; empty replay stays at 0.
    - Command: `npm --prefix frontend test -- src/playback.test.ts`
    - Expected red: same as 5.1 (the file fails to load because `./playback` does not exist; vitest import-resolution error naming `./playback` and src/playback.test.ts). To be confirmed from paste: the exact wording is not stated until the owner pastes a real red run. Any other failure (a different error, a passing run, or a hang) is a stop: report it to the owner and do not implement.
    - **Validates: Requirements 6.9, 6.10, 6.11, 6.13, 6.14, 10.11**
    - _Requirements: 6.9, 6.10, 6.11, 6.13, 6.14, 10.11; Property 2 (P5.2)_

  - [x] 5.3 Implement `playback.ts` and `useReplay.ts` (T5.2)
    - `playback.ts`: `createPlayback`, `playbackReducer` per the table in design section 4. `useReplay.ts`: `useReducer` plus one `setInterval` effect keyed on `[playing, speed]` with cleanup; no timer at mount (no autoplay). `useReplay.ts` is checked by build only.
    - Green check: owner runs `npm --prefix frontend test -- src/playback.test.ts`. Expected: all tests in the file pass, smoke green. Then `npm --prefix frontend run build`. Expected: green.
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 6.8, 6.9, 6.12, 6.14, 10.7_

  - [x] 5.4 Commit task 5
    - After green pastes: `git status --short`, stage `frontend/src/playback.ts`, `frontend/src/useReplay.ts`, `frontend/src/playback.test.ts`, commit `feat(ui): playback reducer and useReplay (T5.2, task 5)`.

- [x] 6. Place cards, token placement and border badge (T5.3)
  - [x] 6.1 Write `src/placeMap.test.ts` (T5.3)
    - `tokenPlace` for every index of the three real replays; forged spawn refusal gives `null` at indices 1 and 2 (and `library` at index 0); enforced token in `library` before and `vault` after the `go:vault` check; refusal with non-null `via_action` keeps the place.
    - Command: `npm --prefix frontend test -- src/placeMap.test.ts`
    - Expected red: the file fails to load because `./placeMap` does not exist; the first failing line is a vitest import-resolution error naming `./placeMap` and src/placeMap.test.ts. To be confirmed from paste: the exact wording is not stated until the owner pastes a real red run. Any other failure (a different error, a passing run, or a hang) is a stop: report it to the owner and do not implement.
    - _Requirements: 2.2, 2.3, 2.8_

  - [x] 6.2 Write `src/badge.test.ts` (T5.3)
    - Every row of the design section 8 table: no check gives `NO BORDER CHECK YET`; `ADMIT`/`OK` gives `ADMITTED`; `ADMIT`/`UNENFORCED` gives `ADMITTED` with reason `UNENFORCED` (unenforced real replay); `ADMIT_IMPOSED` gives `ADMITTED UNDER IMPOSED PERMIT`; `REFUSE` gives `REFUSED` with reason `BAD_SIGNATURE` (forged real replay); badge persists after later events.
    - Command: `npm --prefix frontend test -- src/badge.test.ts`
    - Expected red: the file fails to load because `./badge` does not exist; the first failing line is a vitest import-resolution error naming `./badge` and src/badge.test.ts. To be confirmed from paste: the exact wording is not stated until the owner pastes a real red run. Any other failure (a different error, a passing run, or a hang) is a stop: report it to the owner and do not implement.
    - _Requirements: 2.4, 2.5, 2.6, 2.7, 2.9, 2.10, 2.11_

  - [x] 6.3 Implement `placeMap.ts`, `badge.ts`, `components/PlaceCard.tsx` (T5.3)
    - `tokenPlace`, `borderBadge` per design sections 7 and 8; `PlaceCard` renders place name, token with visible text "agent here", and the dashed border gate element between cards is rendered by `RunPanel` later.
    - Green check: owner runs `npm --prefix frontend test -- src/placeMap.test.ts` and `npm --prefix frontend test -- src/badge.test.ts`. Expected: all tests in both files pass, smoke green. Then `npm --prefix frontend run build`. Expected: green.
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8, 2.9, 2.10, 2.11_

  - [x] 6.4 Commit task 6
    - After green pastes: `git status --short`, stage `frontend/src/placeMap.ts`, `frontend/src/badge.ts`, `frontend/src/components/PlaceCard.tsx`, `frontend/src/placeMap.test.ts`, `frontend/src/badge.test.ts`, commit `feat(ui): place cards, token placement and border badge (T5.3, task 6)`.

- [x] 7. Meters (T5.4)
  - [x] 7.1 Write `src/meters.test.ts` unit tests (T5.4)
    - `barPercent`: zero limit with observed 0 gives 0, with observed above 0 gives 100; equal to the limit gives 100 and is not over; one over is over; clamp at 100; negative observed gives 0. `meterRows` uses home-permit limits. Worked table of design section 6 for both real replays: enforced never OVER LIMIT (index 18: 38 / 60, 17 / 30, 17 / 60); unenforced index 10 equal (60 / 60, not over), OVER LIMIT from index 11, index 30 steps 30 / 30 not over.
    - Command: `npm --prefix frontend test -- src/meters.test.ts`
    - Expected red: the file fails to load because `./meters` does not exist; the first failing line is a vitest import-resolution error naming `./meters` and src/meters.test.ts. To be confirmed from paste: the exact wording is not stated until the owner pastes a real red run. Any other failure (a different error, a passing run, or a hang) is a stop: report it to the owner and do not implement.
    - _Requirements: 3.6, 3.7, 3.8, 3.9, 3.10, 3.14_

  - [x] 7.2 Write property test for meter percentage and over-limit flag
    - **Property 3: Meter percentage is clamped and the over-limit flag is exact (P5.3)**
    - Same file. Seeds 1 to 200: random observed and limit pairs including limit 0 and observed equal to limit; `barPercent` in [0, 100], formula for limit above 0, 0 or 100 for limit 0; `isOver` true iff observed above limit. For every event of every real replay, `meterRows` limits equal the home permit and are identical across events.
    - Command: `npm --prefix frontend test -- src/meters.test.ts`
    - Expected red: same as 7.1 (the file fails to load because `./meters` does not exist; vitest import-resolution error naming `./meters` and src/meters.test.ts). To be confirmed from paste: the exact wording is not stated until the owner pastes a real red run. Any other failure (a different error, a passing run, or a hang) is a stop: report it to the owner and do not implement.
    - **Validates: Requirements 3.8, 3.9, 3.10, 3.14, 10.12**
    - _Requirements: 3.8, 3.9, 3.10, 3.14, 10.12; Property 3 (P5.3)_

  - [x] 7.3 Implement `meters.ts` and `components/Meters.tsx` (T5.4)
    - `barPercent`, `isOver`, `meterRows`. `Meters`: semantic `<table>` with caption, row header label, aria-hidden bar (`.meter-fill.ok` / `.meter-fill.over`), `observed / limit` text and the text `OVER LIMIT` when over. Limits stay the home permit for the whole replay.
    - Green check: owner runs `npm --prefix frontend test -- src/meters.test.ts`. Expected: all tests in the file pass, smoke green. Then `npm --prefix frontend run build`. Expected: green.
    - _Requirements: 3.6, 3.7, 3.8, 3.9, 3.10, 3.11, 3.12, 3.13, 3.14_

  - [x] 7.4 Commit task 7
    - After green pastes: `git status --short`, stage `frontend/src/meters.ts`, `frontend/src/components/Meters.tsx`, `frontend/src/meters.test.ts`, commit `feat(ui): meters with clamped bars and over-limit flag (T5.4, task 7)`.

- [x] 8. Permit card (T5.5)
  - [x] 8.1 Write `src/permitView.test.ts` (T5.5)
    - Known `narrowed_fields`: enforced index 3 and 19 give allowance 40 marked narrowed, `allowed_actions` narrowed, four home actions removed (`removed: true`); enforced index 2 (before the vault border) has no narrowed field and no removed action; `ADMIT` check gives no highlights; unenforced replay never narrowed; all four fields narrowed when the list names all four; state action not in home is appended and not removed.
    - Command: `npm --prefix frontend test -- src/permitView.test.ts`
    - Expected red: the file fails to load because `./permitView` does not exist; the first failing line is a vitest import-resolution error naming `./permitView` and src/permitView.test.ts. To be confirmed from paste: the exact wording is not stated until the owner pastes a real red run. Any other failure (a different error, a passing run, or a hang) is a stop: report it to the owner and do not implement.
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7_

  - [x] 8.2 Implement `permitView.ts` and `components/PermitCard.tsx` (T5.5)
    - `permitView`, `latestNarrowed`. `PermitCard`: `<dl>` of the four fields; narrowed field has the "▼" prefix, the visible word "narrowed" and the orange highlight; removed actions in `<s class="removed">` with visually hidden text "(removed)".
    - Green check: owner runs `npm --prefix frontend test -- src/permitView.test.ts`. Expected: all tests in the file pass, smoke green. Then `npm --prefix frontend run build`. Expected: green.
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7_

  - [x] 8.3 Commit task 8
    - After green pastes: `git status --short`, stage `frontend/src/permitView.ts`, `frontend/src/components/PermitCard.tsx`, `frontend/src/permitView.test.ts`, commit `feat(ui): permit card with narrowed-field highlights (T5.5, task 8)`.

- [x] 9. Timeline, event detail and presentation helpers (T5.6)
  - [x] 9.1 Write `src/present.test.ts` (T5.6, also covers T5.8 label and note text)
    - `eventTone`: red for KILLED and for RUN_ENDED KILLED; per UI_BRIEF mapping for the others. `rowTextTone(event, selected)`: for every event of the three real replays and synthetic events of all seven types, `rowTextTone(event, true) === 'amber'`; `rowTextTone(event, false)` is `'amber'` for KILLED and RUN_ENDED KILLED, `'dim'` for RUN_ENDED HARNESS_CAP, `eventTone(event)` otherwise. Seeded loop (seeds 1 to 200) over random (event, selected) pairs: whenever the row has a tint, the tone is `'amber'`.
    - `eventLabel`, `eventSummary` (KILLED summary contains `KILLED ALLOWANCE_EXCEEDED limit 40 observed 41`), `isKilledRow`, `runEndedStyle`, `statusView` at the KILLED event and at RUN_ENDED (text `KILLED ALLOWANCE_EXCEEDED. The engine destroyed the agent.`), `cursorBlinks` (only when every status is `ALIVE`), `positionLabel` (`event 19 of 20`, `turn 17 of 30`), `liveMessage`, the leading "▸" selected-marker text, `driverLabel`, and `HONESTY_NOTE`. Explicit assertions: `driverLabel('scripted') === 'scripted agent'`; `driverLabel('llm') === 'live LLM'`; `HONESTY_NOTE` equals exactly "Permits do not stop an injection that stays inside the permit boundary. Recorded runs are labelled scripted or live LLM."
    - Command: `npm --prefix frontend test -- src/present.test.ts`
    - Expected red: the file fails to load because `./present` does not exist; the first failing line is a vitest import-resolution error naming `./present` and src/present.test.ts. To be confirmed from paste: the exact wording is not stated until the owner pastes a real red run. Any other failure (a different error, a passing run, or a hang) is a stop: report it to the owner and do not implement.
    - _Requirements: 5.1, 5.2, 5.4, 5.12, 6.16, 6.17, 8.2, 8.3, 8.5, 9.1, 9.2, 9.3, 9.4, 9.5, 9.6, 9.8_

  - [x] 9.2 Implement `present.ts`, `components/Timeline.tsx`, `components/EventDetail.tsx` (T5.6)
    - `present.ts` per design section 10. `Timeline`: `<ol>` of `<button>` rows with roving tabindex, ArrowUp/ArrowDown/Home/End, `aria-current="true"` and "▸" on the selected row, `future` class for later rows (dimmed, still focusable), `killed` / `run-ended-killed` / `run-ended-cap` classes, text colour from `rowTextTone`, marker and border colour from `eventTone`, `scrollIntoView` with `behavior` `'auto'` under reduced motion. `EventDetail`: italic explain line above the JSON, reason / limit / observed line for KILLED, `<pre>` JSON.
    - Green check: owner runs `npm --prefix frontend test -- src/present.test.ts`. Expected: all tests in the file pass, smoke green. Then `npm --prefix frontend run build`. Expected: green.
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7, 5.8, 5.9, 5.10, 5.11, 5.12, 9.1, 9.2, 9.3, 9.4, 9.5, 9.6, 9.7, 9.8_

  - [x] 9.3 Commit task 9
    - After green pastes: `git status --short`, stage `frontend/src/present.ts`, `frontend/src/components/Timeline.tsx`, `frontend/src/components/EventDetail.tsx`, `frontend/src/present.test.ts`, commit `feat(ui): timeline, event detail and presentation helpers (T5.6, task 9)`.

- [x] 10. Picker, pairing and compare view (T5.7)
  - [x] 10.1 Write `src/turns.test.ts` unit tests (T5.7)
    - Real-file numbers: enforced last turn 17 (indices 18 and 19 both turn 17), unenforced last turn 30, forged last turn 0, `sharedMax` 30; enforced selects index `turn + 1` for turns 0 to 16 and 19 for turns 17 to 30; unenforced selects `turn` for 0 to 29 and 31 at 30; empty list gives `selectIndex` 0 and `lastTurn` 0; `go:vault` check is turn-starting in the unenforced replay.
    - Command: `npm --prefix frontend test -- src/turns.test.ts`
    - Expected red: the file fails to load because `./turns` does not exist; the first failing line is a vitest import-resolution error naming `./turns` and src/turns.test.ts. To be confirmed from paste: the exact wording is not stated until the owner pastes a real red run. Any other failure (a different error, a passing run, or a hang) is a stop: report it to the owner and do not implement.
    - _Requirements: 7.1, 7.5, 7.6, 7.7, 7.8_

  - [x] 10.2 Write `src/pair.test.ts` (T5.7)
    - Cases from design section 12 and the test table: same stem and scenario resolves; scenario mismatch unavailable; duplicate on one side unavailable; missing counterpart unavailable; `forged-identity-refused` never paired, also next to a complete pair; `meta.enforce` disagreeing with the suffix is no counterpart; a pair member that failed to load is unavailable; the real index resolves to `poisoned-briefing-enforced` and `poisoned-briefing-unenforced`; `types.ts` has no `pair` field.
    - Command: `npm --prefix frontend test -- src/pair.test.ts`
    - Expected red: the file fails to load because `./pair` does not exist; the first failing line is a vitest import-resolution error naming `./pair` and src/pair.test.ts. To be confirmed from paste: the exact wording is not stated until the owner pastes a real red run. Any other failure (a different error, a passing run, or a hang) is a stop: report it to the owner and do not implement.
    - _Requirements: 7.2, 7.11, 7.12, 1.9_

  - [x] 10.3 Write property test for compare mapping
    - **Property 5: Compare mapping selects a valid event on both sides for any turn (P5.5)**
    - Same file as 10.1, `src/turns.test.ts`. Seeds 1 to 200: random integer turns at or above 0 (below, at and far above the last turn). `turnsOf` has the same length as events, starts at 0, is non-decreasing, does not increase at `RUN_STARTED`, spawn `BORDER_CHECK` or `RUN_ENDED`, and increases by exactly 1 elsewhere. `selectIndex` is in `[0, events.length - 1]` for both real replays, equals a linear-scan oracle, is non-decreasing in the turn, and is the last index when the turn is at least the last turn. For the pair resolved by `pair.ts` from the real index the enforced side selects 19 for every turn from 17 to 30 and the unenforced side selects 31 at 30.
    - Command: `npm --prefix frontend test -- src/turns.test.ts`
    - Expected red: same as 10.1 (the file fails to load because `./turns` does not exist; vitest import-resolution error naming `./turns` and src/turns.test.ts). To be confirmed from paste: the exact wording is not stated until the owner pastes a real red run. Any other failure (a different error, a passing run, or a hang) is a stop: report it to the owner and do not implement.
    - **Validates: Requirements 7.1, 7.5, 7.6, 7.7, 7.8, 10.13**
    - _Requirements: 7.1, 7.5, 7.6, 7.7, 7.8, 10.13; Property 5 (P5.5)_

  - [x] 10.4 Implement `turns.ts` and `pair.ts` (T5.7)
    - `turnsOf`, `lastTurn`, `selectIndex`, `sharedMax` per design section 11; `idStem`, `resolveComparePair`, `PAIR_UNAVAILABLE_MESSAGE` per design section 12. No pair field added to any type.
    - Green check: owner runs `npm --prefix frontend test -- src/turns.test.ts` and `npm --prefix frontend test -- src/pair.test.ts`. Expected: all tests in both files pass, smoke green.
    - _Requirements: 7.1, 7.2, 7.5, 7.6, 7.7, 7.8, 7.11, 7.12_

  - [x] 10.5 Implement `components/ReplayPicker.tsx`, `components/CompareView.tsx`, `useMediaQuery.ts` and the run-view parts CompareView imports (T5.7)
    - `ReplayPicker`: labelled `<select>`, option text `title — scripted agent` / `title — live LLM`, no page reload. `CompareView`: left column "WITHOUT ENFORCEMENT", right column "WITH ENFORCEMENT", one shared turn via `useReplay(sharedMax)`, row click scrubs to the row's turn, tab switcher with roving tabindex below 768px, driver label in each column header.
    - Owner confirmed: RunPanel, StatusLine and PlaybackBar are built here (moved from T5.8) because CompareView imports them.
    - Because `CompareView` imports them, also create here `components/RunPanel.tsx`, `components/StatusLine.tsx` and `components/PlaybackBar.tsx` (planned for T5.8 in the seed; moved earlier by the dependency). They contain no decisions: they call the pure functions of tasks 3 to 10.4.
    - Check: owner runs `npm --prefix frontend run build`. Expected: green.
    - _Requirements: 6.15, 6.16, 6.17, 6.18, 7.2, 7.3, 7.4, 7.9, 7.10, 8.1, 8.4, 8.7_

  - [x] 10.6 Commit task 10
    - After green pastes: `git status --short`, stage `frontend/src/turns.ts`, `frontend/src/pair.ts`, `frontend/src/useMediaQuery.ts`, `frontend/src/components/ReplayPicker.tsx`, `frontend/src/components/CompareView.tsx`, `frontend/src/components/RunPanel.tsx`, `frontend/src/components/StatusLine.tsx`, `frontend/src/components/PlaybackBar.tsx`, `frontend/src/turns.test.ts`, `frontend/src/pair.test.ts`, commit `feat(ui): picker, pair resolution and compare view (T5.7, task 10)`.

- [x] 11. Honesty note, error state and App wiring (T5.8)
  - [x] 11.1 Implement `components/Note.tsx`, `components/ErrorState.tsx` and wire `App.tsx` (T5.8)
    - `Note`: fixed footer with `HONESTY_NOTE` in italic, no dismiss control. `ErrorState`: `role="alert"` with file name and cause. `App.tsx`: loads the index and every replay once (cancelled flag), keeps one `Result` per file, loading text `Loading replays…`, full-page error for the index, per-file error only when that replay is selected, compare toggle with `aria-pressed`, `key` on `RunPanel` / `CompareView` so playback restarts paused at 0, `PAIR_UNAVAILABLE_MESSAGE` when unavailable, one visually hidden `aria-live="polite"` region, subtitle from `SUBTITLE`, title cursor class from `cursorBlinks`. The driver labels and `HONESTY_NOTE` text are already tested in `present.test.ts` (task 9.1); no separate new test file is needed.
    - Owner confirmed: task 11 is a build check only; driver labels (`scripted agent`, `live LLM`) and the exact `HONESTY_NOTE` text are asserted by `present.test.ts` in 9.1.
    - Check: owner runs `npm --prefix frontend run build`. Expected: green. Then owner runs `npm --prefix frontend test`. Expected: all tests pass (counts reported at the final checkpoint).
    - _Requirements: 1.1, 1.2, 1.3, 1.8, 1.9, 6.1, 6.17, 7.11, 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 8.7, 9.8, 10.7_

  - [x] 11.2 Commit task 11
    - After green pastes: `git status --short`, stage `frontend/src/components/Note.tsx`, `frontend/src/components/ErrorState.tsx`, `frontend/src/App.tsx`, commit `feat(ui): honesty note, error state and app wiring (T5.8, task 11)`.

- [x] 12. Remaining static guards
  - [x] 12.1 Green check: extend `src/static.test.ts` with the source-scan guards (no red step)
    - Scan `src/` and `index.html`: no `http://` or `https://` and no `@import url`; `fetch(` appears only in `App.tsx` and `loader.ts`; no `: any` or `as any`; no non-null assertion; no `dangerouslySetInnerHTML`; no `alert(` or `dialog`; no app module outside `test/` and `test-types/` references `test-types`, `node-fs.d.ts` or the `node:` prefix; `vite.config.ts` has `base: './'`; `package.json` dependencies unchanged from the baseline list.
    - Command: `npm --prefix frontend test -- src/static.test.ts`
    - No red step. This is a green-check task: the code from tasks 1 to 11 is expected to already comply, so the owner's first run is expected green. If any guard fails, that is a real violation: stop, report it, and fix app code (never weaken the guard) after the owner agrees.
    - Green check: same command; all tests in the file pass and smoke stays green.
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 10.6, 10.7, 11.7, 11.9_

  - [x] 12.2 Commit task 12
    - After the owner's green paste: `git status --short`, stage `frontend/src/static.test.ts`, commit `test(ui): static source guards (task 12)`.

- [x] 13. Final checkpoint
  - The owner runs `npm --prefix frontend test` and `npm --prefix frontend run build` and pastes both summaries. Expected: build green; all test files pass.
  - Report counts as `baseline 1 + N new = total` from the owner's paste (no counts are claimed before then).
  - Owner action (not an agent action): run `npm run dev` once in `frontend/` and check the seed exit criteria: both poisoned-briefing replays play, the forged replay shows REFUSED with no token, the compare view stays in step, KILLED is obvious, keyboard-only operation works, reduced motion removes blink and animation.
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tests are required; no task carries a `*`.
- Each ROADMAP item T5.1 to T5.8 is covered in ROADMAP order by tasks 3 to 11 (T5.1: tasks 3 and 4; T5.2: task 5; T5.3: task 6; T5.4: task 7; T5.5: task 8; T5.6: task 9; T5.7: task 10; T5.8: task 11).
- Properties: P5.1 task 3.2, P5.2 task 5.2, P5.3 task 7.2, P5.4 task 4.3, P5.5 task 10.3.
- The red and green outcomes are never claimed by the agent; they come from the owner's pasted runs.

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["1.2"] },
    { "id": 2, "tasks": ["1.3"] },
    { "id": 3, "tasks": ["1.4"] },
    { "id": 4, "tasks": ["2.1"] },
    { "id": 5, "tasks": ["2.2"] },
    { "id": 6, "tasks": ["2.3"] },
    { "id": 7, "tasks": ["3.1"] },
    { "id": 8, "tasks": ["3.2"] },
    { "id": 9, "tasks": ["3.3"] },
    { "id": 10, "tasks": ["3.4"] },
    { "id": 11, "tasks": ["4.1"] },
    { "id": 12, "tasks": ["4.2"] },
    { "id": 13, "tasks": ["4.3"] },
    { "id": 14, "tasks": ["4.4"] },
    { "id": 15, "tasks": ["4.5"] },
    { "id": 16, "tasks": ["5.1"] },
    { "id": 17, "tasks": ["5.2"] },
    { "id": 18, "tasks": ["5.3"] },
    { "id": 19, "tasks": ["5.4"] },
    { "id": 20, "tasks": ["6.1"] },
    { "id": 21, "tasks": ["6.2"] },
    { "id": 22, "tasks": ["6.3"] },
    { "id": 23, "tasks": ["6.4"] },
    { "id": 24, "tasks": ["7.1"] },
    { "id": 25, "tasks": ["7.2"] },
    { "id": 26, "tasks": ["7.3"] },
    { "id": 27, "tasks": ["7.4"] },
    { "id": 28, "tasks": ["8.1"] },
    { "id": 29, "tasks": ["8.2"] },
    { "id": 30, "tasks": ["8.3"] },
    { "id": 31, "tasks": ["9.1"] },
    { "id": 32, "tasks": ["9.2"] },
    { "id": 33, "tasks": ["9.3"] },
    { "id": 34, "tasks": ["10.1"] },
    { "id": 35, "tasks": ["10.2"] },
    { "id": 36, "tasks": ["10.3"] },
    { "id": 37, "tasks": ["10.4"] },
    { "id": 38, "tasks": ["10.5"] },
    { "id": 39, "tasks": ["10.6"] },
    { "id": 40, "tasks": ["11.1"] },
    { "id": 41, "tasks": ["11.2"] },
    { "id": 42, "tasks": ["12.1"] },
    { "id": 43, "tasks": ["12.2"] }
  ]
}
```
