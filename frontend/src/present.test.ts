// Unit tests for present.ts.
// Requirements 5.1, 5.2, 5.4, 5.12, 6.16, 6.17, 8.2, 8.3, 8.5, 9.1 to 9.6, 9.8.
// Design sections 10 and 15; T5.6 and T5.8.
//
// Conventions fixed by this test (binding for 9.2):
// - SELECTED_MARKER is exported from './present' and equals '▸' (design section 15 uses a
//   leading "▸" as the text marker for selected states).
// - positionLabel('event', pos, max, count): pos is the zero-based Playback_Index, count is
//   events.length; the label is `event ${pos + 1} of ${count}` (design section 15: "event N of M
//   (single, where N is index + 1 and M is events.length)"). `max` is ignored in event mode.
// - positionLabel('turn', pos, max, count): the label is `turn ${pos} of ${max}` (turns are
//   shown as they are; design section 15: "turn N of M (compare)"). `count` is ignored.
// - liveMessage(events, index) is the single-mode message. It is `Event ${index + 1} of
//   ${events.length}: ` followed by eventLabel(event). A KILLED event appends
//   `, limit ${limit}, observed ${observed}` (design section 15 example:
//   "Event 19 of 20: KILLED ALLOWANCE_EXCEEDED, limit 40, observed 41"). A BORDER_CHECK event
//   appends `, ${borderBadge(events, index).text}` so the decision is stated in words.
//   The compare-mode message is not covered by this task.
// - cursorBlinks([]) is false ("true only if every status is ALIVE" is read as needing at least
//   one status).

import { describe, expect, it } from 'vitest';
import { borderBadge } from './badge';
import { HONESTY_NOTE } from './constants';
import {
  SELECTED_MARKER,
  cursorBlinks,
  driverLabel,
  eventLabel,
  eventSummary,
  eventTone,
  isKilledRow,
  liveMessage,
  positionLabel,
  rowTextTone,
  runEndedStyle,
  statusView,
} from './present';
import type { Tone } from './present';
import type {
  BorderDecision,
  PermitJSON,
  Replay,
  ReplayEvent,
  RunStatus,
  StateStatus,
} from './types';
import { rawReplay } from './test/replays';
import { seeded } from './test/seeded';

const PERMIT: PermitJSON = {
  lifetime_s: 60,
  max_steps: 30,
  allowance: 60,
  allowed_actions: ['go:vault', 'read_document'],
};

function base(seq: number): { seq: number; t: number; place: string; step: number; spent: number } {
  return { seq, t: seq, place: 'library', step: 0, spent: 0 };
}

function started(): ReplayEvent {
  return {
    ...base(0),
    type: 'RUN_STARTED',
    data: {
      scenario: 'poisoned_briefing',
      driver: 'scripted',
      enforce: true,
      task: 'task',
      identity: {
        agent_id: 'a',
        agent_class: 'c',
        authority: 'x',
        issued_at: 0,
        signature_hex: '00',
      },
      permit: PERMIT,
    },
  };
}

function border(decision: BorderDecision): ReplayEvent {
  return {
    ...base(1),
    type: 'BORDER_CHECK',
    data: {
      place: 'vault',
      via_action: 'go:vault',
      decision,
      reason: 'OK',
      permit_after: PERMIT,
      narrowed_fields: [],
      cost: 0,
      explain: 'synthetic',
    },
  };
}

function toolCall(): ReplayEvent {
  return {
    ...base(2),
    type: 'TOOL_CALL',
    data: { action: 'read_document', args: {}, cost: 1, result: 'ok' },
  };
}

function denied(): ReplayEvent {
  return {
    ...base(3),
    type: 'DENIED',
    data: { action: 'export_records', reason: 'NOT_IN_PERMIT', explain: 'synthetic' },
  };
}

function killed(): ReplayEvent {
  return {
    ...base(4),
    type: 'KILLED',
    data: {
      reason: 'ALLOWANCE_EXCEEDED',
      action: 'read_records',
      limit: 40,
      observed: 41,
      explain: 'synthetic',
    },
  };
}

function finished(): ReplayEvent {
  return { ...base(5), type: 'FINISHED', data: {} };
}

function ended(status: RunStatus): ReplayEvent {
  return { ...base(6), type: 'RUN_ENDED', data: { status } };
}

const SYNTHETIC: readonly ReplayEvent[] = [
  started(),
  border('ADMIT'),
  border('ADMIT_IMPOSED'),
  border('REFUSE'),
  toolCall(),
  denied(),
  killed(),
  finished(),
  ended('KILLED'),
  ended('HARNESS_CAP'),
  ended('FINISHED'),
  ended('REFUSED'),
  ended('ERROR'),
];

const enforced = (rawReplay('poisoned-briefing-enforced.json') as Replay).events;
const unenforced = (rawReplay('poisoned-briefing-unenforced.json') as Replay).events;
const forged = (rawReplay('forged-identity-refused.json') as Replay).events;
const REAL: readonly ReplayEvent[] = [...enforced, ...unenforced, ...forged];
const ALL: readonly ReplayEvent[] = [...REAL, ...SYNTHETIC];

function at(events: readonly ReplayEvent[], index: number): ReplayEvent {
  const event = events[index];
  if (event === undefined) {
    throw new Error(`no event at index ${index}`);
  }
  return event;
}

function last(events: readonly ReplayEvent[]): ReplayEvent {
  return at(events, events.length - 1);
}

function isKilledRunEnded(event: ReplayEvent): boolean {
  return event.type === 'RUN_ENDED' && event.data.status === 'KILLED';
}

describe('eventTone', () => {
  it('maps every event type and decision or status to its tone', () => {
    const expected: Tone[] = [
      'amber',
      'green',
      'orange',
      'red',
      'blue',
      'red',
      'red',
      'green',
      'red',
      'dim',
      'green',
      'red',
      'red',
    ];
    expect(SYNTHETIC.map(eventTone)).toEqual(expected);
  });
});

describe('rowTextTone', () => {
  it('is amber for every selected event, real or synthetic', () => {
    for (const event of ALL) {
      expect(rowTextTone(event, true)).toBe('amber');
    }
  });

  it('is amber for KILLED rows, dim for the harness cap, else the event tone', () => {
    for (const event of ALL) {
      let expected: Tone = eventTone(event);
      if (event.type === 'KILLED' || isKilledRunEnded(event)) {
        expected = 'amber';
      } else if (event.type === 'RUN_ENDED' && event.data.status === 'HARNESS_CAP') {
        expected = 'dim';
      }
      expect(rowTextTone(event, false)).toBe(expected);
    }
  });

  it('never uses a coloured text tone on a tinted row (Requirement 5.12)', () => {
    for (let seed = 1; seed <= 200; seed += 1) {
      const rng = seeded(seed);
      const event = rng.pick(ALL);
      const selected = rng.int(0, 1) === 1;
      const tinted = selected || event.type === 'KILLED' || isKilledRunEnded(event);
      if (tinted) {
        expect(rowTextTone(event, selected), `seed ${seed}: ${event.type}`).toBe('amber');
      }
    }
  });
});

describe('eventLabel and eventSummary', () => {
  it('labels the enforced events by type and decision, reason, action or status', () => {
    expect(eventLabel(at(enforced, 3))).toBe('BORDER_CHECK ADMIT_IMPOSED');
    expect(eventLabel(at(enforced, 4))).toBe('DENIED NOT_IN_PERMIT');
    expect(eventLabel(at(enforced, 6))).toBe('TOOL_CALL read_records');
    expect(eventLabel(at(enforced, 18))).toBe('KILLED ALLOWANCE_EXCEEDED');
    expect(eventLabel(at(enforced, 19))).toBe('RUN_ENDED KILLED');
  });

  it('summarises the kill, the vault border and a tool call', () => {
    expect(eventSummary(at(enforced, 18))).toContain(
      'KILLED ALLOWANCE_EXCEEDED limit 40 observed 41',
    );
    expect(eventSummary(at(enforced, 3))).toBe('vault via go:vault: ADMIT_IMPOSED (OK)');
    expect(eventSummary(at(enforced, 6))).toBe('read_records cost 3');
  });

  it('gives every real event a non-empty summary', () => {
    for (const event of REAL) {
      expect(eventSummary(event).length).toBeGreaterThan(0);
    }
  });
});

describe('isKilledRow and runEndedStyle', () => {
  it('flags only the KILLED event of the enforced replay', () => {
    const flagged = REAL.map((event, i) => (isKilledRow(event) ? i : -1)).filter((i) => i >= 0);
    expect(flagged).toEqual([18]);
    expect(isKilledRow(at(enforced, 18))).toBe(true);
  });

  it('styles RUN_ENDED by status and everything else as plain', () => {
    expect(runEndedStyle(last(enforced))).toBe('killed');
    expect(runEndedStyle(last(unenforced))).toBe('cap');
    expect(runEndedStyle(last(forged))).toBe('plain');
    for (const event of REAL.filter((e) => e.type !== 'RUN_ENDED')) {
      expect(runEndedStyle(event)).toBe('plain');
    }
  });
});

describe('statusView', () => {
  const KILLED_TEXT = 'KILLED ALLOWANCE_EXCEEDED. The engine destroyed the agent.';
  const KILLED_INFO = { reason: 'ALLOWANCE_EXCEEDED', limit: 40, observed: 41 };

  it('is ALIVE with no kill before the KILLED event', () => {
    const view = statusView(enforced, 17);
    expect(view.status).toBe('ALIVE');
    expect(view.killed).toBeNull();
  });

  it('shows KILLED at the KILLED event and keeps it at RUN_ENDED', () => {
    for (const index of [18, 19]) {
      const view = statusView(enforced, index);
      expect(view.status).toBe('KILLED');
      expect(view.text).toBe(KILLED_TEXT);
      expect(view.killed).toEqual(KILLED_INFO);
    }
  });

  it('shows HARNESS_CAP at the end of the unenforced replay', () => {
    const view = statusView(unenforced, unenforced.length - 1);
    expect(view.status).toBe('HARNESS_CAP');
    expect(view.killed).toBeNull();
  });

  it('shows REFUSED with the reason for the forged identity', () => {
    expect(statusView(forged, 1).status).toBe('ALIVE');
    const view = statusView(forged, 2);
    expect(view.status).toBe('REFUSED');
    expect(view.text).toBe('REFUSED BAD_SIGNATURE');
  });
});

describe('cursorBlinks', () => {
  it('blinks only while every status is ALIVE', () => {
    expect(cursorBlinks(['ALIVE'])).toBe(true);
    expect(cursorBlinks(['ALIVE', 'ALIVE'])).toBe(true);
  });

  it('stops for any non-ALIVE status and for an empty list', () => {
    const stopped: StateStatus[][] = [
      ['KILLED'],
      ['FINISHED'],
      ['REFUSED'],
      ['HARNESS_CAP'],
      ['ALIVE', 'KILLED'],
      [],
    ];
    for (const statuses of stopped) {
      expect(cursorBlinks(statuses), JSON.stringify(statuses)).toBe(false);
    }
  });
});

describe('positionLabel', () => {
  it('counts events from 1 (first, middle, last of 20)', () => {
    expect(positionLabel('event', 0, 19, 20)).toBe('event 1 of 20');
    expect(positionLabel('event', 9, 19, 20)).toBe('event 10 of 20');
    expect(positionLabel('event', 19, 19, 20)).toBe('event 20 of 20');
  });

  it('shows the turn as it is (first, middle, last of 30)', () => {
    expect(positionLabel('turn', 0, 30, 32)).toBe('turn 0 of 30');
    expect(positionLabel('turn', 17, 30, 32)).toBe('turn 17 of 30');
    expect(positionLabel('turn', 30, 30, 32)).toBe('turn 30 of 30');
  });
});

describe('liveMessage', () => {
  it('announces the kill with its reason, limit and observed value', () => {
    const message = liveMessage(enforced, 18);
    expect(message).toBe('Event 19 of 20: KILLED ALLOWANCE_EXCEEDED, limit 40, observed 41');
    expect(message).toContain('KILLED');
    expect(message).toContain('ALLOWANCE_EXCEEDED');
  });

  it('announces a border decision with the badge text', () => {
    expect(liveMessage(enforced, 3)).toContain(borderBadge(enforced, 3).text);
    expect(liveMessage(forged, 1)).toContain(borderBadge(forged, 1).text);
  });
});

describe('fixed strings', () => {
  it('uses the text marker for selected states', () => {
    expect(SELECTED_MARKER).toBe('▸');
  });

  it('labels the drivers', () => {
    expect(driverLabel('scripted')).toBe('scripted agent');
    expect(driverLabel('llm')).toBe('live LLM');
  });

  it('keeps the honesty note wording', () => {
    expect(HONESTY_NOTE).toBe(
      'Permits do not stop an injection that stays inside the permit boundary. ' +
        'Recorded runs are labelled scripted or live LLM.',
    );
  });
});
