// Fetch and validate replay files through an injected fetch; timeline-ui design section 5, CONTRACTS sections 6 and 9.
import { INDEX_URL, REPLAY_BASE, SAFE_REPLAY_FILE } from './constants';
import type { LoadError, LoadErrorKind, Replay, ReplayIndex, ReplayIndexEntry, Result } from './types';
import { parseIndex, parseReplay } from './validate';

export type FetchLike = (
  url: string,
) => Promise<{ ok: boolean; status: number; text(): Promise<string> }>;

function loadError(url: string, kind: LoadErrorKind, cause: string, status?: number): LoadError {
  const error: LoadError = { file: url, kind, message: `${url}: ${cause}` };
  return status === undefined ? error : { ...error, status };
}

function reason(error: unknown): string {
  return error instanceof Error ? error.message : 'unknown error';
}

async function fetchJson(fetchFn: FetchLike, url: string): Promise<Result<unknown, LoadError>> {
  let response: Awaited<ReturnType<FetchLike>>;
  try {
    response = await fetchFn(url);
  } catch (error) {
    return { ok: false, error: loadError(url, 'network', `network error: ${reason(error)}`) };
  }
  if (!response.ok) {
    const cause = `HTTP status ${response.status}`;
    return { ok: false, error: loadError(url, 'http', cause, response.status) };
  }
  try {
    return { ok: true, value: JSON.parse(await response.text()) as unknown };
  } catch (error) {
    return { ok: false, error: loadError(url, 'invalid_json', `not valid JSON: ${reason(error)}`) };
  }
}

export async function loadIndex(fetchFn: FetchLike): Promise<Result<ReplayIndex, LoadError>> {
  const body = await fetchJson(fetchFn, INDEX_URL);
  return body.ok ? parseIndex(body.value, INDEX_URL) : body;
}

export async function loadReplay(
  fetchFn: FetchLike,
  entry: ReplayIndexEntry,
): Promise<Result<Replay, LoadError>> {
  const url = `${REPLAY_BASE}${entry.file}`;
  if (!SAFE_REPLAY_FILE.test(entry.file)) {
    const error = loadError(url, 'invalid_field', 'file name is not a safe .json file name');
    return { ok: false, error: { ...error, field: 'file' } };
  }
  const body = await fetchJson(fetchFn, url);
  return body.ok ? parseReplay(body.value, url) : body;
}
