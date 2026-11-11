// Tests for loader.ts. Requirements 1.1 to 1.7, 1.9, 10.1; design section 5 and 'Loading
// strategy'; T5.1.
//
// CONVENTIONS (binding for task 4.4): `error.file` is the requested URL and `error.message`
// contains it. fetch rejection -> 'network'; `ok: false` -> 'http' with `error.status`; a body
// that is not JSON -> 'invalid_json'; validation errors pass through with `file` = the URL.
// An index entry whose `file` fails SAFE_REPLAY_FILE is rejected without calling fetch.
import { describe, expect, it } from 'vitest';
import { INDEX_URL, REPLAY_BASE } from './constants';
import { loadIndex, loadReplay } from './loader';
import type { FetchLike } from './loader';
import { indexEntries, rawIndex, rawReplay } from './test/replays';
import type { RawIndexEntry } from './test/replays';
import type { LoadError, LoadErrorKind, ReplayIndexEntry, Result } from './types';

const ENFORCED = 'poisoned-briefing-enforced.json';
const ENFORCED_URL = `${REPLAY_BASE}${ENFORCED}`;

type Route = { status: number; body: string } | Error;

function stubFetch(routes: Record<string, Route>): { fetchFn: FetchLike; calls: string[] } {
  const calls: string[] = [];
  const fetchFn: FetchLike = async (url) => {
    calls.push(url);
    const route = routes[url] ?? { status: 404, body: '' };
    if (route instanceof Error) throw route;
    return {
      ok: route.status >= 200 && route.status < 300,
      status: route.status,
      text: async () => route.body,
    };
  };
  return { fetchFn, calls };
}

function okRoute(body: unknown): Route {
  return { status: 200, body: JSON.stringify(body) };
}

function realRoutes(): Record<string, Route> {
  const routes: Record<string, Route> = { [INDEX_URL]: okRoute(rawIndex()) };
  for (const entry of indexEntries()) {
    routes[`${REPLAY_BASE}${entry.file}`] = okRoute(rawReplay(entry.file));
  }
  return routes;
}

function toEntry(raw: RawIndexEntry): ReplayIndexEntry {
  return {
    id: raw.id,
    title: raw.id,
    file: raw.file,
    driver: raw.driver === 'llm' ? 'llm' : 'scripted',
    enforce: raw.enforce,
  };
}

function enforcedEntry(): ReplayIndexEntry {
  const found = indexEntries().find((entry) => entry.file === ENFORCED);
  if (found === undefined) throw new Error(`${ENFORCED} missing from the real index`);
  return toEntry(found);
}

function clone(value: unknown): unknown {
  return JSON.parse(JSON.stringify(value)) as unknown;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function field(node: unknown, key: string): Record<string, unknown> {
  if (!isRecord(node)) throw new Error(`test document has no object at ${key}`);
  const child = node[key];
  if (!isRecord(child)) throw new Error(`test document has no object at ${key}`);
  return child;
}

function expectError(
  result: Result<unknown, LoadError>,
  kind: LoadErrorKind,
  file: string,
  fieldPath?: string,
): LoadError {
  if (result.ok) {
    throw new Error(`expected an error of kind ${kind}, but the load succeeded`);
  }
  expect(result.error.kind).toBe(kind);
  expect(result.error.file).toBe(file);
  expect(result.error.message).toContain(file);
  if (fieldPath !== undefined) expect(result.error.field).toBe(fieldPath);
  return result.error;
}

describe('loader', () => {
  it('requests only the index URL and loads three entries', async () => {
    const { fetchFn, calls } = stubFetch(realRoutes());
    const result = await loadIndex(fetchFn);
    if (!result.ok) throw new Error(result.error.message);
    expect(calls).toEqual([INDEX_URL]);
    expect(result.value.replays).toHaveLength(3);
  });

  it('loads every indexed replay and requests no other URL', async () => {
    const { fetchFn, calls } = stubFetch(realRoutes());
    for (const raw of indexEntries()) {
      const before = calls.length;
      const result = await loadReplay(fetchFn, toEntry(raw));
      if (!result.ok) throw new Error(result.error.message);
      expect(calls.slice(before)).toEqual([`${REPLAY_BASE}${raw.file}`]);
    }
    expect(calls).toEqual(indexEntries().map((entry) => `${REPLAY_BASE}${entry.file}`));
  });

  it('reports a rejected fetch as a network error naming the file', async () => {
    const { fetchFn } = stubFetch({ [INDEX_URL]: new Error('offline') });
    expectError(await loadIndex(fetchFn), 'network', INDEX_URL);
  });

  it('reports http failures with the status for index and replay', async () => {
    const missing = stubFetch({ [INDEX_URL]: { status: 404, body: '' } });
    const indexError = expectError(await loadIndex(missing.fetchFn), 'http', INDEX_URL);
    expect(indexError.status).toBe(404);
    expect(indexError.message).toContain('404');

    const broken = stubFetch({ [ENFORCED_URL]: { status: 500, body: '' } });
    const replayError = expectError(
      await loadReplay(broken.fetchFn, enforcedEntry()),
      'http',
      ENFORCED_URL,
    );
    expect(replayError.status).toBe(500);
    expect(replayError.message).toContain('500');
  });

  it('reports a body that is not JSON as invalid_json', async () => {
    const { fetchFn } = stubFetch({ [INDEX_URL]: { status: 200, body: '{not json' } });
    expectError(await loadIndex(fetchFn), 'invalid_json', INDEX_URL);
  });

  it('passes a schema_version error through with the replay URL', async () => {
    const doc = clone(rawReplay(ENFORCED));
    if (!isRecord(doc)) throw new Error('replay is not an object');
    doc.schema_version = 2;
    const { fetchFn } = stubFetch({ [ENFORCED_URL]: okRoute(doc) });
    expectError(await loadReplay(fetchFn, enforcedEntry()), 'schema_version', ENFORCED_URL);
  });

  it('passes a missing_field error through with the replay URL', async () => {
    const doc = clone(rawReplay(ENFORCED));
    delete field(field(doc, 'meta'), 'home_permit').allowance;
    const { fetchFn } = stubFetch({ [ENFORCED_URL]: okRoute(doc) });
    expectError(
      await loadReplay(fetchFn, enforcedEntry()),
      'missing_field',
      ENFORCED_URL,
      'meta.home_permit.allowance',
    );
  });

  it('rejects an unsafe file name without calling fetch', async () => {
    const { fetchFn, calls } = stubFetch(realRoutes());
    const entry: ReplayIndexEntry = {
      id: 'x',
      title: 'x',
      file: '../secret.json',
      driver: 'scripted',
      enforce: true,
    };
    const result = await loadReplay(fetchFn, entry);
    if (result.ok) throw new Error('expected the unsafe file name to be rejected');
    expect(result.error.kind).toBe('invalid_field');
    expect(result.error.field).toBe('file');
    expect(calls).toEqual([]);
  });

  it('isolates a failing replay from the others (Requirement 1.9)', async () => {
    const routes = realRoutes();
    const unenforced = indexEntries().find((entry) => !entry.enforce);
    if (unenforced === undefined) throw new Error('no unenforced replay in the real index');
    const failingUrl = `${REPLAY_BASE}${unenforced.file}`;
    routes[failingUrl] = { status: 500, body: '' };
    const { fetchFn } = stubFetch(routes);
    const results = await Promise.all(
      indexEntries().map((raw) => loadReplay(fetchFn, toEntry(raw))),
    );
    expect(results.map((result) => result.ok)).toEqual(
      indexEntries().map((raw) => raw.file !== unenforced.file),
    );
    const failed = results.find((result) => !result.ok);
    if (failed === undefined || failed.ok) throw new Error('expected one failed load');
    expect(failed.error.kind).toBe('http');
    expect(failed.error.status).toBe(500);
    expect(failed.error.file).toBe(failingUrl);
  });

  it('loads a replay whose events list is empty', async () => {
    const doc = clone(rawReplay(ENFORCED));
    if (!isRecord(doc)) throw new Error('replay is not an object');
    doc.events = [];
    const { fetchFn } = stubFetch({ [ENFORCED_URL]: okRoute(doc) });
    const result = await loadReplay(fetchFn, enforcedEntry());
    if (!result.ok) throw new Error(result.error.message);
    expect(result.value.events).toHaveLength(0);
  });
});
