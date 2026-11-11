// Pure playback reducer; timeline-ui design section 4.
import { DEFAULT_SPEED } from './constants';
import type { Speed } from './constants';

export interface PlaybackState {
  pos: number;
  max: number;
  playing: boolean;
  speed: Speed;
}

export type PlaybackAction =
  | { type: 'play' }
  | { type: 'pause' }
  | { type: 'stepForward' }
  | { type: 'stepBack' }
  | { type: 'setSpeed'; speed: Speed }
  | { type: 'scrub'; value: number }
  | { type: 'tick' };

export function createPlayback(max: number): PlaybackState {
  return { pos: 0, max, playing: false, speed: DEFAULT_SPEED };
}

function settle(s: PlaybackState): PlaybackState {
  return { ...s, playing: s.playing && s.pos < s.max };
}

function clamp(value: number, low: number, high: number): number {
  return Math.min(Math.max(value, low), high);
}

export function playbackReducer(state: PlaybackState, action: PlaybackAction): PlaybackState {
  switch (action.type) {
    case 'play':
      if (state.max === 0) {
        return state;
      }
      if (state.pos >= state.max) {
        return settle({ ...state, pos: 0, playing: true });
      }
      return settle({ ...state, playing: true });
    case 'pause':
      return { ...state, playing: false };
    case 'stepForward':
      return settle({ ...state, pos: Math.min(state.pos + 1, state.max) });
    case 'stepBack':
      return { ...state, pos: Math.max(state.pos - 1, 0) };
    case 'setSpeed':
      return { ...state, speed: action.speed };
    case 'scrub':
      if (!Number.isFinite(action.value)) {
        return state;
      }
      return settle({ ...state, pos: clamp(Math.trunc(action.value), 0, state.max) });
    case 'tick':
      if (!state.playing) {
        return state;
      }
      return settle({ ...state, pos: Math.min(state.pos + 1, state.max) });
  }
}
