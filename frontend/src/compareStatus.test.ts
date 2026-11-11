// Regression test for FIX: the title cursor kept blinking in compare mode after the enforced
// side was KILLED, because App passed ['ALIVE'] for compare mode. Requirement 9.8; design 10, 14.
//
// Conventions fixed by this test (binding for the fix):
//   compareStatus.ts exports compareStatuses(unenforced, enforced, turn): StateStatus[]
//   returning [status of the unenforced side, status of the enforced side] at the event each
//   side selects for the shared turn (selectIndex(turnsOf(events), turn), then statusView).
//   An empty event list counts as 'ALIVE'.
//   App no longer hard-codes ['ALIVE'] and passes onStatuses to CompareView.
import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import { compareStatuses } from './compareStatus';
import { cursorBlinks } from './present';
import { rawReplay } from './test/replays';
import type { Replay } from './types';

const unenforced = (rawReplay('poisoned-briefing-unenforced.json') as Replay).events;
const enforced = (rawReplay('poisoned-briefing-enforced.json') as Replay).events;

function source(relative: string): string {
  return readFileSync(new URL(relative, import.meta.url), 'utf8');
}

describe('compareStatuses', () => {
  it('reports both sides ALIVE at turn 0 and turn 16, so the cursor blinks', () => {
    for (const turn of [0, 16]) {
      const statuses = compareStatuses(unenforced, enforced, turn);
      expect(statuses, `turn ${turn}`).toEqual(['ALIVE', 'ALIVE']);
      expect(cursorBlinks(statuses), `turn ${turn}`).toBe(true);
    }
  });

  it('reports the enforced side KILLED from turn 17, so the cursor stops', () => {
    for (const turn of [17, 29]) {
      const statuses = compareStatuses(unenforced, enforced, turn);
      expect(statuses, `turn ${turn}`).toEqual(['ALIVE', 'KILLED']);
      expect(cursorBlinks(statuses), `turn ${turn}`).toBe(false);
    }
  });

  it('reports HARNESS_CAP and KILLED at the last turn', () => {
    const statuses = compareStatuses(unenforced, enforced, 30);
    expect(statuses).toEqual(['HARNESS_CAP', 'KILLED']);
    expect(cursorBlinks(statuses)).toBe(false);
  });

  it('treats an empty side as ALIVE', () => {
    expect(compareStatuses([], enforced, 0)).toEqual(['ALIVE', 'ALIVE']);
  });
});

describe('App uses the compare statuses for the cursor', () => {
  const app = source('./App.tsx');

  it('no longer hard-codes ALIVE for compare mode', () => {
    expect(app).not.toMatch(/\[\s*'ALIVE'\s*\]/);
  });

  it('passes onStatuses to CompareView', () => {
    expect(app).toMatch(/<CompareView[^>]*\bonStatuses\b/s);
  });
});