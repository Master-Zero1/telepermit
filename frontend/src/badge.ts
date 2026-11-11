// Border badge (design section 8).
import type { BorderCheckEvent, ReplayEvent } from './types';

export type BadgeTone = 'none' | 'green' | 'orange' | 'red';
export interface BorderBadge {
  text: string;
  reason: string | null;
  tone: BadgeTone;
}

const TEXT_NONE = 'NO BORDER CHECK YET';
const TEXT_ADMITTED = 'ADMITTED';
const TEXT_IMPOSED = 'ADMITTED UNDER IMPOSED PERMIT';
const TEXT_REFUSED = 'REFUSED';
const REASON_OK = 'OK';

function latestBorderCheck(events: readonly ReplayEvent[], index: number): BorderCheckEvent | null {
  for (let i = Math.min(index, events.length - 1); i >= 0; i -= 1) {
    const event = events[i];
    if (event !== undefined && event.type === 'BORDER_CHECK') return event;
  }
  return null;
}

export function borderBadge(events: readonly ReplayEvent[], index: number): BorderBadge {
  const check = latestBorderCheck(events, index);
  if (check === null) return { text: TEXT_NONE, reason: null, tone: 'none' };
  const { decision, reason } = check.data;
  switch (decision) {
    case 'ADMIT':
      return { text: TEXT_ADMITTED, reason: reason === REASON_OK ? null : reason, tone: 'green' };
    case 'ADMIT_IMPOSED':
      return { text: TEXT_IMPOSED, reason: null, tone: 'orange' };
    case 'REFUSE':
      return { text: TEXT_REFUSED, reason, tone: 'red' };
  }
}
