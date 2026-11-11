// Unit tests for the meters. Requirements 3.6 to 3.10, 3.14, design section 6, T5.4.
import { describe, expect, it } from 'vitest';
import { barPercent, isOver, meterRows } from './meters';
import type { MeterRow } from './meters';
import type { PermitJSON, Replay, ReplayEvent } from './types';
import { rawReplay } from './test/replays';
import { seeded } from './test/seeded';

const HOME: PermitJSON = {
  lifetime_s: 60,
  max_steps: 30,
  allowance: 60,
  allowed_actions: ['go:vault', 'read_document'],
};

const OTHER: PermitJSON = {
  lifetime_s: 10,
  max_steps: 5,
  allowance: 40,
  allowed_actions: ['read_document'],
};

const KEYS = ['allowance', 'steps', 'lifetime'];
const LABELS = ['allowance (teleclicks)', 'steps', 'lifetime (s)'];

function eventWith(spent: number, step: number, t: number): ReplayEvent {
  return {
    seq: step,
    t,
    place: 'library',
    step,
    spent,
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
      permit: OTHER,
    },
  };
}

function load(file: string): Replay {
  return rawReplay(file) as Replay;
}

function rowsAt(replay: Replay, index: number): MeterRow[] {
  return meterRows(replay.meta.home_permit, replay.events[index]);
}

function pairs(rows: MeterRow[]): string[] {
  return rows.map((row) => `${row.observed}/${row.limit}`);
}

const ENFORCED = load('poisoned-briefing-enforced.json');
const UNENFORCED = load('poisoned-briefing-unenforced.json');
const FORGED = load('forged-identity-refused.json');

describe('barPercent and isOver', () => {
  it('limit 0 gives 0 or 100 without dividing by zero', () => {
    expect(barPercent(0, 0)).toBe(0);
    expect(barPercent(1, 0)).toBe(100);
    expect(barPercent(-1, 0)).toBe(0);
  });

  it('equal to the limit is 100 and not over; one over is 100 and over', () => {
    expect(barPercent(60, 60)).toBe(100);
    expect(isOver(60, 60)).toBe(false);
    expect(barPercent(61, 60)).toBe(100);
    expect(isOver(61, 60)).toBe(true);
  });

  it('clamps to the range 0 to 100 and scales in between', () => {
    expect(barPercent(120, 60)).toBe(100);
    expect(barPercent(-5, 60)).toBe(0);
    expect(barPercent(30, 60)).toBe(50);
    expect(barPercent(38, 60)).toBeCloseTo(63.333, 3);
  });
});

describe('meterRows', () => {
  it('returns three rows in order with the labels and the home limits', () => {
    const rows = meterRows(HOME, eventWith(5, 4, 3));
    expect(rows.map((row) => row.key)).toEqual(KEYS);
    expect(rows.map((row) => row.label)).toEqual(LABELS);
    expect(rows.map((row) => row.limit)).toEqual([60, 30, 60]);
    expect(rows.map((row) => row.observed)).toEqual([5, 4, 3]);
  });

  it('enforced replay matches the worked table and is never over', () => {
    const expected: Record<number, string[]> = {
      0: ['0/60', '0/30', '0/60'],
      2: ['1/60', '1/30', '1/60'],
      3: ['2/60', '2/30', '2/60'],
      17: ['38/60', '16/30', '16/60'],
      18: ['38/60', '17/30', '17/60'],
      19: ['38/60', '17/30', '17/60'],
    };
    for (const [index, cells] of Object.entries(expected)) {
      expect(pairs(rowsAt(ENFORCED, Number(index)))).toEqual(cells);
    }
    ENFORCED.events.forEach((_event, index) => {
      expect(rowsAt(ENFORCED, index).some((row) => row.over)).toBe(false);
    });
  });

  it('unenforced replay matches the worked table', () => {
    const expected: Record<number, string[]> = {
      3: ['22/60', '3/30', '3/60'],
      10: ['60/60', '10/30', '10/60'],
      11: ['63/60', '11/30', '11/60'],
      30: ['120/60', '30/30', '30/60'],
      31: ['120/60', '30/30', '30/60'],
    };
    for (const [index, cells] of Object.entries(expected)) {
      expect(pairs(rowsAt(UNENFORCED, Number(index)))).toEqual(cells);
    }
    expect(rowsAt(UNENFORCED, 3).some((row) => row.over)).toBe(false);
    expect(rowsAt(UNENFORCED, 10).some((row) => row.over)).toBe(false);
    expect(rowsAt(UNENFORCED, 11)[0].over).toBe(true);
    expect(rowsAt(UNENFORCED, 30).map((row) => row.over)).toEqual([true, false, false]);
    expect(rowsAt(UNENFORCED, 31).map((row) => row.over)).toEqual([true, false, false]);
  });

  it('unenforced allowance row is over exactly for indices from 11', () => {
    UNENFORCED.events.forEach((_event, index) => {
      expect(rowsAt(UNENFORCED, index)[0].over).toBe(index >= 11);
    });
  });

  it('forged replay index 1 is 0/60, 0/30, 0/60 with nothing over', () => {
    const rows = rowsAt(FORGED, 1);
    expect(pairs(rows)).toEqual(['0/60', '0/30', '0/60']);
    expect(rows.some((row) => row.over)).toBe(false);
  });

  it('limits stay at the home permit for the whole enforced replay', () => {
    ENFORCED.events.forEach((_event, index) => {
      expect(rowsAt(ENFORCED, index).map((row) => row.limit)).toEqual([60, 30, 60]);
    });
  });
});

// Property P5.3: for any observed value and any limit, the bar percentage is observed / limit * 100 clamped to [0, 100] (0 or 100 when the limit is 0, without dividing by zero), and the over-limit flag is true exactly when observed > limit; the meter limits are the home permit and identical for every event of a replay. Validates: Requirements 3.8, 3.9, 3.10, 3.14, 10.12.
describe('Property P5.3', () => {
  it('computes the clamped percentage for 200 seeded observed and limit pairs', () => {
    for (let seed = 1; seed <= 200; seed += 1) {
      const rng = seeded(seed);
      const limit = rng.int(0, 2) === 0 ? 0 : rng.int(1, 200);
      const observed = rng.pick([
        limit,
        limit + 1,
        limit - 1,
        0,
        rng.int(-50, -1),
        rng.next() * 3 * (limit + 1) - 10,
        rng.int(0, 1000),
      ]);
      const percent = barPercent(observed, limit);
      const message = `seed ${seed}: observed ${observed}, limit ${limit}`;
      expect(Number.isFinite(percent), message).toBe(true);
      expect(percent >= 0 && percent <= 100, message).toBe(true);
      if (limit === 0) {
        expect(percent, message).toBe(observed > 0 ? 100 : 0);
      } else {
        expect(percent, message).toBeCloseTo(Math.min(Math.max((observed / limit) * 100, 0), 100), 9);
      }
      expect(isOver(observed, limit), message).toBe(observed > limit);
    }
  });

  it('reports over exactly when observed > limit at the boundaries', () => {
    for (let limit = 0; limit <= 50; limit += 1) {
      expect(isOver(limit, limit), `limit ${limit}`).toBe(false);
      expect(isOver(limit + 1, limit), `limit ${limit}`).toBe(true);
      expect(isOver(limit - 1, limit), `limit ${limit}`).toBe(false);
      expect(barPercent(limit, limit), `limit ${limit}`).toBe(limit > 0 ? 100 : 0);
    }
  });

  it('uses the home permit limits for every event of every real replay', () => {
    for (const replay of [ENFORCED, UNENFORCED, FORGED]) {
      const home = replay.meta.home_permit;
      replay.events.forEach((event, index) => {
        const rows = rowsAt(replay, index);
        expect(rows.map((row) => row.limit)).toEqual([
          home.allowance,
          home.max_steps,
          home.lifetime_s,
        ]);
        expect(rows.map((row) => row.observed)).toEqual([event.spent, event.step, event.t]);
        for (const row of rows) {
          expect(row.percent).toBe(barPercent(row.observed, row.limit));
          expect(row.over).toBe(isOver(row.observed, row.limit));
        }
      });
    }
  });
});
