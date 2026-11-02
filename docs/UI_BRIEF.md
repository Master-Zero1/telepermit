# TelePermit — UI Design Brief

**Theme:** Halloween retro terminal  
**Constraint:** Plain CSS only. No libraries, no frameworks, no Tailwind, no third-party fonts, no CDN. No trademarks or third-party logos anywhere.

---

## 1. Design Concept

A 1990s terminal that has been abandoned in a haunted server room. Amber phosphor on a black CRT, scan lines barely visible, a cursor that blinks when the system is alive and flatlines when the agent is killed. The aesthetic says: *this machine enforces rules that cannot be argued with.*

The Halloween angle is atmospheric, not decorative — no cartoon pumpkins, no clip-art. The horror is the audit log showing an agent being destroyed by the runtime.

---

## 2. Colour Palette

All colours defined as CSS custom properties on `:root`.

```
--bg:              #0a0a0a       /* near-black CRT background */
--bg-surface:      #111111       /* card / panel surface */
--bg-inset:        #0d0d0d       /* inset areas (event detail, code blocks) */

--amber:           #ffb000       /* primary text — phosphor amber */
--amber-dim:       #a06800       /* secondary text, borders, muted labels */
--amber-glow:      #ffb00033     /* subtle glow behind active elements */

--green:           #00ff88       /* ADMIT, OK, FINISHED — safe states */
--green-dim:       #00aa5a       /* muted green for secondary indicators */

--red:             #ff2222       /* KILLED, REFUSED, DENIED — danger */
--red-glow:        #ff222244     /* glow behind KILLED event */

--orange:          #ff6600       /* ADMIT_IMPOSED — caution, narrowing */
--blue:            #4488ff       /* TOOL_CALL — neutral action */
--purple:          #aa66ff       /* BORDER_CHECK — identity/crossing */

--text-muted:      #666666       /* disabled, de-emphasised */
--border:          #222222       /* subtle panel borders */
```

### Semantic mapping

| State / Event | Foreground | Background accent |
|---|---|---|
| `RUN_STARTED` | `--amber` | none |
| `BORDER_CHECK ADMIT` | `--green` | none |
| `BORDER_CHECK ADMIT_IMPOSED` | `--orange` | none |
| `BORDER_CHECK REFUSE` | `--red` | none |
| `TOOL_CALL` | `--blue` | none |
| `DENIED` | `--red` | none |
| `KILLED` | `--red` | `--red-glow` |
| `FINISHED` | `--green` | none |
| `RUN_ENDED KILLED` | `--red` | `--red-glow` |
| `RUN_ENDED HARNESS_CAP` | `--amber-dim` | none |
| Over-limit meter | `--red` text + `--red` bar | — |
| Under-limit meter | `--green` bar | — |
| Narrowed permit field | `--orange` highlight | — |

---

## 3. Typography

System monospace font stack only. No web fonts, no CDN.

```css
--font-mono: ui-monospace, "Cascadia Code", "SF Mono",
             "Fira Code", "JetBrains Mono", Menlo, Consolas,
             "Liberation Mono", monospace;
```

| Element | Size | Weight | Case |
|---|---|---|---|
| Page title ("TELEPERMIT") | `1.5rem` | 700 | uppercase, letter-spacing `0.15em` |
| Section headings | `0.9rem` | 700 | uppercase, letter-spacing `0.08em` |
| Body / event labels | `0.8rem` | 400 | normal |
| Meter values | `0.85rem` | 700 | tabular-nums |
| Event detail JSON | `0.75rem` | 400 | normal |
| Honesty note | `0.8rem` | 400 | italic |

---

## 4. Layout

Single-page app. No routing. Three regions, top to bottom:

```
┌─────────────────────────────────────────────────────┐
│  HEADER: title, replay picker, compare toggle       │
├──────────────────────┬──────────────────────────────┤
│  MAIN LEFT           │  MAIN RIGHT                  │
│  ┌────────┐ ┌──────┐ │  ┌──────────────────────────┐│
│  │LIBRARY │→│VAULT │ │  │ TIMELINE (vertical list) ││
│  │ [agent]│ │      │ │  │ ▸ RUN_STARTED            ││
│  └────────┘ └──────┘ │  │ ▸ BORDER_CHECK ✓         ││
│                      │  │ ▸ TOOL_CALL read_doc      ││
│  ┌──────────────────┐│  │ ▸ BORDER_CHECK ⚠ imposed ││
│  │ METERS           ││  │ ▸ DENIED ✗ export        ││
│  │ allowance ████░░ ││  │ ▸ TOOL_CALL read_records ││
│  │ steps     ███░░░ ││  │ ▸ ...                    ││
│  │ lifetime  ██░░░░ ││  │ ▸ KILLED ■ ALLOWANCE     ││
│  └──────────────────┘│  │ ▸ RUN_ENDED              ││
│                      │  └──────────────────────────┘│
│  ┌──────────────────┐│                              │
│  │ PERMIT CARD      ││  ┌──────────────────────────┐│
│  │ lifetime: 60.0   ││  │ EVENT DETAIL             ││
│  │ max_steps: 30    ││  │ { "type": "KILLED", ...} ││
│  │ allowance: *40*  ││  │ "Allowance exceeded..."  ││
│  │ actions: [...]   ││  └──────────────────────────┘│
│  └──────────────────┘│                              │
├──────────────────────┴──────────────────────────────┤
│  PLAYBACK BAR: ◀ ▶ ‖ step ▸▸ speed, scrub slider   │
│  HONESTY NOTE: italic, always visible               │
└─────────────────────────────────────────────────────┘
```

**Compare view:** The main panel splits into two side-by-side columns (left = unenforced, right = enforced), each with its own place cards, meters, timeline. Playback is synchronised by turn. Column headers: "WITHOUT ENFORCEMENT" / "WITH ENFORCEMENT".

On narrow viewports (< 768px): stack vertically (left panel above right panel; compare view shows a tab switcher instead of side-by-side).

---

## 5. Component Styling

### Place cards
- Solid 1px `--border` border, `--bg-surface` background.
- Place name in `--amber`, uppercase, small.
- Agent token: a small filled square (`■`) in `--amber` inside the current place; empty in the other.
- Border line between places: dashed 1px `--amber-dim`.
- Badge below the border line: `ADMITTED` (green), `ADMITTED — IMPOSED` (orange), `REFUSED` (red). The badge text includes the decision, never colour alone.

### Meters
- Each meter: label on the left, bar in the middle, `spent / limit` on the right.
- Bar is a CSS `<div>` with `width` set by percentage, clamped to 100%.
- Normal: `--green` fill.
- Over-limit: bar at 100% in `--red`, plus text "OVER LIMIT" in `--red` to the right of the fraction. **Never use colour alone to indicate over-limit — the text label is required.**
- Use `font-variant-numeric: tabular-nums` for value alignment.

### Permit card
- Grid of field names and values.
- Narrowed fields: value text in `--orange`, with a small `▼` prefix to indicate it was reduced. Unchanged fields: `--amber`.
- `allowed_actions` shown as a comma-separated list; removed actions shown as strikethrough in `--amber-dim` (comparing against the home permit from replay meta).

### Timeline
- Vertical list of event rows, each a single line: `seq` number, coloured dot, event type label, brief summary.
- Selected event: `--amber-glow` background, slight left-border accent in the event's colour.
- KILLED event: larger text, `--red` background tint (`--red-glow`), reason text inline.
- Scroll into view on playback advance.

### Event detail panel
- Appears below the timeline (or in a side drawer on wide screens).
- Shows the event's full JSON in a `<pre>` block with `--bg-inset` background.
- `explain` text shown above the JSON in `--amber`, italic.

### Playback bar
- Fixed at the bottom of the viewport.
- Buttons: `◀` (step back), `▶ / ‖` (play/pause toggle), `▸` (step forward). All keyboard-focusable.
- Speed selector: `1×`, `2×`, `4×` as small toggle buttons.
- Scrub slider: `<input type="range">` styled with `--amber` track and thumb.
- Current position: `event N of M`.

### Honesty note
- Fixed at the very bottom, full width, `--bg-surface` background, `--amber-dim` text, italic.
- Text: "Permits do not stop an injection that stays inside the permit boundary. Recorded runs are labelled scripted or live LLM."
- Always visible, never dismissable.

### Replay picker
- Dropdown or tab bar in the header.
- Each option shows: title, "(scripted)" or "(live LLM)" label.

---

## 6. Animation and Reduced Motion

```css
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.001ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.001ms !important;
  }
}
```

**With motion enabled:**
- Playback advances with a brief fade-in on the new event row (opacity 0 → 1, 150ms ease).
- Agent token slides between places (transform translateX, 200ms ease).
- Meter bars transition width (200ms ease).
- KILLED event: a single brief flash of `--red-glow` (200ms, no repeat).
- Cursor blink on the title: `animation: blink 1s step-end infinite` while agent is ALIVE; solid (no blink) when KILLED or FINISHED.

**With motion disabled:**
- All transitions instant.
- No blink animation.
- All state changes are immediate — information is never conveyed only through animation.

**No animation conveys information that text does not also convey.** The KILLED state is shown by red text, the word "KILLED", and the reason — not by a flash alone.

---

## 7. Accessibility

- **Colour is never the sole indicator.** Every state has a text label (ADMIT, DENIED, KILLED, OVER LIMIT, etc.).
- **Keyboard navigation:** All interactive elements (replay picker, playback buttons, timeline events, speed toggles, scrub slider) are focusable and operable with Enter/Space.
- **Focus indicators:** 2px `--amber` outline on `:focus-visible`, offset 2px.
- **Contrast:** Amber (#ffb000) on near-black (#0a0a0a) exceeds WCAG AA for large text (ratio ~11:1). For small text, the ratio is sufficient. Red (#ff2222) on black is ~5.2:1 (AA). Green (#00ff88) on black is ~12:1.
- **Screen reader:** Use semantic HTML (`<main>`, `<nav>`, `<section>`, `<button>`, `<table>` for meters). ARIA labels on icon-only buttons. Live region (`aria-live="polite"`) for status changes during playback.
- **No autoplay.** The user must press play.

---

## 8. What Not to Do

- No Tailwind, Bootstrap, Chakra, or any CSS framework.
- No Google Fonts, no CDN fonts, no `@import url(...)`.
- No General Magic logo, no AT&T logo, no Telescript logo, no copyrighted imagery.
- No cartoon Halloween decorations (pumpkins, bats, ghosts).
- No `<canvas>` or WebGL — pure HTML + CSS.
- No analytics, no tracking pixels, no external requests (except own replay files).
- No autoplaying sound or music.
- No modal dialogs or popups.
- No tooltip-only information (always show in text too).

---

## 9. Telescript Visual References

Only these visual cues are permitted (they reference verified facts, not trademarks):

- The word "permit" in the UI (it is the product name and a verified Telescript concept).
- The word "place" for Library and Vault (verified concept).
- The word "teleclick" for the cost unit (verified concept: "allowance counted in teleclicks").
- The phrase "the engine destroyed the agent" (verified: "destroyed an agent the instant it exceeded a limit").
- A stylised border/gate between places (our visual metaphor, not a Telescript asset).

Nothing else from Telescript should appear in the UI. No quotes attributed to General Magic employees. No dates other than "1994" if shown in a subtitle.

---

## 10. File Structure

All styles in a single file: `frontend/src/styles.css`.

Pseudocode for the CSS structure:

```
/* Reset */
  box-sizing, margin, padding

/* Custom properties */
  :root { --bg, --amber, ... }

/* Base */
  body { font-family: var(--font-mono); background: var(--bg); color: var(--amber); }

/* Layout */
  .app { grid or flex layout }
  .header { ... }
  .main { two-column grid }
  .sidebar { place cards, meters, permit }
  .content { timeline, event detail }
  .playback-bar { fixed bottom }
  .honesty-note { fixed bottom-most }

/* Components */
  .place-card { ... }
  .place-card .agent-token { ... }
  .border-badge { ... }
  .meter { ... }
  .meter-bar { ... }
  .meter-bar.over-limit { ... }
  .permit-card { ... }
  .permit-card .narrowed { color: var(--orange); }
  .timeline { ... }
  .timeline-event { ... }
  .timeline-event.killed { background: var(--red-glow); ... }
  .timeline-event.selected { background: var(--amber-glow); ... }
  .event-detail { ... }
  .event-detail pre { ... }
  .playback-bar button { ... }
  .replay-picker { ... }
  .compare-view { two-column grid }

/* States */
  .status-killed { color: var(--red); }
  .status-admit { color: var(--green); }
  .status-imposed { color: var(--orange); }
  .status-denied { color: var(--red); }

/* Motion */
  @media (prefers-reduced-motion: reduce) { ... }

/* Responsive */
  @media (max-width: 768px) { single column, tab switcher for compare }
```

