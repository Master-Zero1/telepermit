// Unit tests for permitView and latestNarrowed. Requirements 4.1 to 4.7, design section 9, T5.5.
// Value convention: numbers print as String(n) (60.0 from JSON prints '60'); the allowed_actions
// value is the state permit's actions joined with ', ' in state order.
import { describe, expect, it } from 'vitest';
import { latestNarrowed, permitView } from './permitView';
import type { PermitView } from './permitView';
import { reduceEvents } from './reduce';
import type { PermitField, PermitJSON, Replay } from './types';
import { rawReplay } from './test/replays';

const enforced = rawReplay('poisoned-briefing-enforced.json') as Replay;
const unenforced = rawReplay('poisoned-briefing-unenforced.json') as Replay;
const forged = rawReplay('forged-identity-refused.json') as Replay;

const ALL_FIELDS: PermitField[] = ['lifetime_s', 'max_steps', 'allowance', 'allowed_actions'];
const HOME_ACTIONS = [
  'export_records',
  'go:library',
  'go:vault',
  'read_document',
  'read_records',
  'search_archive',
];

const HOME: PermitJSON = {
  lifetime_s: 60,
  max_steps: 30,
  allowance: 60,
  allowed_actions: HOME_ACTIONS,
};

function viewAt(replay: Replay, index: number): PermitView {
  return permitView(
    reduceEvents(replay.events.slice(0, index + 1)).permit,
    replay.meta.home_permit,
    latestNarrowed(replay.events, index),
  );
}

function narrowedFields(view: PermitView): PermitField[] {
  return view.fields.filter((f) => f.narrowed).map((f) => f.field);
}

function removedActions(view: PermitView): string[] {
  return view.actions.filter((a) => a.removed).map((a) => a.name);
}

describe('latestNarrowed', () => {
  it('is empty before the vault border in the enforced replay', () => {
    expect(latestNarrowed(enforced.events, 0)).toEqual([]);
    expect(latestNarrowed(enforced.events, 1)).toEqual([]);
    expect(latestNarrowed(enforced.events, 2)).toEqual([]);
  });

  it('returns the vault narrowed fields from the go border to the end', () => {
    const expected: PermitField[] = ['allowance', 'allowed_actions'];
    expect(latestNarrowed(enforced.events, 3)).toEqual(expected);
    expect(latestNarrowed(enforced.events, 19)).toEqual(expected);
  });

  it('is empty at every index of the unenforced and forged replays', () => {
    for (const replay of [unenforced, forged]) {
      for (let i = 0; i < replay.events.length; i += 1) {
        expect(latestNarrowed(replay.events, i)).toEqual([]);
      }
    }
  });
});

describe('permitView', () => {
  const expectedFields = [
    { field: 'lifetime_s', value: '60', narrowed: false },
    { field: 'max_steps', value: '30', narrowed: false },
    { field: 'allowance', value: '40', narrowed: true },
    { field: 'allowed_actions', value: 'go:library, read_records', narrowed: true },
  ];

  it('shows the imposed allowance 40 and four struck actions after the vault border', () => {
    for (const index of [3, 19]) {
      const view = viewAt(enforced, index);
      expect(view.fields).toEqual(expectedFields);
      expect(view.actions.map((a) => a.name)).toEqual(HOME_ACTIONS);
      expect(removedActions(view)).toEqual([
        'export_records',
        'go:vault',
        'read_document',
        'search_archive',
      ]);
      expect(view.actions.filter((a) => !a.removed).map((a) => a.name)).toEqual([
        'go:library',
        'read_records',
      ]);
    }
  });

  it('shows the home permit with nothing narrowed or removed before the vault border', () => {
    const view = viewAt(enforced, 2);
    expect(narrowedFields(view)).toEqual([]);
    expect(removedActions(view)).toEqual([]);
    expect(view.fields[2]).toEqual({ field: 'allowance', value: '60', narrowed: false });
  });

  it('gives no highlights for a plain ADMIT', () => {
    expect(narrowedFields(viewAt(enforced, 1))).toEqual([]);
  });

  it('shows nothing narrowed or removed at any index of the unenforced replay', () => {
    for (let i = 0; i < unenforced.events.length; i += 1) {
      const view = viewAt(unenforced, i);
      expect(narrowedFields(view)).toEqual([]);
      expect(removedActions(view)).toEqual([]);
      expect(view.fields[2]).toEqual({ field: 'allowance', value: '60', narrowed: false });
    }
  });

  it('marks all four fields narrowed and prints their values', () => {
    const state: PermitJSON = {
      lifetime_s: 30,
      max_steps: 10,
      allowance: 5,
      allowed_actions: ['read_records'],
    };
    const view = permitView(state, HOME, ALL_FIELDS);
    expect(view.fields.map((f) => f.field)).toEqual(ALL_FIELDS);
    expect(view.fields.map((f) => f.narrowed)).toEqual([true, true, true, true]);
    expect(view.fields.map((f) => f.value)).toEqual(['30', '10', '5', 'read_records']);
  });

  it('appends a state action that is not a home action and keeps home order', () => {
    const state: PermitJSON = { ...HOME, allowed_actions: ['read_records', 'teleport'] };
    const view = permitView(state, HOME, []);
    expect(view.actions[view.actions.length - 1]).toEqual({ name: 'teleport', removed: false });
    expect(view.actions.slice(0, HOME_ACTIONS.length).map((a) => a.name)).toEqual(HOME_ACTIONS);
  });

  it('does not mutate its inputs', () => {
    const state: PermitJSON = {
      lifetime_s: 60,
      max_steps: 30,
      allowance: 40,
      allowed_actions: ['go:library', 'read_records'],
    };
    const home: PermitJSON = { ...HOME, allowed_actions: [...HOME_ACTIONS] };
    const narrowed: PermitField[] = ['allowance', 'allowed_actions'];
    const stateCopy = JSON.parse(JSON.stringify(state)) as PermitJSON;
    const homeCopy = JSON.parse(JSON.stringify(home)) as PermitJSON;
    const narrowedCopy = [...narrowed];
    permitView(state, home, narrowed);
    expect(state).toEqual(stateCopy);
    expect(home).toEqual(homeCopy);
    expect(narrowed).toEqual(narrowedCopy);
  });
});
