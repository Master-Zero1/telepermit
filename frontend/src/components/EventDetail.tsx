// Event detail (timeline-ui design section 13).
import type { ReplayEvent } from '../types';

export interface EventDetailProps {
  event: ReplayEvent;
}

function explainOf(event: ReplayEvent): string | null {
  if ('explain' in event.data && typeof event.data.explain === 'string') {
    return event.data.explain;
  }
  return null;
}

export function EventDetail({ event }: EventDetailProps) {
  const explain = explainOf(event);
  return (
    <section className="event-detail" aria-label="Event detail">
      {explain === null ? null : <p className="explain">{explain}</p>}
      {event.type === 'KILLED' ? (
        <p>
          {event.data.reason}, limit {event.data.limit}, observed {event.data.observed}
        </p>
      ) : null}
      <pre>{JSON.stringify(event, null, 2)}</pre>
    </section>
  );
}
