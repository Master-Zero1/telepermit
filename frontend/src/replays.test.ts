// Property P5.4: every replay file parses against the TypeScript types; the enforced replay's last non-terminal event is KILLED with reason ALLOWANCE_EXCEEDED, limit 40 and observed 41; the unenforced replay has no KILLED event; removing any required key gives missing_field naming that key. Validates: Requirements 1.7, 10.10.
//
// Field paths follow the convention fixed in validate.test.ts: dotted keys and bracketed
// indices from the document root.
import { describe, expect, it } from 'vitest';
import { indexEntries, rawIndex, rawReplay, replayFiles } from './test/replays';
import type { Replay, ReplayEvent } from './types';
import { parseIndex, parseReplay } from './validate';

const ENFORCED = 'poisoned-briefing-enforced.json';
const UNENFORCED = 'poisoned-briefing-unenforced.json';
const FORGED = 'forged-identity-refused.json';

const PERMIT_KEYS = ['lifetime_s', 'max_steps', 'allowance', 'allowed_actions'];
const TOP_KEYS = ['schema_version', 'meta', 'events'];
const META_KEYS = [
  'id',
  'title',
  'scenario',
  'driver',
  'enforce',
  'harness_cap',
  'task',
  'home_permit',
  'ceilings',
  'tool_costs',
  'document_text',
  'generated_by',
];
const EVENT_KEYS = ['seq', 't', 'type', 'place', 'step', 'spent', 'data'];
const IDENTITY_KEYS = ['agent_id', 'agent_class', 'authority', 'issued_at', 'signature_hex'];

// Required keys under `data`, by event type (CONTRACTS section 6; design section 5).
const DATA_KEYS: Record<string, string[]> = {
  RUN_STARTED: ['scenario', 'driver', 'enforce', 'task', 'identity', 'permit'],
  BORDER_CHECK: [
    'place',
    'via_action',
    'decision',
    'reason',
    'permit_after',
    'narrowed_fields',
    'cost',
    'explain',
  ],
  TOOL_CALL: ['action', 'args', 'cost', 'result'],
  DENIED: ['action', 'reason', 'explain'],
  KILLED: ['reason', 'action', 'limit', 'observed', 'explain'],
  FINISHED: [],
  RUN_ENDED: ['status'],
};

type Path = (string | number)[];

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function clone(value: unknown): unknown {
  return JSON.parse(JSON.stringify(value)) as unknown;
}

function pathString(path: Path): string {
  return path.reduce<string>((text, key) => {
    if (typeof key === 'number') return `${text}[${key}]`;
    return text === '' ? key : `${text}.${key}`;
  }, '');
}

function child(path: Path, keys: string[]): Path[] {
  return keys.map((key) => [...path, key]);
}

function parsed(file: string): Replay {
  const result = parseReplay(rawReplay(file), `./replays/${file}`);
  if (!result.ok) throw new Error(result.error.message);
  return result.value;
}

function eventAt(replay: Replay, position: number): ReplayEvent {
  const event = replay.events[position];
  if (event === undefined) throw new Error(`no event at ${position}`);
  return event;
}

// Required key paths for one raw replay, built from the schema above. Record contents
// that are not fixed keys (tool_call args, tool_costs entries, ceilings entry names) are
// not enumerated; ceilings entry names are read from the document.
function requiredPaths(raw: unknown): Path[] {
  if (!isRecord(raw) || !isRecord(raw.meta) || !Array.isArray(raw.events)) {
    throw new Error('replay does not have the expected top-level shape');
  }
  const paths: Path[] = [
    ...child([], TOP_KEYS),
    ...child(['meta'], META_KEYS),
    ...child(['meta', 'home_permit'], PERMIT_KEYS),
  ];
  const ceilings = raw.meta.ceilings;
  if (!isRecord(ceilings)) throw new Error('meta.ceilings is not an object');
  for (const name of Object.keys(ceilings)) {
    paths.push(...child(['meta', 'ceilings', name], PERMIT_KEYS));
  }
  raw.events.forEach((event: unknown, position: number) => {
    if (!isRecord(event) || typeof event.type !== 'string') {
      throw new Error(`events[${position}] is not an event`);
    }
    const base: Path = ['events', position];
    const dataKeys = DATA_KEYS[event.type];
    if (dataKeys === undefined) throw new Error(`unknown event type ${event.type}`);
    const dataPath: Path = [...base, 'data'];
    paths.push(...child(base, EVENT_KEYS), ...child(dataPath, dataKeys));
    if (event.type === 'RUN_STARTED') {
      paths.push(
        ...child([...dataPath, 'identity'], IDENTITY_KEYS),
        ...child([...dataPath, 'permit'], PERMIT_KEYS),
      );
    }
    if (event.type === 'BORDER_CHECK') {
      paths.push(...child([...dataPath, 'permit_after'], PERMIT_KEYS));
    }
  });
  return paths;
}

function removeKey(root: unknown, path: Path): void {
  let node: unknown = root;
  for (const key of path.slice(0, -1)) {
    if (Array.isArray(node) && typeof key === 'number') {
      node = node[key];
    } else if (isRecord(node) && typeof key === 'string') {
      node = node[key];
    } else {
      throw new Error(`bad test path ${pathString(path)}`);
    }
  }
  const last = path[path.length - 1];
  if (!isRecord(node) || typeof last !== 'string' || !(last in node)) {
    throw new Error(`schema key ${pathString(path)} is absent from the file`);
  }
  delete node[last];
}

function countMissingFieldChecks(file: string): number {
  const raw = rawReplay(file);
  const paths = requiredPaths(raw);
  for (const path of paths) {
    const copy = clone(raw);
    removeKey(copy, path);
    const result = parseReplay(copy, `./replays/${file}`);
    const field = pathString(path);
    expect(result.ok, field).toBe(false);
    if (!result.ok) {
      expect(result.error.kind, field).toBe('missing_field');
      // Removing events[0].type leaves a first event that is no longer RUN_STARTED, but
      // the per-event key check runs before the first-event check (design section 5,
      // check 5 before check 6), so the expected field is still events[0].type.
      expect(result.error.field, field).toBe(field);
    }
  }
  return paths.length;
}

describe('Property P5.4', () => {
  it('parses the real index and every replay it names', () => {
    const index = parseIndex(rawIndex(), './replays/index.json');
    expect(index.ok).toBe(true);
    const entries = indexEntries();
    for (const entry of entries) {
      const result = parseReplay(rawReplay(entry.file), `./replays/${entry.file}`);
      if (!result.ok) throw new Error(result.error.message);
      expect(result.value.meta.id).toBe(entry.id);
      expect(result.value.meta.driver).toBe(entry.driver);
      expect(result.value.meta.enforce).toBe(entry.enforce);
    }
    expect(replayFiles()).toEqual(entries.map((entry) => entry.file).sort());
  });

  it('ends the enforced replay with KILLED ALLOWANCE_EXCEEDED, limit 40, observed 41', () => {
    const replay = parsed(ENFORCED);
    const last = eventAt(replay, replay.events.length - 1);
    expect(last.type).toBe('RUN_ENDED');
    if (last.type !== 'RUN_ENDED') throw new Error('last event is not RUN_ENDED');
    expect(last.data.status).toBe('KILLED');
    const killed = eventAt(replay, replay.events.length - 2);
    if (killed.type !== 'KILLED') throw new Error(`expected KILLED, got ${killed.type}`);
    expect(killed.data.reason).toBe('ALLOWANCE_EXCEEDED');
    expect(killed.data.limit).toBe(40);
    expect(killed.data.observed).toBe(41);
  });

  it('has no KILLED event in the unenforced replay', () => {
    const replay = parsed(UNENFORCED);
    expect(replay.events.some((event) => event.type === 'KILLED')).toBe(false);
    const last = eventAt(replay, replay.events.length - 1);
    if (last.type !== 'RUN_ENDED') throw new Error('last event is not RUN_ENDED');
    expect(last.data.status).toBe('HARNESS_CAP');
  });

  it('still parses the forged-identity replay', () => {
    const replay = parsed(FORGED);
    expect(replay.events).toHaveLength(3);
    const border = eventAt(replay, 1);
    if (border.type !== 'BORDER_CHECK') throw new Error(`expected BORDER_CHECK, got ${border.type}`);
    expect(border.data.decision).toBe('REFUSE');
    expect(border.data.reason).toBe('BAD_SIGNATURE');
    const last = eventAt(replay, 2);
    if (last.type !== 'RUN_ENDED') throw new Error('last event is not RUN_ENDED');
    expect(last.data.status).toBe('REFUSED');
  });

  // Hand count of required-key checks. Shared by all three files (ceilings: library, vault):
  //   top 3 + meta 12 + home_permit 4 + ceilings 2 x 4 = 27.
  // Per event: 7 keys. Data keys: RUN_STARTED 6 + identity 5 + permit 4 = 15;
  //   BORDER_CHECK 8 + permit_after 4 = 12; TOOL_CALL 4; DENIED 3; KILLED 5; RUN_ENDED 1.
  // enforced (20 events: 1 RUN_STARTED, 2 BORDER_CHECK, 13 TOOL_CALL, 2 DENIED, 1 KILLED,
  //   1 RUN_ENDED): 27 + 20 x 7 = 167; data 15 + 24 + 52 + 6 + 5 + 1 = 103; total 270.
  // unenforced (32 events: 1 RUN_STARTED, 1 BORDER_CHECK, 29 TOOL_CALL, 1 RUN_ENDED):
  //   27 + 32 x 7 = 251; data 15 + 12 + 116 + 1 = 144; total 395.
  // forged (3 events: RUN_STARTED, BORDER_CHECK, RUN_ENDED): 27 + 3 x 7 = 48;
  //   data 15 + 12 + 1 = 28; total 76.
  // Sum: 270 + 395 + 76 = 741.
  it('reports missing_field naming the path for every removed required key', () => {
    expect(countMissingFieldChecks(ENFORCED)).toBe(270);
    expect(countMissingFieldChecks(UNENFORCED)).toBe(395);
    expect(countMissingFieldChecks(FORGED)).toBe(76);
  });
});
