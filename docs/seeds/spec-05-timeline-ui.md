# Seed: spec 5, timeline UI ("Mission Control")

Contract details: `docs/CONTRACTS.md` sections 6 and 9. Depends on spec 4 (replay files exist). Branch: `spec/05-timeline-ui`.

## Goal
A single-page React + TypeScript app that plays recorded replays and tells the story: the same attack unenforced versus enforced, ending in a red KILLED event with the reason. Static, no backend, no keys, no external requests.

## Files
`frontend/src/` with: `types.ts` (replay and event types matching CONTRACTS), `reduce.ts` (`reduceEvents` identical in behaviour to the Python one), `useReplay.ts` (index, play, pause, step, speed, scrub), components `PlaceCard`, `Meters`, `Timeline`, `EventDetail`, `ReplayPicker`, `CompareView`, `Note` (what permits do not stop), `App.tsx`, `styles.css`; vitest tests beside the logic.

## Requirements to capture (EARS, number them 5.1, 5.2, ...)
1. WHEN the app loads, THE UI SHALL fetch `./replays/index.json` and the selected replay by relative URL, and SHALL show a readable error state if loading or parsing fails.
2. THE UI SHALL show two place cards (Library, Vault) with a border between them, the agent token in the current place at the selected event, and a badge for the latest border decision (REFUSED, ADMITTED, ADMITTED UNDER IMPOSED PERMIT).
3. THE UI SHALL show meters for allowance (spent against the current permit's allowance), steps and lifetime, computed from events and replay meta; WHEN spent exceeds the allowance THE meter SHALL show an explicit over-limit state (text plus colour, not colour alone).
4. THE UI SHALL show the current permit as a card and highlight which fields an imposed permit narrowed.
5. THE UI SHALL show a colour-coded timeline of all events with text labels; selecting an event SHALL show its JSON and its `explain` text.
6. THE UI SHALL provide play, pause, step forward, step back, speed, and scrubbing, with keyboard-focusable controls.
7. THE UI SHALL provide a compare view that plays the unenforced and the enforced replay side by side, synchronised by turn.
8. THE UI SHALL label every replay as "scripted agent" or "live LLM" using the `driver` field, and show a permanent note that an injection which stays inside the permit is not stopped.
9. THE UI SHALL make a KILLED event unmistakable (red, large, with the reason, limit and observed values).
10. THE UI SHALL make no network requests other than to its own replay files and SHALL use only system fonts.
11. Style: retro terminal (amber on dark, monospace). No third-party logos, no copyrighted imagery.

## Correctness properties (vitest, node environment, reading the real replay files from `public/replays/`)
- P5.1 For every replay and every prefix of events, `reduceEvents` matches the last event's snapshot. (Req 5.2, 5.3)
- P5.2 Playback index never leaves [0, events.length - 1] under any sequence of play/pause/step/scrub actions. (Req 5.6)
- P5.3 Meter percentage is computed correctly, clamped for the bar, and the over-limit flag is true exactly when spent > allowance. (Req 5.3)
- P5.4 Every replay parses against the TypeScript types; the enforced replay's last non-terminal event is KILLED with reason ALLOWANCE_EXCEEDED; the unenforced replay has no KILLED. (Req 5.1, 5.9)
- P5.5 Compare view mapping: for any turn, both sides select a valid event index. (Req 5.7)

## Exit criteria
- `cd frontend && npm run build && npm test` pass. `tsc` strict, no `any` in app code.
- The human runs `npm run dev` once and checks: both replays play, compare view works, KILLED is obvious, keyboard works. Agent then fixes with `FIX`.
- Branch ready for `MERGE`.
