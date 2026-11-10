// Runtime validation of replay and index documents; timeline-ui design section 5, CONTRACTS sections 6 and 9.
import { SAFE_REPLAY_FILE, SCHEMA_VERSION } from './constants';
import type { LoadError, LoadErrorKind, Replay, ReplayIndex, Result } from './types';

type Checker = (value: unknown, path: string, file: string) => LoadError | null;
type Spec = readonly [key: string, check: Checker];

const DRIVERS = ['scripted', 'llm'];
const EVENT_TYPES = [
  'RUN_STARTED',
  'BORDER_CHECK',
  'TOOL_CALL',
  'DENIED',
  'KILLED',
  'FINISHED',
  'RUN_ENDED',
];
const DECISIONS = ['ADMIT', 'ADMIT_IMPOSED', 'REFUSE'];
const PERMIT_FIELDS = ['lifetime_s', 'max_steps', 'allowance', 'allowed_actions'];
const DENIED_REASONS = ['NOT_IN_PERMIT', 'NOT_IN_PLACE'];
const KILLED_REASONS = ['LIFETIME_EXCEEDED', 'STEPS_EXCEEDED', 'ALLOWANCE_EXCEEDED'];
const RUN_STATUSES = ['FINISHED', 'KILLED', 'REFUSED', 'HARNESS_CAP', 'ERROR'];

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function fieldPath(base: string, key: string): string {
  return base === '' ? key : `${base}.${key}`;
}

function indexPath(base: string, position: number): string {
  return `${base}[${position}]`;
}

function fail(file: string, kind: LoadErrorKind, field: string, cause: string): LoadError {
  const where = field === '' ? '' : `${field}: `;
  return { file, kind, field, message: `${file}: ${where}${cause}` };
}

function invalid(file: string, path: string, expected: string): LoadError {
  return fail(file, 'invalid_field', path, `expected ${expected}`);
}

const isString: Checker = (value, path, file) =>
  typeof value === 'string' ? null : invalid(file, path, 'a string');

const isNumber: Checker = (value, path, file) =>
  typeof value === 'number' ? null : invalid(file, path, 'a number');

const isBoolean: Checker = (value, path, file) =>
  typeof value === 'boolean' ? null : invalid(file, path, 'a boolean');

const isObject: Checker = (value, path, file) =>
  isRecord(value) ? null : invalid(file, path, 'an object');

const isNullableString: Checker = (value, path, file) =>
  value === null || typeof value === 'string' ? null : invalid(file, path, 'a string or null');

function oneOf(allowed: string[]): Checker {
  return (value, path, file) =>
    typeof value === 'string' && allowed.includes(value)
      ? null
      : invalid(file, path, `one of ${allowed.join(', ')}`);
}

function arrayOf(item: Checker): Checker {
  return (value, path, file) => {
    if (!Array.isArray(value)) return invalid(file, path, 'an array');
    for (const [position, element] of (value as unknown[]).entries()) {
      const error = item(element, indexPath(path, position), file);
      if (error !== null) return error;
    }
    return null;
  };
}

function recordOf(item: Checker): Checker {
  return (value, path, file) => {
    if (!isRecord(value)) return invalid(file, path, 'an object');
    for (const [key, element] of Object.entries(value)) {
      const error = item(element, fieldPath(path, key), file);
      if (error !== null) return error;
    }
    return null;
  };
}

// Presence of every key is checked first (in order), then the type of each key.
function checkObject(value: unknown, path: string, file: string, specs: Spec[]): LoadError | null {
  if (!isRecord(value)) return invalid(file, path, 'an object');
  for (const [key] of specs) {
    if (!(key in value)) {
      return fail(file, 'missing_field', fieldPath(path, key), 'required key is missing');
    }
  }
  for (const [key, check] of specs) {
    const error = check(value[key], fieldPath(path, key), file);
    if (error !== null) return error;
  }
  return null;
}

function objectOf(specs: Spec[]): Checker {
  return (value, path, file) => checkObject(value, path, file, specs);
}

const PERMIT_SPECS: Spec[] = [
  ['lifetime_s', isNumber],
  ['max_steps', isNumber],
  ['allowance', isNumber],
  ['allowed_actions', arrayOf(isString)],
];
const checkPermit = objectOf(PERMIT_SPECS);

const IDENTITY_SPECS: Spec[] = [
  ['agent_id', isString],
  ['agent_class', isString],
  ['authority', isString],
  ['issued_at', isNumber],
  ['signature_hex', isString],
];

const DATA_SPECS: Record<string, Spec[]> = {
  RUN_STARTED: [
    ['scenario', isString],
    ['driver', oneOf(DRIVERS)],
    ['enforce', isBoolean],
    ['task', isString],
    ['identity', objectOf(IDENTITY_SPECS)],
    ['permit', checkPermit],
  ],
  BORDER_CHECK: [
    ['place', isString],
    ['via_action', isNullableString],
    ['decision', oneOf(DECISIONS)],
    ['reason', isString],
    ['permit_after', checkPermit],
    ['narrowed_fields', arrayOf(oneOf(PERMIT_FIELDS))],
    ['cost', isNumber],
    ['explain', isString],
  ],
  TOOL_CALL: [
    ['action', isString],
    ['args', recordOf(isString)],
    ['cost', isNumber],
    ['result', isString],
  ],
  DENIED: [
    ['action', isString],
    ['reason', oneOf(DENIED_REASONS)],
    ['explain', isString],
  ],
  KILLED: [
    ['reason', oneOf(KILLED_REASONS)],
    ['action', isString],
    ['limit', isNumber],
    ['observed', isNumber],
    ['explain', isString],
  ],
  FINISHED: [],
  RUN_ENDED: [['status', oneOf(RUN_STATUSES)]],
};

const EVENT_SPECS: Spec[] = [
  ['seq', isNumber],
  ['t', isNumber],
  ['type', oneOf(EVENT_TYPES)],
  ['place', isString],
  ['step', isNumber],
  ['spent', isNumber],
  ['data', isObject],
];

const META_SPECS: Spec[] = [
  ['id', isString],
  ['title', isString],
  ['scenario', isString],
  ['driver', oneOf(DRIVERS)],
  ['enforce', isBoolean],
  ['harness_cap', isNumber],
  ['task', isString],
  ['home_permit', checkPermit],
  ['ceilings', recordOf(checkPermit)],
  ['tool_costs', recordOf(isNumber)],
  ['document_text', isString],
  ['generated_by', isString],
];

const INDEX_ENTRY_SPECS: Spec[] = [
  ['id', isString],
  ['title', isString],
  ['file', checkFileName],
  ['driver', oneOf(DRIVERS)],
  ['enforce', isBoolean],
];

function checkFileName(value: unknown, path: string, file: string): LoadError | null {
  const error = isString(value, path, file);
  if (error !== null) return error;
  return SAFE_REPLAY_FILE.test(String(value)) ? null : invalid(file, path, 'a safe .json file name');
}

function checkEvent(value: unknown, path: string, file: string): LoadError | null {
  const error = checkObject(value, path, file, EVENT_SPECS);
  if (error !== null || !isRecord(value)) return error;
  const specs = DATA_SPECS[String(value.type)] ?? [];
  return checkObject(value.data, fieldPath(path, 'data'), file, specs);
}

function checkSchemaVersion(root: Record<string, unknown>, file: string): LoadError | null {
  if (!('schema_version' in root)) {
    return fail(file, 'missing_field', 'schema_version', 'required key is missing');
  }
  const found = root.schema_version;
  if (found === SCHEMA_VERSION) return null;
  return fail(
    file,
    'schema_version',
    'schema_version',
    `unsupported schema_version ${String(found)}, expected ${SCHEMA_VERSION}`,
  );
}

function checkRoot(raw: unknown, file: string, specs: Spec[]): LoadError | null {
  if (!isRecord(raw)) return invalid(file, '', 'an object');
  return checkSchemaVersion(raw, file) ?? checkObject(raw, '', file, specs);
}

function checkFirstEvent(events: unknown[], file: string): LoadError | null {
  const first = events[0];
  if (events.length === 0 || (isRecord(first) && first.type === 'RUN_STARTED')) return null;
  return fail(file, 'missing_field', 'events[0] (RUN_STARTED)', 'first event must be RUN_STARTED');
}

export function parseIndex(raw: unknown, file: string): Result<ReplayIndex, LoadError> {
  const specs: Spec[] = [['replays', arrayOf(objectOf(INDEX_ENTRY_SPECS))]];
  const error = checkRoot(raw, file, specs);
  return error === null ? { ok: true, value: raw as ReplayIndex } : { ok: false, error };
}

export function parseReplay(raw: unknown, file: string): Result<Replay, LoadError> {
  const specs: Spec[] = [
    ['meta', objectOf(META_SPECS)],
    ['events', arrayOf(checkEvent)],
  ];
  const error = checkRoot(raw, file, specs);
  if (error !== null) return { ok: false, error };
  const replay = raw as Replay;
  const firstError = checkFirstEvent(replay.events, file);
  return firstError === null ? { ok: true, value: replay } : { ok: false, error: firstError };
}
