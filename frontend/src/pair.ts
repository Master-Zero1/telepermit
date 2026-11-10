// Compare pair resolution by id suffix, stem and scenario (design section 12).
import type { Replay } from './types';

const UNENFORCED_SUFFIX = '-unenforced';
const ENFORCED_SUFFIX = '-enforced';

export const PAIR_UNAVAILABLE_MESSAGE =
  'Compare view unavailable: the index needs one "-enforced" and one "-unenforced" replay of the same scenario.';

export type ComparePair =
  | { kind: 'pair'; unenforced: Replay; enforced: Replay }
  | { kind: 'unavailable'; message: string };

export function idStem(id: string): string | null {
  if (id.endsWith(UNENFORCED_SUFFIX)) {
    return id.slice(0, id.length - UNENFORCED_SUFFIX.length);
  }
  if (id.endsWith(ENFORCED_SUFFIX)) {
    return id.slice(0, id.length - ENFORCED_SUFFIX.length);
  }
  return null;
}

interface StemGroup {
  unenforced: Replay[];
  enforced: Replay[];
}

function groupByStem(replays: readonly Replay[]): Map<string, StemGroup> {
  const groups = new Map<string, StemGroup>();
  for (const replay of replays) {
    const stem = idStem(replay.meta.id);
    if (stem === null) {
      continue;
    }
    const isUnenforced = replay.meta.id.endsWith(UNENFORCED_SUFFIX);
    if (replay.meta.enforce === isUnenforced) {
      continue;
    }
    const group = groups.get(stem) ?? { unenforced: [], enforced: [] };
    (isUnenforced ? group.unenforced : group.enforced).push(replay);
    groups.set(stem, group);
  }
  return groups;
}

export function resolveComparePair(replays: readonly Replay[]): ComparePair {
  const pairs: { unenforced: Replay; enforced: Replay }[] = [];
  for (const group of groupByStem(replays).values()) {
    if (group.unenforced.length !== 1 || group.enforced.length !== 1) {
      continue;
    }
    const [unenforced] = group.unenforced;
    const [enforced] = group.enforced;
    if (unenforced.meta.scenario === enforced.meta.scenario) {
      pairs.push({ unenforced, enforced });
    }
  }
  if (pairs.length !== 1) {
    return { kind: 'unavailable', message: PAIR_UNAVAILABLE_MESSAGE };
  }
  return { kind: 'pair', ...pairs[0] };
}
