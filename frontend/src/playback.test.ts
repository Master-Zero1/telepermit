// Playback reducer unit tests. Requirements 6.1 to 6.8, 6.10 to 6.14; design section 4; T5.2.
import { describe, expect, it } from 'vitest';
import { createPlayback, playbackReducer } from './playback';
import type { PlaybackAction, PlaybackState } from './playback';
import { seeded } from './test/seeded';
import type { Seeded } from './test/seeded';
import { SPEEDS } from './constants';

function run(state: PlaybackState, ...actions: PlaybackAction[]): PlaybackState {
  return actions.reduce(playbackReducer, state);
}

describe('playbackReducer', () => {
  it('createPlayback starts paused at 0 with speed 1', () => {
    expect(createPlayback(19)).toEqual({ pos: 0, max: 19, playing: false, speed: 1 });
  });

  it('play then pause toggles playing and keeps pos', () => {
    const s = createPlayback(19);
    const playing = run(s, { type: 'play' });
    expect(playing.playing).toBe(true);
    expect(playing.pos).toBe(0);
    const paused = run(playing, { type: 'pause' });
    expect(paused.playing).toBe(false);
    expect(paused.pos).toBe(0);
  });

  it('stepForward advances by 1 and stays at max (6.10)', () => {
    expect(run(createPlayback(19), { type: 'stepForward' }).pos).toBe(1);
    const atMax: PlaybackState = { pos: 19, max: 19, playing: false, speed: 1 };
    expect(run(atMax, { type: 'stepForward' }).pos).toBe(19);
  });

  it('stepBack goes back by 1, stays at 0 (6.11), keeps playing', () => {
    const at3: PlaybackState = { pos: 3, max: 19, playing: false, speed: 1 };
    expect(run(at3, { type: 'stepBack' }).pos).toBe(2);
    expect(run(createPlayback(19), { type: 'stepBack' }).pos).toBe(0);
    const playing: PlaybackState = { ...at3, playing: true };
    const back = run(playing, { type: 'stepBack' });
    expect(back.pos).toBe(2);
    expect(back.playing).toBe(true);
  });

  it('setSpeed changes only speed (6.7)', () => {
    const playing: PlaybackState = { pos: 5, max: 19, playing: true, speed: 1 };
    expect(run(playing, { type: 'setSpeed', speed: 4 })).toEqual({
      pos: 5,
      max: 19,
      playing: true,
      speed: 4,
    });
    const paused = run(createPlayback(19), { type: 'setSpeed', speed: 2 });
    expect(paused.playing).toBe(false);
    expect(paused.speed).toBe(2);
  });

  it('scrub truncates, clamps and ignores non-finite values (6.13)', () => {
    const s = createPlayback(19);
    expect(run(s, { type: 'scrub', value: 7 }).pos).toBe(7);
    expect(run(s, { type: 'scrub', value: 7.9 }).pos).toBe(7);
    expect(run(s, { type: 'scrub', value: -3 }).pos).toBe(0);
    expect(run(s, { type: 'scrub', value: 99 }).pos).toBe(19);
    const at4: PlaybackState = { pos: 4, max: 19, playing: false, speed: 1 };
    for (const value of [Number.NaN, Number.POSITIVE_INFINITY, Number.NEGATIVE_INFINITY]) {
      expect(run(at4, { type: 'scrub', value }).pos).toBe(4);
    }
  });

  it('scrub to max while playing stops playback', () => {
    const playing: PlaybackState = { pos: 2, max: 19, playing: true, speed: 1 };
    const s = run(playing, { type: 'scrub', value: 19 });
    expect(s.pos).toBe(19);
    expect(s.playing).toBe(false);
  });

  it('tick is a no-op when paused and advances by 1 when playing', () => {
    const paused: PlaybackState = { pos: 2, max: 19, playing: false, speed: 1 };
    expect(run(paused, { type: 'tick' })).toEqual(paused);
    const playing: PlaybackState = { ...paused, playing: true };
    expect(run(playing, { type: 'tick' }).pos).toBe(3);
  });

  it('ticking to the last event stops playback (6.12)', () => {
    const s = run(
      createPlayback(3),
      { type: 'play' },
      { type: 'tick' },
      { type: 'tick' },
      { type: 'tick' },
    );
    expect(s.pos).toBe(3);
    expect(s.playing).toBe(false);
    expect(run(s, { type: 'tick' }).pos).toBe(3);
  });

  it('play at the last event restarts at 0 and plays', () => {
    const atEnd: PlaybackState = { pos: 19, max: 19, playing: false, speed: 1 };
    const s = run(atEnd, { type: 'play' });
    expect(s.pos).toBe(0);
    expect(s.playing).toBe(true);
  });

  it('empty replay ignores every action (6.14)', () => {
    const actions: PlaybackAction[] = [
      { type: 'play' },
      { type: 'pause' },
      { type: 'stepForward' },
      { type: 'stepBack' },
      { type: 'setSpeed', speed: 2 },
      { type: 'scrub', value: 5 },
      { type: 'tick' },
    ];
    for (const action of actions) {
      const s = run(createPlayback(0), action);
      expect(s.pos).toBe(0);
      expect(s.playing).toBe(false);
    }
  });

  it('does not mutate its input state', () => {
    const state: PlaybackState = { pos: 2, max: 19, playing: true, speed: 2 };
    const copy = { ...state };
    const actions: PlaybackAction[] = [
      { type: 'play' },
      { type: 'pause' },
      { type: 'stepForward' },
      { type: 'stepBack' },
      { type: 'setSpeed', speed: 4 },
      { type: 'scrub', value: 9 },
      { type: 'tick' },
    ];
    for (const action of actions) {
      playbackReducer(state, action);
      expect(state).toEqual(copy);
    }
  });
});

// Property P5.2: under any sequence of play, pause, step forward, step back, speed and scrub actions (and timer ticks), the playback position stays within [0, max], the speed stays one of 1, 2, 4, and playing implies pos < max. Validates: Requirements 6.9, 6.10, 6.11, 6.13, 6.14, 10.11.
describe('Property P5.2', () => {
  function randomScrubValue(rng: Seeded, max: number): number {
    const kind = rng.int(0, 2);
    if (kind === 0) {
      return rng.int(-5, max + 5);
    }
    if (kind === 1) {
      return rng.next() * (max + 10) - 5;
    }
    return rng.pick([Number.NaN, Number.POSITIVE_INFINITY, Number.NEGATIVE_INFINITY]);
  }

  function randomAction(rng: Seeded, max: number): PlaybackAction {
    switch (rng.int(0, 6)) {
      case 0:
        return { type: 'play' };
      case 1:
        return { type: 'pause' };
      case 2:
        return { type: 'stepForward' };
      case 3:
        return { type: 'stepBack' };
      case 4:
        return { type: 'setSpeed', speed: rng.pick(SPEEDS) };
      case 5:
        return { type: 'scrub', value: randomScrubValue(rng, max) };
      default:
        return { type: 'tick' };
    }
  }

  function checkInvariants(state: PlaybackState, max: number): void {
    expect(Number.isInteger(state.pos)).toBe(true);
    expect(state.pos).toBeGreaterThanOrEqual(0);
    expect(state.pos).toBeLessThanOrEqual(max);
    expect(state.max).toBe(max);
    expect((SPEEDS as readonly number[]).includes(state.speed)).toBe(true);
    expect(!state.playing || state.pos < state.max).toBe(true);
  }

  it('keeps the position in range for 200 seeded action sequences', () => {
    for (let seed = 1; seed <= 200; seed += 1) {
      const rng = seeded(seed);
      const n = rng.int(0, 40);
      const max = Math.max(n - 1, 0);
      let state = createPlayback(max);
      checkInvariants(state, max);
      const length = rng.int(1, 100);
      for (let i = 0; i < length; i += 1) {
        const action = randomAction(rng, max);
        state = playbackReducer(state, action);
        expect(Number.isInteger(state.pos), `seed ${seed}`).toBe(true);
        expect(state.pos >= 0 && state.pos <= max, `seed ${seed}`).toBe(true);
        checkInvariants(state, max);
      }
    }
  });

  it('keeps an empty replay at position 0 under any sequence', () => {
    for (let seed = 1; seed <= 200; seed += 1) {
      const rng = seeded(seed);
      let state = createPlayback(0);
      const length = rng.int(1, 100);
      for (let i = 0; i < length; i += 1) {
        state = playbackReducer(state, randomAction(rng, 0));
        expect(state.pos, `seed ${seed}`).toBe(0);
        expect(state.playing, `seed ${seed}`).toBe(false);
      }
    }
  });

  it('matches a clamp oracle for scrub', () => {
    for (let seed = 1; seed <= 200; seed += 1) {
      const rng = seeded(seed);
      const max = rng.int(0, 40);
      const value = rng.next() * 140 - 50;
      const result = playbackReducer(createPlayback(max), { type: 'scrub', value });
      const expected = Math.min(Math.max(Math.trunc(value), 0), max);
      expect(result.pos, `seed ${seed}`).toBe(expected);
    }
  });
});
