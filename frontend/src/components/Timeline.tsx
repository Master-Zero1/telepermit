// Timeline rows (timeline-ui design sections 13 and 15).
import { useEffect, useRef, useState } from 'react';
import type { KeyboardEvent } from 'react';
import { REDUCED_MOTION_QUERY } from '../constants';
import {
  SELECTED_MARKER,
  eventLabel,
  eventSummary,
  eventTone,
  isKilledRow,
  rowTextTone,
  runEndedStyle,
} from '../present';
import type { ReplayEvent } from '../types';

export interface TimelineProps {
  events: ReplayEvent[];
  selected: number;
  onSelect: (i: number) => void;
}

function rowClass(event: ReplayEvent, i: number, selected: number): string {
  const classes = [
    'timeline-event',
    `tone-${eventTone(event)}`,
    `text-${rowTextTone(event, i === selected)}`,
  ];
  if (i === selected) classes.push('selected');
  if (i > selected) classes.push('future');
  if (isKilledRow(event)) classes.push('killed');
  const ended = runEndedStyle(event);
  if (ended !== 'plain') classes.push(`run-ended-${ended}`);
  return classes.join(' ');
}

function scrollBehavior(): ScrollBehavior {
  const reduced =
    typeof window.matchMedia !== 'function' || window.matchMedia(REDUCED_MOTION_QUERY).matches;
  return reduced ? 'auto' : 'smooth';
}

function targetIndex(key: string, i: number, last: number): number | null {
  switch (key) {
    case 'ArrowUp':
      return Math.max(i - 1, 0);
    case 'ArrowDown':
      return Math.min(i + 1, last);
    case 'Home':
      return 0;
    case 'End':
      return last;
    default:
      return null;
  }
}

export function Timeline({ events, selected, onSelect }: TimelineProps) {
  const rows = useRef<(HTMLButtonElement | null)[]>([]);
  const [focus, setFocus] = useState(selected);

  useEffect(() => {
    setFocus(selected);
    rows.current[selected]?.scrollIntoView({ block: 'nearest', behavior: scrollBehavior() });
  }, [selected]);

  function onKeyDown(e: KeyboardEvent<HTMLButtonElement>, i: number): void {
    const next = targetIndex(e.key, i, events.length - 1);
    if (next === null) return;
    e.preventDefault();
    setFocus(next);
    rows.current[next]?.focus();
  }

  return (
    <ol className="timeline" aria-label="Events">
      {events.map((event, i) => (
        <li key={event.seq}>
          <button
            type="button"
            ref={(el) => {
              rows.current[i] = el;
            }}
            className={rowClass(event, i, selected)}
            aria-current={i === selected ? 'true' : undefined}
            tabIndex={i === focus ? 0 : -1}
            onClick={() => onSelect(i)}
            onKeyDown={(e) => onKeyDown(e, i)}
          >
            {i === selected ? <span aria-hidden="true">{SELECTED_MARKER} </span> : null}
            <span className="seq">{event.seq}</span>
            <span className="dot" aria-hidden="true" />
            <span className="label">{eventLabel(event)}</span>
            <span className="summary">{eventSummary(event)}</span>
          </button>
        </li>
      ))}
    </ol>
  );
}
