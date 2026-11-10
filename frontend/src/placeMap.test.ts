// Unit tests for tokenPlace. Requirements 2.2, 2.3, 2.8, design section 7, T5.3.
import { describe, expect, it } from 'vitest';
import { tokenPlace } from './placeMap';
import type {
  BorderDecision,
  PermitJSON,
  Replay,
  ReplayEvent,
  RunStatus,
} from './types';
import { rawReplay } from './test/replays';

const PERMIT: PermitJSON = {
  lifetime_s: 60,
  max_steps: 30,
  allowance: 60,
  allowed_actions: ['go:vault', 'read_document'],
};

function started(seq: number, place: string): ReplayEvent {
  return {
    seq,
    t: seq,
    place,
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

function border(
  seq: number,
  place: string,
  dataPlace: string,
  viaAction: string | null,
  decision: BorderDecision,
): ReplayEvent {
  return {
    seq,
    t: seq,
    place,
    step: 0,
    spent: 0,
    type: 'BORDER_CHECK',
    data: {
      place: dataPlace,
      via_action: viaAction,
      decision,
      reason: decision === 'REFUSE' ? 'BAD_SIGNATURE' : 'OK',
      permit_after: PERMIT,
      narrowed_fields: [],
      cost: 0,
      explain: 'synthetic',
    },
  };
}

function ended(seq: number, place: string, status: RunStatus): ReplayEvent {
  return {
    seq,
    t: seq,
    place,
    step: 0,
    spent: 0,
    type: 'RUN_ENDED',
    data: { status },
  };
}

function places(events: readonly ReplayEvent[]): (string | null)[] {
  return events.map((_, i) => tokenPlace(events, i));
}

function repeat(place: string, count: number): string[] {
  return Array.from({ length: count }, () => place);
}

const enforced = (rawReplay('poisoned-briefing-enforced.json') as Replay).events;
const unenforced = (rawReplay('poisoned-briefing-unenforced.json') as Replay).events;
const forged = (rawReplay('forged-identity-refused.json') as Replay).events;

describe('tokenPlace', () => {
  it('follows the enforced replay from library to vault at the go border', () => {
    const expected = [...repeat('library', 3), ...repeat('vault', 17)];
    expect(enforced).toHaveLength(20);
    expect(places(enforced)).toEqual(expected);
  });

  it('follows the unenforced replay from library to vault at the go border', () => {
    const expected = [...repeat('library', 2), ...repeat('vault', 30)];
    expect(unenforced).toHaveLength(32);
    expect(places(unenforced)).toEqual(expected);
  });

  it('hides the token after a spawn refusal even though every event says library', () => {
    expect(forged.every((event) => event.place === 'library')).toBe(true);
    expect(places(forged)).toEqual(['library', null, null]);
  });

  it('moves the token only where the place changes', () => {
    const moves: number[] = [];
    for (let i = 1; i < enforced.length; i += 1) {
      if (tokenPlace(enforced, i) !== tokenPlace(enforced, i - 1)) {
        moves.push(i);
      }
    }
    expect(moves).toEqual([3]);
  });

  it('keeps the agent in place when a go border refuses it', () => {
    const events = [
      started(0, 'library'),
      border(1, 'library', 'library', null, 'ADMIT'),
      border(2, 'library', 'vault', 'go:vault', 'REFUSE'),
    ];
    expect(tokenPlace(events, 2)).toBe('library');
  });

  it('keeps the token hidden for every event after a spawn refusal', () => {
    const events = [
      started(0, 'library'),
      border(1, 'library', 'library', null, 'REFUSE'),
      ended(2, 'library', 'REFUSED'),
    ];
    expect(places(events)).toEqual(['library', null, null]);
  });
});
