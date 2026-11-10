// Replay and state types; CONTRACTS sections 6 and 9, timeline-ui design section 1.
export type Driver = 'scripted' | 'llm';
export type PermitField = 'lifetime_s' | 'max_steps' | 'allowance' | 'allowed_actions';
export type BorderDecision = 'ADMIT' | 'ADMIT_IMPOSED' | 'REFUSE';
export type DeniedReason = 'NOT_IN_PERMIT' | 'NOT_IN_PLACE';
export type KilledReason = 'LIFETIME_EXCEEDED' | 'STEPS_EXCEEDED' | 'ALLOWANCE_EXCEEDED';
export type RunStatus = 'FINISHED' | 'KILLED' | 'REFUSED' | 'HARNESS_CAP' | 'ERROR';
export type StateStatus = 'ALIVE' | RunStatus;

export interface PermitJSON {
  lifetime_s: number;
  max_steps: number;
  allowance: number;
  allowed_actions: string[];
}

export interface IdentityJSON {
  agent_id: string;
  agent_class: string;
  authority: string;
  issued_at: number;
  signature_hex: string;
}

export interface RunStartedData {
  scenario: string;
  driver: Driver;
  enforce: boolean;
  task: string;
  identity: IdentityJSON;
  permit: PermitJSON;
}
export interface BorderCheckData {
  place: string;
  via_action: string | null; // "go:<p>", or null at spawn
  decision: BorderDecision;
  reason: string; // OK, UNENFORCED, BAD_SIGNATURE, UNTRUSTED_AUTHORITY, CLASS_NOT_ALLOWED, EXCEEDS_CEILING
  permit_after: PermitJSON;
  narrowed_fields: PermitField[];
  cost: number;
  explain: string;
}
export interface ToolCallData {
  action: string;
  args: Record<string, string>;
  cost: number;
  result: string;
}
export interface DeniedData {
  action: string;
  reason: DeniedReason;
  explain: string;
}
export interface KilledData {
  reason: KilledReason;
  action: string;
  limit: number;
  observed: number;
  explain: string;
}
export type FinishedData = Record<string, never>;
export interface RunEndedData {
  status: RunStatus;
}

interface EventBase {
  seq: number;
  t: number; // clock time; born time is 0.0
  place: string; // snapshot AFTER the transition
  step: number;
  spent: number;
}
export interface RunStartedEvent extends EventBase {
  type: 'RUN_STARTED';
  data: RunStartedData;
}
export interface BorderCheckEvent extends EventBase {
  type: 'BORDER_CHECK';
  data: BorderCheckData;
}
export interface ToolCallEvent extends EventBase {
  type: 'TOOL_CALL';
  data: ToolCallData;
}
export interface DeniedEvent extends EventBase {
  type: 'DENIED';
  data: DeniedData;
}
export interface KilledEvent extends EventBase {
  type: 'KILLED';
  data: KilledData;
}
export interface FinishedEvent extends EventBase {
  type: 'FINISHED';
  data: FinishedData;
}
export interface RunEndedEvent extends EventBase {
  type: 'RUN_ENDED';
  data: RunEndedData;
}
export type ReplayEvent =
  | RunStartedEvent
  | BorderCheckEvent
  | ToolCallEvent
  | DeniedEvent
  | KilledEvent
  | FinishedEvent
  | RunEndedEvent;

export interface ReplayMeta {
  id: string;
  title: string;
  scenario: string;
  driver: Driver;
  enforce: boolean;
  harness_cap: number;
  task: string;
  home_permit: PermitJSON;
  ceilings: Record<string, PermitJSON>; // library, vault
  tool_costs: Record<string, number>;
  document_text: string;
  generated_by: string; // "scripts/record_replays.py" or "telepermit.cli"
}
export interface Replay {
  schema_version: 1;
  meta: ReplayMeta;
  events: ReplayEvent[];
}

export interface ReplayIndexEntry {
  id: string;
  title: string;
  file: string;
  driver: Driver;
  enforce: boolean;
}
export interface ReplayIndex {
  schema_version: 1;
  replays: ReplayIndexEntry[];
}

export interface ReducedState {
  place: string;
  step: number;
  spent: number;
  permit: PermitJSON;
  status: StateStatus;
}

export type LoadErrorKind =
  | 'network'
  | 'http'
  | 'invalid_json'
  | 'schema_version'
  | 'missing_field'
  | 'invalid_field';
export interface LoadError {
  file: string; // e.g. "./replays/index.json"
  kind: LoadErrorKind;
  message: string; // names the file and the cause
  status?: number; // kind 'http'
  field?: string; // kinds 'missing_field', 'invalid_field' (e.g. "meta.home_permit.allowance")
}
export type Result<T, E> = { ok: true; value: T } | { ok: false; error: E };
