// Turn mapping and shared-turn index selection (design section 11).
import type { ReplayEvent } from './types';

function startsTurn(event: ReplayEvent): boolean {
  if (event.type === 'RUN_STARTED' || event.type === 'RUN_ENDED') {
    return false;
  }
  if (event.type === 'BORDER_CHECK' && event.data.via_action === null) {
    return false;
  }
  return true;
}

export function turnsOf(events: readonly ReplayEvent[]): number[] {
  const turns: number[] = [];
  let counter = 0;
  for (const event of events) {
    if (startsTurn(event)) {
      counter += 1;
    }
    turns.push(counter);
  }
  return turns;
}

export function lastTurn(events: readonly ReplayEvent[]): number {
  const turns = turnsOf(events);
  return turns.length === 0 ? 0 : turns[turns.length - 1];
}

export function selectIndex(turns: readonly number[], turn: number): number {
  let found = 0;
  for (let i = 0; i < turns.length; i += 1) {
    if (turns[i] <= turn) {
      found = i;
    }
  }
  return found;
}

export function sharedMax(a: readonly ReplayEvent[], b: readonly ReplayEvent[]): number {
  return Math.max(lastTurn(a), lastTurn(b));
}
