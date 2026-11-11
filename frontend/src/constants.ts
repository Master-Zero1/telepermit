// Named constants for the timeline UI; timeline-ui design section 2 (CONTRACTS section 9 replay paths).
import type { Driver } from './types';

export const SCHEMA_VERSION = 1;
export const REPLAY_BASE = './replays/';
export const INDEX_URL = './replays/index.json';
export const TICK_MS = 800; // base interval; real interval = TICK_MS / speed
export const SPEEDS = [1, 2, 4] as const;
export type Speed = (typeof SPEEDS)[number];
export const DEFAULT_SPEED: Speed = 1;
export const NARROW_QUERY = '(max-width: 767.98px)';
export const REDUCED_MOTION_QUERY = '(prefers-reduced-motion: reduce)';
export const SAFE_REPLAY_FILE = /^[A-Za-z0-9][A-Za-z0-9._-]*\.json$/;
export const HONESTY_NOTE =
  'Permits do not stop an injection that stays inside the permit boundary. ' +
  'Recorded runs are labelled scripted or live LLM.';
export const SUBTITLE = 'Permits and places, 1994. Limits enforced by the runtime, not the prompt.';
export const DRIVER_LABEL: Record<Driver, string> = { scripted: 'scripted agent', llm: 'live LLM' };
export const PLACES = ['library', 'vault'] as const;
