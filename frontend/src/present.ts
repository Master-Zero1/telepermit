// Presentation helpers (timeline-ui design section 10).
import { borderBadge } from './badge';
import { DRIVER_LABEL } from './constants';
import { reduceEvents } from './reduce';
import type { Driver, KilledReason, ReplayEvent, RunStatus, StateStatus } from './types';

export type Tone = 'amber' | 'green' | 'orange' | 'red' | 'blue' | 'purple' | 'dim';
export type RunEndedStyle = 'killed' | 'cap' | 'plain';
export interface StatusView {
  status: StateStatus;
  text: string;
  killed: { reason: KilledReason; limit: number; observed: number } | null;
}

export const SELECTED_MARKER = '▸';

const KILLED_SUFFIX = 'The engine destroyed the agent.';

function runEndedTone(status: RunStatus): Tone {
  switch (status) {
    case 'HARNESS_CAP':
      return 'dim';
    case 'FINISHED':
      return 'green';
    default:
      return 'red';
  }
}

export function eventTone(event: ReplayEvent): Tone {
  switch (event.type) {
    case 'RUN_STARTED':
      return 'amber';
    case 'BORDER_CHECK':
      if (event.data.decision === 'ADMIT') return 'green';
      return event.data.decision === 'ADMIT_IMPOSED' ? 'orange' : 'red';
    case 'TOOL_CALL':
      return 'blue';
    case 'DENIED':
    case 'KILLED':
      return 'red';
    case 'FINISHED':
      return 'green';
    case 'RUN_ENDED':
      return runEndedTone(event.data.status);
  }
}

export function isKilledRow(event: ReplayEvent): boolean {
  return event.type === 'KILLED';
}

export function runEndedStyle(event: ReplayEvent): RunEndedStyle {
  if (event.type !== 'RUN_ENDED') return 'plain';
  if (event.data.status === 'KILLED') return 'killed';
  return event.data.status === 'HARNESS_CAP' ? 'cap' : 'plain';
}

export function rowTextTone(event: ReplayEvent, selected: boolean): Tone {
  if (selected) return 'amber';
  if (isKilledRow(event) || runEndedStyle(event) === 'killed') return 'amber';
  if (runEndedStyle(event) === 'cap') return 'dim';
  return eventTone(event);
}

export function eventLabel(event: ReplayEvent): string {
  switch (event.type) {
    case 'RUN_STARTED':
    case 'FINISHED':
      return event.type;
    case 'BORDER_CHECK':
      return `${event.type} ${event.data.decision}`;
    case 'TOOL_CALL':
      return `${event.type} ${event.data.action}`;
    case 'DENIED':
    case 'KILLED':
      return `${event.type} ${event.data.reason}`;
    case 'RUN_ENDED':
      return `${event.type} ${event.data.status}`;
  }
}

export function eventSummary(event: ReplayEvent): string {
  switch (event.type) {
    case 'RUN_STARTED':
      return `${event.data.scenario} (${DRIVER_LABEL[event.data.driver]})`;
    case 'BORDER_CHECK': {
      const via = event.data.via_action === null ? 'at spawn' : `via ${event.data.via_action}`;
      return `${event.data.place} ${via}: ${event.data.decision} (${event.data.reason})`;
    }
    case 'TOOL_CALL':
      return `${event.data.action} cost ${event.data.cost}`;
    case 'DENIED':
      return `${event.data.action} denied`;
    case 'KILLED':
      return `KILLED ${event.data.reason} limit ${event.data.limit} observed ${event.data.observed}`;
    case 'FINISHED':
      return 'agent finished';
    case 'RUN_ENDED':
      return `run ended: ${event.data.status}`;
  }
}

export function driverLabel(driver: Driver): string {
  return DRIVER_LABEL[driver];
}

function killedBefore(events: readonly ReplayEvent[], index: number): StatusView | null {
  for (const event of events.slice(0, index + 1)) {
    if (event.type === 'KILLED') {
      const { reason, limit, observed } = event.data;
      return {
        status: 'KILLED',
        text: `KILLED ${reason}. ${KILLED_SUFFIX}`,
        killed: { reason, limit, observed },
      };
    }
  }
  return null;
}

function refusalReason(events: readonly ReplayEvent[]): string | null {
  for (let i = events.length - 1; i >= 0; i -= 1) {
    const event = events[i];
    if (event !== undefined && event.type === 'BORDER_CHECK' && event.data.decision === 'REFUSE') {
      return event.data.reason;
    }
  }
  return null;
}

export function statusView(events: readonly ReplayEvent[], index: number): StatusView {
  const killed = killedBefore(events, index);
  if (killed !== null) return killed;
  const prefix = events.slice(0, index + 1);
  const { status } = reduceEvents(prefix);
  if (status === 'REFUSED') {
    const reason = refusalReason(prefix);
    return { status, text: reason === null ? status : `REFUSED ${reason}`, killed: null };
  }
  return { status, text: status, killed: null };
}

export function cursorBlinks(statuses: readonly StateStatus[]): boolean {
  return statuses.length > 0 && statuses.every((s) => s === 'ALIVE');
}

export function positionLabel(
  mode: 'event' | 'turn',
  pos: number,
  max: number,
  count: number,
): string {
  return mode === 'event' ? `event ${pos + 1} of ${count}` : `turn ${pos} of ${max}`;
}

export function liveMessage(events: readonly ReplayEvent[], index: number): string {
  const event = events[index];
  const head = `Event ${index + 1} of ${events.length}`;
  if (event === undefined) return head;
  let message = `${head}: ${eventLabel(event)}`;
  if (event.type === 'KILLED') {
    message += `, limit ${event.data.limit}, observed ${event.data.observed}`;
  } else if (event.type === 'BORDER_CHECK') {
    message += `, ${borderBadge(events, index).text}`;
  }
  return message;
}
