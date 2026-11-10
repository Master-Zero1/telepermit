// Unit tests for borderBadge. Requirements 2.4 to 2.7, 2.9 to 2.11, design section 8, T5.3.
import { describe, expect, it } from 'vitest';
import { borderBadge } from './badge';
import type { BorderBadge } from './badge';
import type { BorderDecision, PermitJSON, Replay, ReplayEvent } from './types';
import { rawReplay } from './test/replays';

const PERMIT: PermitJSON = {
  lifetime_s: 60,
  max_steps: 30,
  allowance: 60,
  allowed_actions: ['go:vault', 'read_document'],
};

const NO_CHECK: BorderBadge = { text: 'NO BORDER CHECK YET', reason: null, tone: 'none' };
const ADMITTED: BorderBadge = { text: 'ADMITTED', reason: null, tone: 'green' };
const IMPOSED: BorderBadge = {
  text: 'ADMITTED UNDER IMPOSED PERMIT',
  reason: null,
  tone: 'orange',
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

function border(
  seq: number,
  viaAction: string | null,
  decision: BorderDecision,
  reason: string,
): ReplayEvent {
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
      decision,
      reason,
      permit_after: PERMIT,
      narrowed_fields: [],
      cost: 0,
      explain: 'synthetic',
    },
  };
}

function badges(events: readonly ReplayEvent[], from: number, to: number): BorderBadge[] {
  return events.slice(from, to + 1).map((_, offset) => borderBadge(events, from + offset));
}

function repeat(badge: BorderBadge, count: number): BorderBadge[] {
  return Array.from({ length: count }, () => badge);
}

const enforced = (rawReplay('poisoned-briefing-enforced.json') as Replay).events;
const unenforced = (rawReplay('poisoned-briefing-unenforced.json') as Replay).events;
const forged = (rawReplay('forged-identity-refused.json') as Replay).events;

describe('borderBadge', () => {
  it('shows no border check yet before the first BORDER_CHECK', () => {
    expect(borderBadge(enforced, 0)).toEqual(NO_CHECK);
    expect(borderBadge(unenforced, 0)).toEqual(NO_CHECK);
    expect(borderBadge(unenforced, 1)).toEqual(NO_CHECK);
  });

  it('shows ADMITTED with no reason for an ADMIT with reason OK', () => {
    expect(borderBadge(enforced, 1)).toEqual(ADMITTED);
    expect(borderBadge(enforced, 2)).toEqual(ADMITTED);
  });

  it('shows the imposed-permit badge from the go border to the end of the run', () => {
    expect(enforced).toHaveLength(20);
    expect(badges(enforced, 3, 19)).toEqual(repeat(IMPOSED, 17));
  });

  it('shows ADMITTED with the UNENFORCED reason in the unenforced replay', () => {
    const expected: BorderBadge = { text: 'ADMITTED', reason: 'UNENFORCED', tone: 'green' };
    expect(unenforced).toHaveLength(32);
    expect(badges(unenforced, 2, 31)).toEqual(repeat(expected, 30));
  });

  it('shows REFUSED with the reason code after a spawn refusal', () => {
    const expected: BorderBadge = { text: 'REFUSED', reason: 'BAD_SIGNATURE', tone: 'red' };
    expect(borderBadge(forged, 0)).toEqual(NO_CHECK);
    expect(borderBadge(forged, 1)).toEqual(expected);
    expect(borderBadge(forged, 2)).toEqual(expected);
  });

  it('uses the latest BORDER_CHECK at or before the index', () => {
    const events = [
      started(0),
      border(1, null, 'ADMIT_IMPOSED', 'OK'),
      border(2, 'go:library', 'REFUSE', 'EXCEEDS_CEILING'),
    ];
    expect(borderBadge(events, 1)).toEqual(IMPOSED);
    expect(borderBadge(events, 2)).toEqual({
      text: 'REFUSED',
      reason: 'EXCEEDS_CEILING',
      tone: 'red',
    });
  });

  it('always states the decision in text for every index of every real replay', () => {
    const texts = ['NO BORDER CHECK YET', 'ADMITTED', 'ADMITTED UNDER IMPOSED PERMIT', 'REFUSED'];
    const textForTone = { green: 'ADMITTED', orange: 'ADMITTED UNDER IMPOSED PERMIT', red: 'REFUSED' };
    for (const events of [enforced, unenforced, forged]) {
      for (let i = 0; i < events.length; i += 1) {
        const badge = borderBadge(events, i);
        expect(texts).toContain(badge.text);
        if (badge.tone !== 'none') {
          expect(badge.text).not.toBe('');
          expect(badge.text).toBe(textForTone[badge.tone]);
        }
      }
    }
  });
});
