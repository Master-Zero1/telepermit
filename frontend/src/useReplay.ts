// React hook driving the playback reducer with a timer; timeline-ui design section 4.
import { useEffect, useMemo, useReducer } from 'react';
import { TICK_MS } from './constants';
import type { Speed } from './constants';
import { createPlayback, playbackReducer } from './playback';
import type { PlaybackState } from './playback';

export interface ReplayControls {
  state: PlaybackState;
  play(): void;
  pause(): void;
  stepForward(): void;
  stepBack(): void;
  setSpeed(speed: Speed): void;
  scrub(value: number): void;
}

// The owning component is remounted by `key` when the replay changes, so `max` is read only at
// mount and no reset action exists. Playback starts paused: no timer exists until play.
export function useReplay(max: number): ReplayControls {
  const [state, dispatch] = useReducer(playbackReducer, max, createPlayback);

  useEffect(() => {
    if (!state.playing) {
      return undefined;
    }
    const id = window.setInterval(() => dispatch({ type: 'tick' }), TICK_MS / state.speed);
    return () => window.clearInterval(id);
  }, [state.playing, state.speed]);

  const controls = useMemo(
    () => ({
      play: () => dispatch({ type: 'play' }),
      pause: () => dispatch({ type: 'pause' }),
      stepForward: () => dispatch({ type: 'stepForward' }),
      stepBack: () => dispatch({ type: 'stepBack' }),
      setSpeed: (speed: Speed) => dispatch({ type: 'setSpeed', speed }),
      scrub: (value: number) => dispatch({ type: 'scrub', value }),
    }),
    [],
  );

  return { state, ...controls };
}
