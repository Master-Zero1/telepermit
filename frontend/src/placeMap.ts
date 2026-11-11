// Token placement (design section 7).
import type { ReplayEvent } from './types';

export function tokenPlace(events: readonly ReplayEvent[], index: number): string | null {
  const event = events[index];
  if (event === undefined) return null;
  for (let i = 0; i <= index; i += 1) {
    const candidate = events[i];
    if (
      candidate !== undefined &&
      candidate.type === 'BORDER_CHECK' &&
      candidate.data.decision === 'REFUSE' &&
      candidate.data.via_action === null
    ) {
      return null;
    }
  }
  return event.place;
}
