// Run panel for one replay (timeline-ui design section 13).
import { useId, useMemo } from 'react';
import { composeLive } from '../announce';
import { borderBadge } from '../badge';
import { PLACES } from '../constants';
import { meterRows } from '../meters';
import { latestNarrowed, permitView } from '../permitView';
import { tokenPlace } from '../placeMap';
import { driverLabel, liveMessage, statusView } from '../present';
import { reduceEvents } from '../reduce';
import type { Replay } from '../types';
import { EventDetail } from './EventDetail';
import { Meters } from './Meters';
import { PermitCard } from './PermitCard';
import { BorderBadgeView, PlaceCard } from './PlaceCard';
import { StatusLine } from './StatusLine';
import { Timeline } from './Timeline';

export interface RunPanelProps {
  replay: Replay;
  index: number;
  heading?: string;
  onSelectEvent: (eventIndex: number) => void;
  showDetail: boolean;
  announce?: boolean;
  announcement?: string | null;
}

function placeLabel(place: string): string {
  return place.charAt(0).toUpperCase() + place.slice(1);
}

export function RunPanel({
  replay,
  index,
  heading,
  onSelectEvent,
  showDetail,
  announce = false,
  announcement = null,
}: RunPanelProps) {
  const headingId = useId();
  const { events, meta } = replay;
  const event = events[index];
  const view = useMemo(() => {
    if (event === undefined) {
      return null;
    }
    const prefix = events.slice(0, index + 1);
    return {
      token: tokenPlace(events, index),
      badge: borderBadge(events, index),
      rows: meterRows(meta.home_permit, event),
      permit: permitView(
        reduceEvents(prefix).permit,
        meta.home_permit,
        latestNarrowed(events, index),
      ),
      status: statusView(events, index),
    };
  }, [events, index, event, meta.home_permit]);

  return (
    <section aria-labelledby={headingId}>
      <h2 id={headingId}>
        {heading ?? meta.title} — {driverLabel(meta.driver)}
      </h2>
      {event === undefined || view === null ? (
        <p>This replay has no events.</p>
      ) : (
        <div className="run-panel">
          <div className="run-main">
            <StatusLine
              view={view.status}
              live={announce ? composeLive(liveMessage(events, index), announcement) : undefined}
            />
            <div className="places">
              <PlaceCard
                place={PLACES[0]}
                label={placeLabel(PLACES[0])}
                hasToken={view.token === PLACES[0]}
              />
              <div className="border-gate" aria-hidden="true" />
              <PlaceCard
                place={PLACES[1]}
                label={placeLabel(PLACES[1])}
                hasToken={view.token === PLACES[1]}
              />
            </div>
            <BorderBadgeView badge={view.badge} />
            <Meters rows={view.rows} />
            <PermitCard view={view.permit} />
          </div>
          <div className="run-side">
            <Timeline events={events} selected={index} onSelect={onSelectEvent} />
            {showDetail ? <EventDetail event={event} /> : null}
          </div>
        </div>
      )}
    </section>
  );
}