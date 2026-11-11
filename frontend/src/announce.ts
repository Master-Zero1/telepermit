// Playback announcements for the single-mode live region (timeline-ui design section 15).
import type { PlaybackState } from './playback';

export const ANNOUNCE_PLAYING = 'Playing';
export const ANNOUNCE_PAUSED = 'Paused';
export const ANNOUNCE_END = 'End of replay';

export function playbackAnnouncement(prev: PlaybackState, next: PlaybackState): string | null {
  if (!prev.playing && next.playing) {
    return ANNOUNCE_PLAYING;
  }
  if (prev.playing && !next.playing) {
    return next.pos >= next.max ? ANNOUNCE_END : ANNOUNCE_PAUSED;
  }
  return null;
}

export function composeLive(message: string, announcement: string | null): string {
  return announcement === null ? message : `${announcement}. ${message}`;
}
