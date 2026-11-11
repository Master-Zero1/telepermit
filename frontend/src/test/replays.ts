// Test-only reader for frontend/public/replays. Never imported by app code.
import { readdirSync, readFileSync } from 'node:fs';

const REPLAY_DIR = new URL('../../public/replays/', import.meta.url);
const INDEX_FILE = 'index.json';

export interface RawIndexEntry {
  id: string;
  file: string;
  driver: string;
  enforce: boolean;
}

export function readJson(file: string): unknown {
  const text = readFileSync(new URL(file, REPLAY_DIR), 'utf8');
  return JSON.parse(text) as unknown;
}

export function rawIndex(): unknown {
  return readJson(INDEX_FILE);
}

export function rawReplay(file: string): unknown {
  return readJson(file);
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function toEntry(value: unknown, position: number): RawIndexEntry {
  if (
    !isRecord(value) ||
    typeof value.id !== 'string' ||
    typeof value.file !== 'string' ||
    typeof value.driver !== 'string' ||
    typeof value.enforce !== 'boolean'
  ) {
    throw new Error(`${INDEX_FILE}: replays[${position}] is not a valid entry`);
  }
  return { id: value.id, file: value.file, driver: value.driver, enforce: value.enforce };
}

export function indexEntries(): RawIndexEntry[] {
  const index = rawIndex();
  if (!isRecord(index) || !Array.isArray(index.replays)) {
    throw new Error(`${INDEX_FILE}: missing replays array`);
  }
  return index.replays.map((entry: unknown, position: number) => toEntry(entry, position));
}

export function replayFiles(): string[] {
  return readdirSync(REPLAY_DIR)
    .filter((name) => name.endsWith('.json') && name !== INDEX_FILE)
    .sort();
}
