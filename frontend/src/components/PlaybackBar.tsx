// Playback bar (timeline-ui design sections 13 and 15).
import type { ChangeEvent } from 'react';
import { SPEEDS } from '../constants';
import type { Speed } from '../constants';
import type { PlaybackState } from '../playback';

export interface PlaybackBarProps {
  state: PlaybackState;
  label: string;
  onPlay: () => void;
  onPause: () => void;
  onStepForward: () => void;
  onStepBack: () => void;
  onSpeed: (speed: Speed) => void;
  onScrub: (value: number) => void;
}

export function PlaybackBar({
  state,
  label,
  onPlay,
  onPause,
  onStepForward,
  onStepBack,
  onSpeed,
  onScrub,
}: PlaybackBarProps) {
  return (
    <nav className="playback-bar" aria-label="Playback">
      <button type="button" aria-label="Step back" onClick={onStepBack}>
        ◀
      </button>
      <button
        type="button"
        aria-label={state.playing ? 'Pause' : 'Play'}
        onClick={state.playing ? onPause : onPlay}
      >
        {state.playing ? '‖' : '▶'}
      </button>
      <button type="button" aria-label="Step forward" onClick={onStepForward}>
        ▸
      </button>
      <div className="speed-buttons">
        {SPEEDS.map((speed) => (
          <button
            key={speed}
            type="button"
            aria-pressed={state.speed === speed}
            onClick={() => onSpeed(speed)}
          >
            {state.speed === speed ? `[${speed}×]` : `${speed}×`}
          </button>
        ))}
      </div>
      <input
        type="range"
        min={0}
        max={state.max}
        value={state.pos}
        aria-label="Scrub"
        aria-valuetext={label}
        onChange={(e: ChangeEvent<HTMLInputElement>) => onScrub(Number(e.target.value))}
      />
      <span>{label}</span>
    </nav>
  );
}