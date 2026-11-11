// Run statuses of both compare-view sides at a shared turn (timeline-ui design sections 10 and 14).
import { statusView } from './present';
import { selectIndex, turnsOf } from './turns';
import type { ReplayEvent, StateStatus } from './types';

function sideStatus(events: readonly ReplayEvent[], turn: number): StateStatus {
  if (events.length === 0) {
    return 'ALIVE';
  }
  return statusView(events, selectIndex(turnsOf(events), turn)).status;
}

// [unenforced status, enforced status] at the event each side shows for the shared turn.
export function compareStatuses(
  unenforced: readonly ReplayEvent[],
  enforced: readonly ReplayEvent[],
  turn: number,
): StateStatus[] {
  return [sideStatus(unenforced, turn), sideStatus(enforced, turn)];
}