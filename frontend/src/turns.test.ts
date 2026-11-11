// Unit tests for the turn mapping. Requirements 7.1, 7.5 to 7.8, design sections 11 and 14, T5.7.
//
// Expected arrays were computed from frontend/public/replays/*.json with the turn rule
// (RUN_STARTED, a spawn BORDER_CHECK with via_action null, and RUN_ENDED do not start a turn):
//   enforced (20 events):   [0, 0, 1, 2, 3, ..., 16, 17, 17]  (index 18 KILLED and 19 RUN_ENDED are 17)
//   unenforced (32 events): [0, 1, 2, ..., 30, 30]            (index i is turn i for 1..30; 31 is 30)
//   forged (3 events):      [0, 0, 0]
import { describe, expect, it } from 'vitest';
import { lastTurn, selectIndex, sharedMax, turnsOf } from './turns';
import { resolveComparePair } from './pair';
import { seeded } from './test/seeded';
import type { LoadError, PermitJSON, Replay, ReplayEvent, Result } from './types';
import { indexEntries, rawReplay } from './test/replays';
import { parseReplay } from './validate';

const PERMIT: PermitJSON = {
  lifetime_s: 60,
  max_steps: 30,
  allowance: 60,
  allowed_actions: ['go:vault', 'read_document'],
};

function started(seq: number): ReplayEvent {
  return {
    seq,
    t: seq,
    place: 'library',
    step: 0,
    spent: 0,
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

function border(seq: number, viaAction: string | null): ReplayEvent {
  return {
    seq,
    t: seq,
    place: 'library',
    step: 0,
    spent: 0,
    type: 'BORDER_CHECK',
    data: {
      place: 'vault',
      via_action: viaAction,
      decision: 'ADMIT',
      reason: 'OK',
      permit_after: PERMIT,
      narrowed_fields: [],
      cost: 0,
      explain: 'synthetic',
    },
  };
}

function toolCall(seq: number): ReplayEvent {
  return {
    seq,
    t: seq,
    place: 'library',
    step: seq,
    spent: 0,
    type: 'TOOL_CALL',
    data: { action: 'read_document', args: {}, cost: 0, result: 'ok' },
  };
}

function ended(seq: number): ReplayEvent {
  return {
    seq,
    t: seq,
    place: 'library',
    step: 0,
    spent: 0,
    type: 'RUN_ENDED',
    data: { status: 'FINISHED' },
  };
}

function range(from: number, to: number): number[] {
  return Array.from({ length: to - from + 1 }, (_, offset) => from + offset);
}

const enforced = (rawReplay('poisoned-briefing-enforced.json') as Replay).events;
const unenforced = (rawReplay('poisoned-briefing-unenforced.json') as Replay).events;
const forged = (rawReplay('forged-identity-refused.json') as Replay).events;

const ENFORCED_TURNS = [0, 0, ...range(1, 17), 17];
const UNENFORCED_TURNS = [0, ...range(1, 30), 30];
const FORGED_TURNS = [0, 0, 0];

describe('turnsOf', () => {
  it('maps the enforced replay and puts KILLED and RUN_ENDED in turn 17', () => {
    expect(enforced).toHaveLength(20);
    const turns = turnsOf(enforced);
    expect(turns).toEqual(ENFORCED_TURNS);
    expect(turns[18]).toBe(17);
    expect(turns[19]).toBe(17);
  });

  it('maps the unenforced replay and starts a turn at the go:vault BORDER_CHECK', () => {
    expect(unenforced).toHaveLength(32);
    const turns = turnsOf(unenforced);
    expect(turns).toEqual(UNENFORCED_TURNS);
    expect(turns[2]).toBe(2);
  });

  it('maps the forged replay to turn 0 for every event', () => {
    expect(turnsOf(forged)).toEqual(FORGED_TURNS);
    expect(lastTurn(forged)).toBe(0);
  });

  it('joins RUN_ENDED to the previous turn and starts a turn only at a go border check', () => {
    const events = [started(0), border(1, null), border(2, 'go:vault'), toolCall(3), ended(4)];
    expect(turnsOf(events)).toEqual([0, 0, 1, 2, 2]);
  });
});

describe('lastTurn and sharedMax', () => {
  it('returns the last turn of each replay and 0 for an empty list', () => {
    expect(lastTurn(enforced)).toBe(17);
    expect(lastTurn(unenforced)).toBe(30);
    expect(lastTurn([])).toBe(0);
  });

  it('takes the larger last turn, symmetrically', () => {
    expect(sharedMax(enforced, unenforced)).toBe(30);
    expect(sharedMax(unenforced, enforced)).toBe(30);
  });
});

describe('selectIndex', () => {
  it('selects index t + 1 on the enforced turns and holds the last event after turn 17', () => {
    for (const t of range(0, 16)) {
      expect(selectIndex(ENFORCED_TURNS, t)).toBe(t + 1);
    }
    for (const t of range(17, 30)) {
      expect(selectIndex(ENFORCED_TURNS, t)).toBe(19);
    }
  });

  it('selects index t on the unenforced turns, and 31 at turn 30', () => {
    for (const t of range(0, 29)) {
      expect(selectIndex(UNENFORCED_TURNS, t)).toBe(t);
    }
    expect(selectIndex(UNENFORCED_TURNS, 30)).toBe(31);
  });

  it('returns 0 for an empty list and 2 on the forged turns', () => {
    expect(selectIndex([], 0)).toBe(0);
    expect(selectIndex([], 5)).toBe(0);
    for (const t of range(0, 5)) {
      expect(selectIndex(FORGED_TURNS, t)).toBe(2);
    }
  });
});

// Property P5.5: for any shared turn value of zero or greater, both sides of the compare view select a valid event index, equal to the last event whose turn is at most the shared turn; turnsOf is non-decreasing and increases by exactly one at each turn-starting event. Validates: Requirements 7.1, 7.5, 7.6, 7.7, 7.8, 10.13.
describe('Property P5.5', () => {
  function loadRealPair(): { unenforced: Replay; enforced: Replay } {
    const loaded: Replay[] = [];
    for (const entry of indexEntries()) {
      const result: Result<Replay, LoadError> = parseReplay(rawReplay(entry.file), entry.file);
      if (result.ok) {
        loaded.push(result.value);
      }
    }
    const pair = resolveComparePair(loaded);
    if (pair.kind !== 'pair') {
      throw new Error('real replays did not resolve to a compare pair');
    }
    return { unenforced: pair.unenforced, enforced: pair.enforced };
  }

  function oracleIndex(turns: readonly number[], turn: number): number {
    let found = 0;
    for (let i = 0; i < turns.length; i += 1) {
      if (turns[i] <= turn) {
        found = i;
      }
    }
    return found;
  }

  it('turnsOf starts at 0, never decreases and steps by exactly one at turn-starting events', () => {
    for (const events of [enforced, unenforced, forged]) {
      const turns = turnsOf(events);
      expect(turns).toHaveLength(events.length);
      expect(turns[0]).toBe(0);
      for (let i = 1; i < events.length; i += 1) {
        const event = events[i];
        const joinsPrevious =
          event.type === 'RUN_STARTED' ||
          event.type === 'RUN_ENDED' ||
          (event.type === 'BORDER_CHECK' && event.data.via_action === null);
        expect(turns[i] - turns[i - 1], `event ${i}`).toBe(joinsPrevious ? 0 : 1);
      }
    }
  });

  it('selects a valid index on both sides for 200 seeded turn values', () => {
    const pair = loadRealPair();
    for (let seed = 1; seed <= 200; seed += 1) {
      const rng = seeded(seed);
      const pick = rng.int(0, 2);
      const turn = pick === 0 ? rng.int(0, 30) : pick === 1 ? rng.int(31, 200) : 0;
      for (const side of [pair.unenforced, pair.enforced]) {
        const turns = turnsOf(side.events);
        const index = selectIndex(turns, turn);
        const message = `seed ${seed}, turn ${turn}`;
        expect(Number.isInteger(index), message).toBe(true);
        expect(index, message).toBeGreaterThanOrEqual(0);
        expect(index, message).toBeLessThanOrEqual(side.events.length - 1);
        expect(index, message).toBe(oracleIndex(turns, turn));
      }
    }
  });

  it('is monotone in the turn and holds the last event from the last turn on', () => {
    const pair = loadRealPair();
    for (const side of [pair.unenforced, pair.enforced]) {
      const turns = turnsOf(side.events);
      const last = lastTurn(side.events);
      let previous = 0;
      for (const turn of range(0, 40)) {
        const index = selectIndex(turns, turn);
        expect(index, `turn ${turn}`).toBeGreaterThanOrEqual(previous);
        previous = index;
        if (turn >= last) {
          expect(index, `turn ${turn}`).toBe(side.events.length - 1);
        }
      }
    }
  });

  it('holds the enforced side at index 19 for turns 17 to 30 while the unenforced side reaches 31 at turn 30', () => {
    const pair = loadRealPair();
    const enforcedTurns = turnsOf(pair.enforced.events);
    const unenforcedTurns = turnsOf(pair.unenforced.events);
    for (const turn of range(17, 30)) {
      expect(selectIndex(enforcedTurns, turn), `turn ${turn}`).toBe(19);
    }
    expect(selectIndex(unenforcedTurns, 30)).toBe(31);
    expect(selectIndex(unenforcedTurns, 29)).toBe(29);
  });
});
