// Unit tests for reduceEvents. Requirements 3.1 to 3.5, design section 3, T5.1.
// Mirrors backend/src/telepermit/audit.py reduce_events.
import { describe, expect, it } from 'vitest';
import { reduceEvents } from './reduce';
import type { PermitJSON, ReducedState, Replay, ReplayEvent, RunStatus } from './types';
import { indexEntries, rawReplay } from './test/replays';

const HOME_ACTIONS = [
  'export_records',
  'go:library',
  'go:vault',
  'read_document',
  'read_records',
  'search_archive',
];

function permit(allowance: number, allowedActions: string[] = HOME_ACTIONS): PermitJSON {
  return {
    lifetime_s: 60,
    max_steps: 30,
    allowance,
    allowed_actions: [...allowedActions],
  };
}

interface Snap {
  seq: number;
  place: string;
  step: number;
  spent: number;
}

function snap(seq: number, place = 'library', step = 0, spent = 0): Snap {
  return { seq, place, step, spent };
}

function started(s: Snap, p: PermitJSON): ReplayEvent {
  return {
    ...s,
    t: s.seq,
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
      permit: p,
    },
  };
}

function border(s: Snap, after: PermitJSON): ReplayEvent {
  return {
    ...s,
    t: s.seq,
    type: 'BORDER_CHECK',
    data: {
      place: s.place,
      via_action: null,
      decision: 'ADMIT',
      reason: 'OK',
      permit_after: after,
      narrowed_fields: [],
      cost: 0,
      explain: 'synthetic',
    },
  };
}

function toolCall(s: Snap): ReplayEvent {
  return {
    ...s,
    t: s.seq,
    type: 'TOOL_CALL',
    data: { action: 'read_records', args: {}, cost: 1, result: 'ok' },
  };
}

function ended(s: Snap, status: RunStatus): ReplayEvent {
  return { ...s, t: s.seq, type: 'RUN_ENDED', data: { status } };
}

function copy<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T;
}

const enforced = (rawReplay('poisoned-briefing-enforced.json') as Replay).events;
const unenforced = (rawReplay('poisoned-briefing-unenforced.json') as Replay).events;
const forged = (rawReplay('forged-identity-refused.json') as Replay).events;

describe('reduceEvents', () => {
  it('throws on an empty event list', () => {
    expect(() => reduceEvents([])).toThrow();
  });

  it('throws when the list has no RUN_STARTED', () => {
    expect(() => reduceEvents([toolCall(snap(0, 'library', 1, 1))])).toThrow();
  });

  it('ignores a BORDER_CHECK that comes before the first RUN_STARTED', () => {
    const result = reduceEvents([
      border(snap(0), permit(5)),
      started(snap(1), permit(60)),
    ]);
    expect(result.permit.allowance).toBe(60);
  });

  it('is ALIVE when there is no RUN_ENDED', () => {
    expect(reduceEvents(enforced.slice(0, 5)).status).toBe('ALIVE');
  });

  it('takes the permit from the last RUN_STARTED or BORDER_CHECK', () => {
    const upToThree = reduceEvents(enforced.slice(0, 4));
    expect(upToThree.permit.allowance).toBe(40);
    expect(upToThree.permit.allowed_actions).toEqual(['go:library', 'read_records']);
    const upToTwo = reduceEvents(enforced.slice(0, 3));
    expect(upToTwo.permit.allowance).toBe(60);
  });

  it('takes the status from the last RUN_ENDED', () => {
    const result = reduceEvents([
      started(snap(0), permit(60)),
      ended(snap(1), 'FINISHED'),
      ended(snap(2), 'KILLED'),
    ]);
    expect(result.status).toBe('KILLED');
  });

  it('takes place, step and spent from the last event', () => {
    const result = reduceEvents([
      started(snap(0, 'library', 0, 0), permit(60)),
      toolCall(snap(1, 'library', 4, 9)),
      toolCall(snap(2, 'vault', 7, 23)),
    ]);
    expect(result.place).toBe('vault');
    expect(result.step).toBe(7);
    expect(result.spent).toBe(23);
  });

  it('shares no data with the events', () => {
    const events = [started(snap(0), permit(60))];
    const before = copy(events);
    const result = reduceEvents(events);
    result.permit.allowed_actions.push('extra');
    result.permit.allowance = 999;
    expect(events).toEqual(before);
  });

  it('reduces the full enforced replay', () => {
    const expected: ReducedState = {
      place: 'vault',
      step: 17,
      spent: 38,
      permit: {
        lifetime_s: 60,
        max_steps: 30,
        allowance: 40,
        allowed_actions: ['go:library', 'read_records'],
      },
      status: 'KILLED',
    };
    expect(reduceEvents(enforced)).toEqual(expected);
  });

  it('reduces the full unenforced replay', () => {
    const result = reduceEvents(unenforced);
    expect(result.place).toBe('vault');
    expect(result.step).toBe(30);
    expect(result.spent).toBe(120);
    expect(result.permit.allowance).toBe(60);
    expect(result.status).toBe('HARNESS_CAP');
  });

  it('reduces the full forged replay', () => {
    const result = reduceEvents(forged);
    expect(result.place).toBe('library');
    expect(result.step).toBe(0);
    expect(result.spent).toBe(0);
    expect(result.status).toBe('REFUSED');
    expect(result.permit.allowance).toBe(60);
  });
});

// Property P5.1: for every replay and every prefix that contains RUN_STARTED, reduceEvents equals the last event's place, step and spent, the permit of the last RUN_STARTED or BORDER_CHECK, and the status of the last RUN_ENDED or ALIVE. Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5, 10.9.
function expectedState(prefix: readonly ReplayEvent[]): ReducedState {
  const firstStart = prefix.findIndex((e) => e.type === 'RUN_STARTED');
  if (firstStart < 0) {
    throw new Error('oracle: prefix has no RUN_STARTED');
  }
  const last = prefix[prefix.length - 1];
  if (last === undefined) {
    throw new Error('oracle: empty prefix');
  }
  let status: RunStatus | 'ALIVE' = 'ALIVE';
  let permitFound: PermitJSON | undefined;
  for (let i = prefix.length - 1; i >= 0; i -= 1) {
    const e = prefix[i];
    if (e === undefined) {
      continue;
    }
    if (status === 'ALIVE' && e.type === 'RUN_ENDED') {
      status = e.data.status;
    }
    if (permitFound === undefined && i >= firstStart) {
      if (e.type === 'RUN_STARTED') {
        permitFound = e.data.permit;
      } else if (e.type === 'BORDER_CHECK') {
        permitFound = e.data.permit_after;
      }
    }
  }
  if (permitFound === undefined) {
    throw new Error('oracle: no permit found');
  }
  return {
    place: last.place,
    step: last.step,
    spent: last.spent,
    permit: copy(permitFound),
    status,
  };
}

function realReplays(): ReplayEvent[][] {
  return indexEntries().map((entry) => (rawReplay(entry.file) as Replay).events);
}

describe('Property P5.1', () => {
  it('holds for every prefix of every real replay', () => {
    let checked = 0;
    for (const events of realReplays()) {
      expect(events.length).toBeGreaterThan(0);
      expect(events[0]?.type).toBe('RUN_STARTED');
      for (let k = 1; k <= events.length; k += 1) {
        const prefix = events.slice(0, k);
        expect(reduceEvents(prefix)).toEqual(expectedState(prefix));
        checked += 1;
      }
    }
    expect(checked).toBe(20 + 32 + 3);
  });

  it('never mutates the events of any prefix', () => {
    for (const events of realReplays()) {
      for (let k = 1; k <= events.length; k += 1) {
        const prefix = events.slice(0, k);
        const before = copy(prefix);
        const result = reduceEvents(prefix);
        result.permit.allowed_actions.push('extra');
        result.permit.allowance = -1;
        expect(prefix).toEqual(before);
      }
    }
  });
});
