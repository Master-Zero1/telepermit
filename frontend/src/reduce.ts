// reduceEvents mirrors audit.py reduce_events; CONTRACTS section 6, timeline-ui design section 3.
import type { PermitJSON, ReducedState, ReplayEvent, StateStatus } from './types';

export function reduceEvents(events: readonly ReplayEvent[]): ReducedState {
  if (events.length === 0) {
    throw new Error('cannot reduce an empty event list');
  }
  let permit: PermitJSON | null = null;
  let status: StateStatus = 'ALIVE';
  for (const event of events) {
    switch (event.type) {
      case 'RUN_STARTED':
        permit = event.data.permit;
        break;
      case 'BORDER_CHECK':
        if (permit !== null) {
          permit = event.data.permit_after;
        }
        break;
      case 'RUN_ENDED':
        status = event.data.status;
        break;
      default:
        break;
    }
  }
  if (permit === null) {
    throw new Error('the event list has no RUN_STARTED event');
  }
  const last = events[events.length - 1];
  return {
    place: last.place,
    step: last.step,
    spent: last.spent,
    permit: {
      lifetime_s: permit.lifetime_s,
      max_steps: permit.max_steps,
      allowance: permit.allowance,
      allowed_actions: [...permit.allowed_actions],
    },
    status,
  };
}
