// Tests for pair.ts: Requirements 7.2, 7.11, 7.12, 1.9; design section 12; T5.7.
//
// Conventions fixed by this test (binding for 10.4):
// - idStem(id): string | null. Strips one trailing '-unenforced' or '-enforced'; null if neither.
//   '-unenforced' is checked first, so 'x-unenforced' has stem 'x', never 'x-un'.
// - resolveComparePair(replays: readonly Replay[]): ComparePair, per design section 12.
//   The input holds only successfully loaded replays, in index order. A replay that failed to
//   load is simply absent from the array (the caller keeps only Result.ok values).
// - Unavailable result: { kind: 'unavailable', message: PAIR_UNAVAILABLE_MESSAGE }.
// - Pair result: { kind: 'pair', unenforced: Replay, enforced: Replay } (same object references).
import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import { PAIR_UNAVAILABLE_MESSAGE, idStem, resolveComparePair } from './pair';
import { indexEntries, rawReplay } from './test/replays';
import type { LoadError, Replay, Result } from './types';
import { parseReplay } from './validate';

const ENFORCED = 'poisoned-briefing-enforced';
const UNENFORCED = 'poisoned-briefing-unenforced';
const FORGED = 'forged-identity-refused';

function loadResults(): Result<Replay, LoadError>[] {
  return indexEntries().map((entry) => parseReplay(rawReplay(entry.file), entry.file));
}

function loadReal(): Replay[] {
  const replays: Replay[] = [];
  for (const result of loadResults()) {
    if (!result.ok) {
      throw new Error(result.error.message);
    }
    replays.push(result.value);
  }
  return replays;
}

function byId(replays: readonly Replay[], id: string): Replay {
  const found = replays.find((replay) => replay.meta.id === id);
  if (found === undefined) {
    throw new Error(`real replay not found: ${id}`);
  }
  return found;
}

function clone(replay: Replay): Replay {
  return JSON.parse(JSON.stringify(replay)) as Replay;
}

function variant(replay: Replay, id: string, scenario?: string, enforce?: boolean): Replay {
  const copy = clone(replay);
  copy.meta.id = id;
  if (scenario !== undefined) {
    copy.meta.scenario = scenario;
  }
  if (enforce !== undefined) {
    copy.meta.enforce = enforce;
  }
  return copy;
}

function expectUnavailable(replays: readonly Replay[]): void {
  expect(resolveComparePair(replays)).toEqual({
    kind: 'unavailable',
    message: PAIR_UNAVAILABLE_MESSAGE,
  });
}

describe('idStem', () => {
  it('strips -enforced and -unenforced to the same stem, and gives null without a suffix', () => {
    expect(idStem(ENFORCED)).toBe('poisoned-briefing');
    expect(idStem(UNENFORCED)).toBe('poisoned-briefing');
    expect(idStem(FORGED)).toBeNull();
  });

  it('treats x-unenforced as the unenforced side, never as an enforced x-un', () => {
    expect(idStem('x-unenforced')).toBe('x');
    expect(idStem('x-enforced')).toBe('x');
  });
});

describe('resolveComparePair', () => {
  it('resolves the real index to unenforced (left) and enforced (right)', () => {
    const replays = loadReal();
    const result = resolveComparePair(replays);
    expect(result.kind).toBe('pair');
    if (result.kind === 'pair') {
      expect(result.unenforced.meta.id).toBe(UNENFORCED);
      expect(result.enforced.meta.id).toBe(ENFORCED);
      expect(result.unenforced.meta.enforce).toBe(false);
      expect(result.enforced.meta.enforce).toBe(true);
    }
  });

  it('never pairs forged-identity-refused, alone or next to a complete pair', () => {
    const replays = loadReal();
    const forged = byId(replays, FORGED);
    expectUnavailable([forged]);
    const withPair = resolveComparePair([forged, ...replays.filter((r) => r !== forged)]);
    expect(withPair.kind).toBe('pair');
    if (withPair.kind === 'pair') {
      expect(withPair.enforced.meta.id).not.toBe(FORGED);
      expect(withPair.unenforced.meta.id).not.toBe(FORGED);
    }
  });

  it('is unavailable when the stem matches but meta.scenario differs', () => {
    const replays = loadReal();
    const enforced = byId(replays, ENFORCED);
    const other = variant(byId(replays, UNENFORCED), UNENFORCED, 'another-scenario');
    expectUnavailable([enforced, other]);
  });

  it('is unavailable when one side is duplicated for the same stem', () => {
    const replays = loadReal();
    const enforced = byId(replays, ENFORCED);
    const unenforced = byId(replays, UNENFORCED);
    expectUnavailable([enforced, variant(enforced, ENFORCED), unenforced]);
    expectUnavailable([enforced, unenforced, variant(unenforced, UNENFORCED)]);
  });

  it('is unavailable when the counterpart is missing', () => {
    const replays = loadReal();
    expectUnavailable([byId(replays, ENFORCED)]);
    expectUnavailable([byId(replays, UNENFORCED)]);
    expectUnavailable([byId(replays, ENFORCED), byId(replays, FORGED)]);
  });

  it('does not accept a counterpart whose meta.enforce disagrees with its suffix', () => {
    const replays = loadReal();
    const enforced = byId(replays, ENFORCED);
    const stemmed = variant(enforced, 'p-enforced', undefined, false);
    const partner = variant(byId(replays, UNENFORCED), 'p-unenforced');
    expectUnavailable([stemmed, partner]);
    const badUnenforced = variant(byId(replays, UNENFORCED), 'q-unenforced', undefined, true);
    expectUnavailable([variant(enforced, 'q-enforced'), badUnenforced]);
  });

  it('is unavailable when a pair member failed to load, but not when an unrelated file did', () => {
    const results = loadResults();
    const failure: LoadError = {
      file: './replays/failed.json',
      kind: 'http',
      message: './replays/failed.json: HTTP 500',
      status: 500,
    };
    const loaded = (list: Result<Replay, LoadError>[]): Replay[] =>
      list.flatMap((result) => (result.ok ? [result.value] : []));
    const real = loaded(results);

    const withoutEnforced = results.map((r) =>
      r.ok && r.value.meta.id === ENFORCED ? ({ ok: false, error: failure } as const) : r,
    );
    expectUnavailable(loaded(withoutEnforced));

    const withoutForged = results.map((r) =>
      r.ok && r.value.meta.id === FORGED ? ({ ok: false, error: failure } as const) : r,
    );
    expect(real.length).toBe(results.length);
    expect(resolveComparePair(loaded(withoutForged)).kind).toBe('pair');
  });

  it('carries PAIR_UNAVAILABLE_MESSAGE, a non-empty string, in the unavailable result', () => {
    expect(typeof PAIR_UNAVAILABLE_MESSAGE).toBe('string');
    expect(PAIR_UNAVAILABLE_MESSAGE.length).toBeGreaterThan(0);
    const result = resolveComparePair([]);
    expect(result).toEqual({ kind: 'unavailable', message: PAIR_UNAVAILABLE_MESSAGE });
  });
});

describe('replay format carries no pair field (Requirement 7.12)', () => {
  it('types.ts has no pair field and the real replay metas have no key containing pair', () => {
    const source = readFileSync(new URL('./types.ts', import.meta.url), 'utf8');
    expect(source).not.toMatch(/\bpair\b/i);
    for (const replay of loadReal()) {
      const keys = Object.keys(replay.meta);
      expect(keys.filter((key) => key.toLowerCase().includes('pair'))).toEqual([]);
    }
  });
});
