// Requirements 6.2, 6.3, 6.12, 6.17; design section 15; task 11 owner additions.
//
// Conventions fixed by this test (binding for 11.1):
//   announce.ts is a new pure module exporting:
//     ANNOUNCE_PLAYING = 'Playing'
//     ANNOUNCE_PAUSED = 'Paused'
//     ANNOUNCE_END = 'End of replay'
//     playbackAnnouncement(prev, next): string | null
//       not playing -> playing                         => 'Playing'
//       playing -> not playing, next.pos >= next.max   => 'End of replay'
//       playing -> not playing, next.pos <  next.max   => 'Paused'
//       anything else (speed change, step while paused,
//       tick while playing)                            => null
//     composeLive(message, announcement)
//       announcement === null ? message : `${announcement}. ${message}`
//   App owns the playback state, so App computes the announcement. There is exactly
//   one aria-live region per mode: StatusLine (single mode, enabled via RunPanel
//   `announce`) and CompareView (compare mode). App has no region of its own.
import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import {
  ANNOUNCE_END,
  ANNOUNCE_PAUSED,
  ANNOUNCE_PLAYING,
  composeLive,
  playbackAnnouncement,
} from './announce';
import { createPlayback, playbackReducer } from './playback';
import type { PlaybackState } from './playback';

function playing(max: number, pos: number): PlaybackState {
  return { ...createPlayback(max), pos, playing: true };
}

function source(relative: string): string {
  return readFileSync(new URL(relative, import.meta.url), 'utf8');
}

function count(text: string, pattern: RegExp): number {
  return (text.match(pattern) ?? []).length;
}

describe('playbackAnnouncement', () => {
  it('announces Playing on play from paused', () => {
    const prev = createPlayback(5);
    const next = playbackReducer(prev, { type: 'play' });
    expect(next.playing).toBe(true);
    expect(playbackAnnouncement(prev, next)).toBe(ANNOUNCE_PLAYING);
    expect(ANNOUNCE_PLAYING).toBe('Playing');
  });

  it('announces Paused on pause mid-replay', () => {
    const prev = playing(5, 2);
    const next = playbackReducer(prev, { type: 'pause' });
    expect(playbackAnnouncement(prev, next)).toBe(ANNOUNCE_PAUSED);
    expect(ANNOUNCE_PAUSED).toBe('Paused');
  });

  it('announces End of replay only on the transition to the last event', () => {
    let state = playbackReducer(createPlayback(3), { type: 'play' });
    let announced: Array<string | null> = [];
    while (state.playing) {
      const next = playbackReducer(state, { type: 'tick' });
      announced = [...announced, playbackAnnouncement(state, next)];
      state = next;
    }
    expect(state.pos).toBe(3);
    expect(announced).toEqual([null, null, ANNOUNCE_END]);
    expect(ANNOUNCE_END).toBe('End of replay');
    const after = playbackReducer(state, { type: 'tick' });
    expect(playbackAnnouncement(state, after)).toBeNull();
  });

  it('returns null for a tick while playing mid-replay', () => {
    const prev = playing(5, 1);
    const next = playbackReducer(prev, { type: 'tick' });
    expect(playbackAnnouncement(prev, next)).toBeNull();
  });

  it('returns null for setSpeed while playing', () => {
    const prev = playing(5, 1);
    const next = playbackReducer(prev, { type: 'setSpeed', speed: 4 });
    expect(next.speed).toBe(4);
    expect(playbackAnnouncement(prev, next)).toBeNull();
  });

  it('returns null for stepForward while paused', () => {
    const prev = createPlayback(5);
    const next = playbackReducer(prev, { type: 'stepForward' });
    expect(playbackAnnouncement(prev, next)).toBeNull();
  });

  it('returns null for play on an empty replay', () => {
    const prev = createPlayback(0);
    const next = playbackReducer(prev, { type: 'play' });
    expect(next.playing).toBe(false);
    expect(playbackAnnouncement(prev, next)).toBeNull();
  });
});

describe('composeLive', () => {
  it('returns the message unchanged without an announcement', () => {
    expect(composeLive('Event 1 of 20: RUN_STARTED', null)).toBe('Event 1 of 20: RUN_STARTED');
  });

  it('prefixes the announcement to the message', () => {
    expect(composeLive('Event 20 of 20: RUN_ENDED KILLED', 'End of replay')).toBe(
      'End of replay. Event 20 of 20: RUN_ENDED KILLED',
    );
  });
});

describe('one live region per mode (owner choice 2)', () => {
  const statusLine = source('./components/StatusLine.tsx');
  const compareView = source('./components/CompareView.tsx');
  const app = source('./App.tsx');

  it('StatusLine and CompareView each contain exactly one aria-live region', () => {
    expect(count(statusLine, /aria-live=/g)).toBe(1);
    expect(count(compareView, /aria-live=/g)).toBe(1);
  });

  it('App owns no aria-live region of its own', () => {
    expect(count(app, /aria-live=/g)).toBe(0);
  });

  it('CompareView renders RunPanel without an announce prop', () => {
    expect(count(compareView, /<RunPanel[^>]*\bannounce\b/gs)).toBe(0);
  });

  it('App passes announce to RunPanel and renders CompareView', () => {
    expect(app).toMatch(/<RunPanel[^>]*\bannounce\b/s);
    expect(app).toMatch(/<CompareView\b/);
  });

  it('App imports from ./announce', () => {
    expect(app).toMatch(/from\s+['"]\.\/announce['"]/);
  });
});
