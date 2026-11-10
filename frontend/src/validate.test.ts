// Tests for validate.ts. Requirements 1.6, 1.7, 6.14, 10.1; design section 5; T5.1.
//
// FIELD PATH CONVENTION (binding for tasks 4.1, 4.3 and 4.4): dotted keys and bracketed
// indices from the document root, e.g. `schema_version`, `replays[1].file`,
// `meta.home_permit.allowance`, `events[3].data.permit_after.allowance`. The first-event
// rule uses the field `events[0] (RUN_STARTED)`. A non-object document root is reported
// with the empty string '' as its field.
import { describe, expect, it } from 'vitest';
import { indexEntries, rawIndex, rawReplay } from './test/replays';
import type { LoadError, LoadErrorKind, Result } from './types';
import { parseIndex, parseReplay } from './validate';

const INDEX_FILE = './replays/index.json';
const REPLAY_FILE = './replays/poisoned-briefing-enforced.json';
const ENFORCED = 'poisoned-briefing-enforced.json';
const EXPECTED_EVENT_COUNTS = [20, 32, 3];

type Path = (string | number)[];

function clone(value: unknown): unknown {
  return JSON.parse(JSON.stringify(value)) as unknown;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function container(root: unknown, path: Path): Record<string, unknown> | unknown[] {
  let node: unknown = root;
  for (const key of path) {
    if (Array.isArray(node) && typeof key === 'number') {
      node = node[key];
    } else if (isRecord(node) && typeof key === 'string') {
      node = node[key];
    } else {
      throw new Error(`bad test path at ${String(key)}`);
    }
  }
  if (Array.isArray(node) || isRecord(node)) return node;
  throw new Error(`test path ${path.join('.')} does not lead to a container`);
}

function set(root: unknown, path: Path, value: unknown): void {
  const last = path[path.length - 1];
  const parent = container(root, path.slice(0, -1));
  if (Array.isArray(parent) && typeof last === 'number') {
    parent[last] = value;
  } else if (!Array.isArray(parent) && typeof last === 'string') {
    parent[last] = value;
  } else {
    throw new Error('bad final key in set');
  }
}

function del(root: unknown, path: Path): void {
  const last = path[path.length - 1];
  const parent = container(root, path.slice(0, -1));
  if (Array.isArray(parent) && typeof last === 'number') {
    parent.splice(last, 1);
  } else if (!Array.isArray(parent) && typeof last === 'string') {
    if (!(last in parent)) throw new Error(`key ${last} not present`);
    delete parent[last];
  } else {
    throw new Error('bad final key in del');
  }
}

function enforcedCopy(): unknown {
  return clone(rawReplay(ENFORCED));
}

function indexCopy(): unknown {
  return clone(rawIndex());
}

function expectError(
  result: Result<unknown, LoadError>,
  kind: LoadErrorKind,
  field?: string,
  file: string = REPLAY_FILE,
): void {
  if (result.ok) {
    throw new Error(`expected an error of kind ${kind}, but the document parsed`);
  }
  expect(result.error.kind).toBe(kind);
  expect(result.error.file).toBe(file);
  expect(result.error.message).toContain(file);
  if (field !== undefined) expect(result.error.field).toBe(field);
}

describe('validate: real files', () => {
  it('parses the real index in index order', () => {
    const result = parseIndex(rawIndex(), INDEX_FILE);
    if (!result.ok) throw new Error(result.error.message);
    expect(result.value.replays).toHaveLength(3);
    expect(result.value.replays.map((entry) => entry.id)).toEqual(
      indexEntries().map((entry) => entry.id),
    );
  });

  it('parses each of the three real replays', () => {
    const entries = indexEntries();
    expect(entries).toHaveLength(EXPECTED_EVENT_COUNTS.length);
    entries.forEach((entry, position) => {
      const file = `./replays/${entry.file}`;
      const result = parseReplay(rawReplay(entry.file), file);
      if (!result.ok) throw new Error(result.error.message);
      expect(result.value.events).toHaveLength(EXPECTED_EVENT_COUNTS[position] ?? -1);
      expect(result.value.meta.id).toBe(entry.id);
    });
  });
});

describe('validate: schema_version', () => {
  it('rejects schema_version 2 in a replay and in an index', () => {
    const replay = enforcedCopy();
    set(replay, ['schema_version'], 2);
    const replayResult = parseReplay(replay, REPLAY_FILE);
    expectError(replayResult, 'schema_version');
    if (!replayResult.ok) expect(replayResult.error.message).toContain('2');

    const index = indexCopy();
    set(index, ['schema_version'], 2);
    const indexResult = parseIndex(index, INDEX_FILE);
    expectError(indexResult, 'schema_version', undefined, INDEX_FILE);
    if (!indexResult.ok) expect(indexResult.error.message).toContain('2');
  });

  it('reports a missing schema_version as missing_field', () => {
    const replay = enforcedCopy();
    del(replay, ['schema_version']);
    expectError(parseReplay(replay, REPLAY_FILE), 'missing_field', 'schema_version');
  });
});

describe('validate: replay fields', () => {
  it('reports a missing nested meta field with its full path', () => {
    const replay = enforcedCopy();
    del(replay, ['meta', 'home_permit', 'allowance']);
    expectError(parseReplay(replay, REPLAY_FILE), 'missing_field', 'meta.home_permit.allowance');
  });

  it('reports wrong types as invalid_field', () => {
    const meta = enforcedCopy();
    set(meta, ['meta', 'harness_cap'], '30');
    expectError(parseReplay(meta, REPLAY_FILE), 'invalid_field', 'meta.harness_cap');

    const event = enforcedCopy();
    set(event, ['events', 2, 'step'], 'x');
    expectError(parseReplay(event, REPLAY_FILE), 'invalid_field', 'events[2].step');
  });

  it('rejects an unknown driver in a replay and in an index entry', () => {
    const replay = enforcedCopy();
    set(replay, ['meta', 'driver'], 'robot');
    expectError(parseReplay(replay, REPLAY_FILE), 'invalid_field', 'meta.driver');

    const index = indexCopy();
    set(index, ['replays', 0, 'driver'], 'robot');
    expectError(parseIndex(index, INDEX_FILE), 'invalid_field', 'replays[0].driver', INDEX_FILE);
  });

  it('rejects an unknown event type', () => {
    const replay = enforcedCopy();
    set(replay, ['events', 2, 'type'], 'TELEPORT');
    expectError(parseReplay(replay, REPLAY_FILE), 'invalid_field', 'events[2].type');
  });

  it('reports missing nested event data keys', () => {
    const permit = enforcedCopy();
    del(permit, ['events', 3, 'data', 'permit_after', 'allowance']);
    expectError(
      parseReplay(permit, REPLAY_FILE),
      'missing_field',
      'events[3].data.permit_after.allowance',
    );

    const identity = enforcedCopy();
    del(identity, ['events', 0, 'data', 'identity', 'signature_hex']);
    expectError(
      parseReplay(identity, REPLAY_FILE),
      'missing_field',
      'events[0].data.identity.signature_hex',
    );
  });
});

describe('validate: index file names', () => {
  it.each(['../secret.json', 'sub/dir.json', 'https://x.example/a.json', 'C:\\x.json', 'a.txt', ''])(
    'rejects the unsafe file name %j',
    (name) => {
      const index = indexCopy();
      set(index, ['replays', 0, 'file'], name);
      expectError(parseIndex(index, INDEX_FILE), 'invalid_field', 'replays[0].file', INDEX_FILE);
    },
  );
});

describe('validate: event list rules', () => {
  it('requires the first event to be RUN_STARTED', () => {
    const replay = enforcedCopy();
    del(replay, ['events', 0]);
    expectError(parseReplay(replay, REPLAY_FILE), 'missing_field', 'events[0] (RUN_STARTED)');
  });

  it('accepts an empty events array', () => {
    const replay = enforcedCopy();
    set(replay, ['events'], []);
    const result = parseReplay(replay, REPLAY_FILE);
    if (!result.ok) throw new Error(result.error.message);
    expect(result.value.events).toHaveLength(0);
  });
});

describe('validate: non-object documents', () => {
  it.each([[null], [42], ['x'], [[]]])('rejects the root value %j with an empty field', (raw) => {
    expectError(parseReplay(raw, REPLAY_FILE), 'invalid_field', '');
    expectError(parseIndex(raw, INDEX_FILE), 'invalid_field', '', INDEX_FILE);
  });
});
