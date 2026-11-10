# Requirements Document

## Introduction

The Timeline UI ("Mission Control") is a static single-page React + TypeScript application that plays recorded TelePermit replays. It tells one story: the same prompt-injection attack run without enforcement and with enforcement, ending in a red KILLED event that states the reason. The UI needs no backend, no API key and no external network request. It consumes the replay files defined in docs/CONTRACTS.md section 9 and the event model in section 6, and it reproduces the Python `reduce_events` behaviour in TypeScript.

The Meters measure against the home limits in `meta.home_permit`. The enforced run is stopped at observed 41 against the imposed 40, which the KILLED row shows, so its allowance meter against 60 is not over limit. The unenforced run reaches 120 against 60 and shows OVER LIMIT.

Requirement headings use the validator's integer numbering (Requirement 1 to 11) and carry the seed ID in brackets: Requirement N is seed requirement 5.N, in seed order. Acceptance criteria are numbered 1..n inside each requirement and are referenced as, for example, 5.3.4.

## Glossary

- **UI**: The static React + TypeScript single-page application in `frontend/`.
- **Replay**: A JSON file `{schema_version, meta, events}` from `frontend/public/replays/`, as defined in CONTRACTS section 9.
- **ReplayPicker**: The UI element in the header that lists the Replay_Index entries and selects the Replay to play.
- **Replay_Index**: The file `./replays/index.json` listing available replays.
- **Replay_Loader**: The UI component that fetches and validates the Replay_Index and Replay files.
- **Event**: One audit record `{seq, t, type, place, step, spent, data}` as defined in CONTRACTS section 6.
- **Reducer**: The TypeScript function `reduceEvents`, equivalent in behaviour to the Python `reduce_events`.
- **State_Snapshot**: The result of the Reducer: `{place, step, spent, permit, status}`.
- **Permit**: The record `{lifetime_s, max_steps, allowance, allowed_actions}`. The state permit is the Permit in the State_Snapshot.
- **Home_Permit**: The Permit in `meta.home_permit`, used as the comparison baseline.
- **Place_Card**: The UI element for one place (Library or Vault).
- **Border_Badge**: The text badge showing the latest border decision.
- **Meters**: The UI element showing allowance, steps and lifetime usage against the limits of meta.home_permit.
- **Permit_Card**: The UI element showing the state permit fields.
- **Timeline**: The ordered, colour-coded list of all Events of the selected Replay.
- **Event_Detail**: The panel showing the JSON and `explain` text of the selected Event.
- **Playback_Controller**: The logic and controls that hold the selected event index and playback state (`useReplay`).
- **Playback_Index**: The zero-based index of the selected Event, within `[0, events.length - 1]`.
- **Turn**: A number derived from Events. Turn 0 holds the setup Events. Every Event except `RUN_STARTED`, the spawn `BORDER_CHECK` (`data.via_action` is null) and `RUN_ENDED` starts a new Turn numbered one higher than the previous Turn. A `RUN_ENDED` Event belongs to the Turn of the Event before it.
- **Compare_Pair**: The '-unenforced' and '-enforced' Replays that share an id stem and scenario.
- **Compare_View**: The view that plays the unenforced and the enforced Replay side by side.
- **Honesty_Note**: The permanent text stating what permits do not stop.
- **Over_Limit**: The condition where an observed value is greater than its limit.
- **Narrowed_Fields**: The `data.narrowed_fields` list of a `BORDER_CHECK` Event.
- **Seeded_Generator**: A small deterministic pseudo-random generator written in the repository and used by property tests.

## Requirements

### Requirement 1: [5.1] Loading and error state

**User Story:** As a viewer, I want the app to load replays by itself and tell me clearly when loading fails, so that I never see a blank or broken page.

#### Acceptance Criteria

1. WHEN the UI loads, THE Replay_Loader SHALL fetch `./replays/index.json` by relative URL.
2. WHEN the Replay_Index is loaded, THE Replay_Loader SHALL fetch the selected Replay and the Replays the compare view needs, each by the relative URL built from the index entry `file` field.
3. IF a fetch fails at the network level, THEN THE UI SHALL display an error state that names the file that failed to load.
4. IF a fetch returns a non-OK HTTP status, THEN THE UI SHALL display an error state that names the file and the status code.
5. IF a fetched body is not valid JSON, THEN THE UI SHALL display an error state that names the file and states that the JSON is invalid.
6. IF a fetched document has a `schema_version` other than 1, THEN THE UI SHALL display an error state that names the file and the unsupported version.
7. IF a fetched document is missing a required field defined in CONTRACTS section 9 or section 6, THEN THE UI SHALL display an error state that names the file and the missing field.
8. WHILE a fetch is in progress, THE UI SHALL display a text loading indicator.
9. THE Replay_Loader SHALL fetch every Replay named in the Replay_Index at start, and a failure of one Replay file SHALL NOT prevent the other Replays from being shown.

### Requirement 2: [5.2] Place cards, agent token and border badge

**User Story:** As a viewer, I want to see where the agent is and what the last border decision was, so that I can follow the story of the run.

#### Acceptance Criteria

1. THE UI SHALL display one Place_Card for Library and one Place_Card for Vault, with a dashed border element between them.
2. THE UI SHALL display the agent token in the Place_Card whose place equals `place` of the Event at the Playback_Index.
3. WHEN the Event at the Playback_Index changes `place` compared with the preceding Event, THE UI SHALL move the agent token to the new Place_Card.
4. THE Border_Badge SHALL show the text "ADMITTED" for the latest `BORDER_CHECK` Event at or before the Playback_Index with decision `ADMIT`.
5. THE Border_Badge SHALL show the text "ADMITTED UNDER IMPOSED PERMIT" for the latest `BORDER_CHECK` Event at or before the Playback_Index with decision `ADMIT_IMPOSED`.
6. THE Border_Badge SHALL show the text "REFUSED" for the latest `BORDER_CHECK` Event at or before the Playback_Index with decision `REFUSE`.
7. WHEN the latest `BORDER_CHECK` Event has decision `ADMIT` and reason `UNENFORCED`, THE Border_Badge SHALL show the text "ADMITTED" and SHALL show the reason text "UNENFORCED".
8. WHEN the Replay contains a `BORDER_CHECK` Event with decision `REFUSE` and `via_action` null (refusal at spawn), THE UI SHALL display the agent token in no Place_Card at and after that Event.
9. WHEN the Replay contains a spawn refusal, THE Border_Badge SHALL show "REFUSED" together with the refusal reason text (for example `BAD_SIGNATURE`).
10. WHILE no `BORDER_CHECK` Event exists at or before the Playback_Index, THE Border_Badge SHALL show the text "NO BORDER CHECK YET".
11. THE Border_Badge SHALL convey the decision in text, not in colour alone.

### Requirement 3: [5.3] Meters and reducer

**User Story:** As a viewer, I want live meters for allowance, steps and lifetime, so that I can see the agent approach and cross a limit.

#### Acceptance Criteria

1. WHEN given a non-empty list of Events that contains a `RUN_STARTED` Event, THE Reducer SHALL return a State_Snapshot whose `place`, `step` and `spent` equal those of the last Event in the list.
2. THE Reducer SHALL take the State_Snapshot `permit` from `data.permit` of the `RUN_STARTED` Event or `data.permit_after` of the `BORDER_CHECK` Event, whichever occurs last, and SHALL ignore any `BORDER_CHECK` Event that occurs before the first `RUN_STARTED` Event.
3. THE Reducer SHALL take the State_Snapshot `status` from `data.status` of the last `RUN_ENDED` Event, and SHALL return status `ALIVE` WHEN no `RUN_ENDED` Event exists.
4. IF the Reducer receives an empty list, THEN THE Reducer SHALL raise an error.
5. IF the Reducer receives a list without a `RUN_STARTED` Event, THEN THE Reducer SHALL raise an error.
6. THE Meters SHALL display three rows: allowance (`spent` against `meta.home_permit.allowance`), steps (`step` against `meta.home_permit.max_steps`) and lifetime (elapsed seconds against `meta.home_permit.lifetime_s`), where the observed values are `spent`, `step` and `t` of the Event at the Playback_Index of the loaded Replay.
7. THE Meters SHALL take the lifetime elapsed value from `t` of the Event at the Playback_Index, with the born time being 0.0.
8. THE Meters SHALL compute each bar percentage as observed divided by limit multiplied by 100, clamped to the range 0 to 100.
9. IF a limit equals 0, THEN THE Meters SHALL compute the bar percentage as 0 when observed equals 0 and as 100 when observed is greater than 0, without dividing by zero.
10. THE Meters SHALL set the Over_Limit flag of a row to true exactly when observed is greater than limit, for allowance, steps and lifetime alike.
11. WHILE the Over_Limit flag of a row is true, THE Meters SHALL show the text "OVER LIMIT" next to the `observed / limit` fraction and SHALL draw the bar in red.
12. WHILE the Over_Limit flag of a row is false, THE Meters SHALL draw the bar in green.
13. THE Meters SHALL be rendered as a semantic table with a text label and a numeric `observed / limit` value in every row.
14. THE Meters SHALL keep the three limits fixed at the `meta.home_permit` values for the whole Replay, including after an imposed permit narrows the state permit.

### Requirement 4: [5.4] Permit card and narrowed fields

**User Story:** As a viewer, I want to see the current permit and what a border narrowed, so that I understand why the agent lost capabilities.

#### Acceptance Criteria

1. THE Permit_Card SHALL display `lifetime_s`, `max_steps`, `allowance` and `allowed_actions` of the state permit at the Playback_Index.
2. THE Permit_Card SHALL highlight each field named in the Narrowed_Fields of the latest `BORDER_CHECK` Event at or before the Playback_Index, using the orange highlight and a "▼" prefix.
3. WHEN the Narrowed_Fields list is empty, THE Permit_Card SHALL highlight no field.
4. THE Permit_Card SHALL display each action that is in `meta.home_permit.allowed_actions` and not in the state permit `allowed_actions` as struck-through text in the dim amber colour.
5. THE Permit_Card SHALL display the text "narrowed" next to each highlighted field so that the highlight is not conveyed by colour alone.
6. WHILE the state permit equals the Home_Permit, THE Permit_Card SHALL display no struck-through action.
7. THE Permit_Card SHALL show the state-permit values, including the imposed allowance 40 after the Vault border, because the Meters use the home limits.

### Requirement 5: [5.5] Timeline and event detail

**User Story:** As a viewer, I want a colour-coded list of every event with a detail view, so that I can inspect exactly what happened and why.

#### Acceptance Criteria

1. THE Timeline SHALL list every Event of the selected Replay, one row per Event, showing `seq`, a coloured dot, the event type label and a brief summary.
2. THE Timeline SHALL colour each row according to the semantic mapping of docs/UI_BRIEF.md section 2 and SHALL show the event type and decision or reason as text.
3. WHEN the user selects a Timeline row by click, or by Enter or Space while the row has focus, THE UI SHALL set the Playback_Index to that row's Event index.
4. THE Timeline SHALL mark the row at the Playback_Index as selected and SHALL expose that state to assistive technology.
5. WHEN the Playback_Index changes during playback, THE Timeline SHALL scroll the selected row into view.
6. THE Event_Detail SHALL display the full JSON of the Event at the Playback_Index in a preformatted block.
7. WHEN the Event at the Playback_Index has a `data.explain` string, THE Event_Detail SHALL display it above the JSON in italic text.
8. WHEN the Event at the Playback_Index has no `data.explain` string, THE Event_Detail SHALL display the JSON without an explain line.
9. THE UI SHALL display the Event_Detail content as always-visible text, with no information available only in a tooltip.
10. THE Timeline SHALL show rows for Events after the Playback_Index dimmed, not hidden, and the dimmed text SHALL keep a contrast ratio of at least 4.5:1 against the row background.
11. THE dimmed Timeline rows SHALL remain keyboard-reachable and selectable like the other rows.
12. THE Timeline SHALL render the text of every row that has a tinted background (the selected row on `--amber-glow` and the KILLED and RUN_ENDED KILLED rows on `--red-glow`) in `--amber`, SHALL express the event colour only in the row marker and the left border, and SHALL use no coloured text (`--red`, `--blue`, `--purple`, `--orange`, `--row-dim`) on any tinted background; the row text SHALL keep a contrast ratio of at least 4.5:1 against the tinted background.

### Requirement 6: [5.6] Playback controls

**User Story:** As a viewer, I want to play, pause, step and scrub through a run, so that I can control the pace of the story.

#### Acceptance Criteria

1. WHEN a Replay is loaded, THE Playback_Controller SHALL start paused at Playback_Index 0.
2. WHEN the user activates play, THE Playback_Controller SHALL advance the Playback_Index by one Event per tick at the selected speed.
3. WHEN the user activates pause, THE Playback_Controller SHALL stop advancing the Playback_Index.
4. WHEN the user activates step forward, THE Playback_Controller SHALL increase the Playback_Index by one.
5. WHEN the user activates step back, THE Playback_Controller SHALL decrease the Playback_Index by one.
6. THE Playback_Controller SHALL offer the speeds 1×, 2× and 4×, with 1× as the default.
7. WHEN the user changes speed during playback, THE Playback_Controller SHALL continue playback at the new speed without changing the Playback_Index.
8. WHEN the user moves the scrub slider, THE Playback_Controller SHALL set the Playback_Index to the slider value.
9. THE Playback_Controller SHALL keep the Playback_Index within the range 0 to `events.length - 1` for every sequence of play, pause, step forward, step back, speed and scrub actions.
10. IF step forward is requested at the last Event, THEN THE Playback_Controller SHALL keep the Playback_Index unchanged.
11. IF step back is requested at Event 0, THEN THE Playback_Controller SHALL keep the Playback_Index unchanged.
12. WHEN playback reaches the last Event, THE Playback_Controller SHALL stop playback.
13. IF a scrub value is outside the valid range, THEN THE Playback_Controller SHALL clamp it into the range 0 to `events.length - 1`.
14. IF a Replay contains no Events, THEN THE Playback_Controller SHALL hold the Playback_Index at 0 and THE UI SHALL display an empty-replay message.
15. THE UI SHALL render step back, play or pause, step forward, each speed option and the scrub slider as keyboard-focusable controls operable with Enter or Space, with a 2px amber focus outline offset by 2px on `:focus-visible`.
16. THE UI SHALL give icon-only playback buttons an ARIA label, and SHALL display the position as text "event N of M".
17. THE UI SHALL announce status changes during playback through an `aria-live="polite"` region.
18. THE UI SHALL render the pressed and selected states of its controls (the speed buttons, the compare toggle and the compare tabs) with a 1px `--border` outline and a text marker, and SHALL use no tinted background for any control state.

### Requirement 7: [5.7] Compare view

**User Story:** As a viewer, I want the unenforced and enforced runs side by side, so that I can see the difference the permit makes at the same moment.

#### Acceptance Criteria

1. THE UI SHALL derive the Turn of every Event from the Event list alone, following the Turn definition in the Glossary.
2. THE Compare_View SHALL play the Replay with `meta.enforce` false in the left column headed "WITHOUT ENFORCEMENT" and the Replay with `meta.enforce` true in the right column headed "WITH ENFORCEMENT", where the left and right columns are the Replays resolved by the Compare_Pair pairing.
3. THE Compare_View SHALL render in each column its own Place_Card pair, Meters, Permit_Card and Timeline.
4. THE Compare_View SHALL drive both columns from one shared Turn value controlled by one set of playback controls.
5. FOR EACH side and each Turn value, THE Compare_View SHALL select the index of the last Event whose Turn is less than or equal to the shared Turn value.
6. WHILE the shared Turn value is greater than the last Turn of one Replay, THE Compare_View SHALL hold that Replay at its last Event.
7. THE Compare_View SHALL select a valid Event index within `[0, events.length - 1]` on each side for every shared Turn value of zero or greater.
8. WHEN the shared Turn value advances past the Turn of the enforced `KILLED` Event, THE Compare_View SHALL keep the enforced column on its terminal `RUN_ENDED` Event while the unenforced column continues.
9. WHILE the viewport width is below 768px, THE Compare_View SHALL show a tab switcher with one tab per column instead of two side-by-side columns.
10. THE Compare_View SHALL keep both columns reachable by keyboard in the tab switcher and SHALL expose the active tab to assistive technology.
11. IF the Replay_Index does not contain exactly one entry whose id ends with "-enforced" and one entry whose id ends with "-unenforced" that share the same id stem and the same meta.scenario, THEN THE UI SHALL display a message that the compare view is unavailable.
12. THE Compare_View SHALL pair an "-enforced" Replay only with the "-unenforced" Replay of the same id stem and scenario, SHALL never pair a Replay that has no "-unenforced" counterpart (for example "forged-identity-refused"), and the replay file format SHALL gain no pair field.

### Requirement 8: [5.8] Replay labels, picker and honesty note

**User Story:** As a viewer, I want each replay honestly labelled and a permanent statement of the limits of permits, so that I am not misled about what was demonstrated.

#### Acceptance Criteria

1. THE ReplayPicker SHALL list every entry of the Replay_Index showing its `title` and a driver label.
2. THE UI SHALL show the label "scripted agent" for a Replay whose `driver` field is `scripted`.
3. THE UI SHALL show the label "live LLM" for a Replay whose `driver` field is `llm`.
4. THE UI SHALL display the driver label next to the title of the selected Replay in the header and in each Compare_View column.
5. THE UI SHALL display the Honesty_Note with the text "Permits do not stop an injection that stays inside the permit boundary. Recorded runs are labelled scripted or live LLM." in italic text.
6. THE UI SHALL keep the Honesty_Note visible at the bottom of the viewport at all times, with no control to dismiss it.
7. THE ReplayPicker SHALL be operable by keyboard and SHALL change the selected Replay without a page reload.

### Requirement 9: [5.9] KILLED event presentation

**User Story:** As a viewer, I want the kill to be unmistakable, so that the key moment of the demo cannot be missed.

#### Acceptance Criteria

1. WHEN a `KILLED` Event is displayed in the Timeline, THE Timeline SHALL render its row with the text in the amber colour (`--amber`) on a red-tinted background (`--red-glow`), with a red marker and a red left border, and with a font size larger than other rows, and the row text SHALL keep a contrast ratio of at least 4.5:1 against the tinted background.
2. THE KILLED row SHALL contain the text "KILLED", the `data.reason` code, the `data.limit` value and the `data.observed` value as text.
3. WHEN the Playback_Index is at or after a `KILLED` Event, THE UI SHALL display the text "KILLED" and the reason code in the status area.
4. WHEN the Event at the Playback_Index is `KILLED`, THE Event_Detail SHALL display the reason, limit and observed values above the JSON.
5. WHEN the Playback_Index is at or after the `RUN_ENDED` Event with status `KILLED`, THE UI SHALL render that `RUN_ENDED` row with amber text on the red-tinted background (`--red-glow`), with a red marker and a red left border, and with the text "KILLED".
6. WHEN the Playback_Index is at or after the `RUN_ENDED` Event with status `HARNESS_CAP`, THE UI SHALL render that row in dim amber with the text "HARNESS_CAP".
7. WHERE the user has enabled reduced motion, THE UI SHALL present the KILLED state without any animation, and the KILLED state SHALL remain identifiable through text alone.
8. THE UI SHALL stop the title cursor blink when status is `KILLED`, `FINISHED` or `REFUSED`, and SHALL blink it only while status is `ALIVE` and motion is allowed.

### Requirement 10: [5.10] Network, dependencies and verification constraints

**User Story:** As the project owner, I want the UI to be self-contained and verifiable, so that it runs on a static host with zero keys and zero backend.

#### Acceptance Criteria

1. THE UI SHALL request only `./replays/index.json` and the Replay files named in it, each by relative URL.
2. THE UI SHALL load no external font, CDN asset, analytics script, tracking pixel, image or other remote resource.
3. THE UI SHALL render all text with system fonts only, using the font stack of docs/UI_BRIEF.md section 3.
4. THE UI SHALL use no dependency beyond those already declared in `frontend/package.json`, and property tests SHALL use a Seeded_Generator written in the repository instead of a property-testing library.
5. THE UI SHALL compile with TypeScript strict mode, with no `any` type and no non-null assertion in application code.
6. THE UI SHALL set `base: './'` in `vite.config.ts`.
7. THE UI SHALL perform no autoplay and SHALL show no modal dialog or popup.
8. THE vitest suite SHALL run in the node environment and SHALL read the real Replay files from `frontend/public/replays/`.
9. FOR EACH Replay file and each prefix of its Events, THE vitest suite SHALL verify that the Reducer result equals the `place`, `step` and `spent` of the prefix's last Event and the permit and status rules of Requirement 5.3.
10. FOR EACH Replay file, THE vitest suite SHALL verify that the file parses against the TypeScript types, that the enforced Replay's last non-terminal Event is `KILLED` with reason `ALLOWANCE_EXCEEDED`, limit 40 and observed 41, and that the unenforced Replay contains no `KILLED` Event.
11. FOR ALL generated sequences of playback actions drawn from a Seeded_Generator, THE vitest suite SHALL verify that the Playback_Index stays within `[0, events.length - 1]`.
12. FOR ALL generated observed and limit pairs (including limit 0 and observed equal to limit) drawn from a Seeded_Generator, THE vitest suite SHALL verify the bar percentage clamp and that the Over_Limit flag is true exactly when observed is greater than limit.
13. FOR ALL Turn values of zero or greater drawn from a Seeded_Generator, THE vitest suite SHALL verify that the Compare_View selects a valid Event index on both sides.
14. THE command `npm --prefix frontend test` SHALL pass and THE command `npm --prefix frontend run build` SHALL pass.

### Requirement 11: [5.11] Visual style and accessibility

**User Story:** As a viewer, I want a retro terminal look that is readable and accessible, so that the demo is memorable and usable by everyone.

#### Acceptance Criteria

1. THE UI SHALL define all colours as CSS custom properties on `:root` using the palette of docs/UI_BRIEF.md section 2, with amber text on a near-black background and a monospace font.
2. THE UI SHALL keep all styles in the single file `frontend/src/styles.css` and SHALL use plain CSS only, with no CSS framework or component library.
3. WHERE the user agent reports `prefers-reduced-motion: reduce`, THE UI SHALL set animation and transition durations to effectively zero and SHALL remove the cursor blink.
4. THE UI SHALL convey every state (ADMIT, ADMIT_IMPOSED, REFUSE, DENIED, KILLED, OVER LIMIT) through a text label in addition to colour.
5. THE UI SHALL use semantic elements (`main`, `nav`, `section`, `button`, `table`) for its regions and controls.
6. WHILE the viewport width is below 768px, THE UI SHALL stack the left and right regions vertically.
7. THE UI SHALL contain no General Magic, AT&T or Telescript logo, no third-party trademark and no copyrighted imagery.
8. THE UI SHALL limit Telescript-related wording to the terms "permit", "place", "teleclick", the phrase "the engine destroyed the agent", and the year "1994" in a subtitle, as listed in docs/UI_BRIEF.md section 9.
9. THE UI SHALL contain no cartoon Halloween decoration, no canvas or WebGL element, and no sound.
