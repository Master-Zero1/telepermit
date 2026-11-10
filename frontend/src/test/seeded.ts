// Test-only Seeded_Generator (mulberry32). Never imported by app code.

export interface Seeded {
  next(): number;
  int(min: number, max: number): number;
  pick<T>(items: readonly T[]): T;
}

export function seeded(seed: number): Seeded {
  let state = seed >>> 0;

  function next(): number {
    state = (state + 0x6d2b79f5) >>> 0;
    let t = state;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  }

  function int(min: number, max: number): number {
    if (!Number.isInteger(min) || !Number.isInteger(max)) {
      throw new Error(`int(${min}, ${max}): bounds must be integers`);
    }
    if (max < min) {
      throw new Error(`int(${min}, ${max}): max is below min`);
    }
    return min + Math.floor(next() * (max - min + 1));
  }

  function pick<T>(items: readonly T[]): T {
    if (items.length === 0) {
      throw new Error('pick: empty array');
    }
    const item = items[int(0, items.length - 1)];
    if (item === undefined) {
      throw new Error('pick: index out of range');
    }
    return item;
  }

  return { next, int, pick };
}
