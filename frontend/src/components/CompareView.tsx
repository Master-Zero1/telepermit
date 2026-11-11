// Compare view with shared turn and narrow tab switcher (timeline-ui design sections 14 and 15).
import { useEffect, useId, useMemo, useRef, useState } from 'react';
import type { KeyboardEvent } from 'react';
import { compareStatuses } from '../compareStatus';
import { NARROW_QUERY } from '../constants';
import { eventSummary, positionLabel, SELECTED_MARKER } from '../present';
import { selectIndex, sharedMax, turnsOf } from '../turns';
import type { Replay, ReplayEvent, StateStatus } from '../types';
import { useMediaQuery } from '../useMediaQuery';
import { useReplay } from '../useReplay';
import { PlaybackBar } from './PlaybackBar';
import { RunPanel } from './RunPanel';

export interface CompareViewProps {
  pair: { unenforced: Replay; enforced: Replay };
  onStatuses?: (statuses: StateStatus[]) => void;
}

type Side = 'unenforced' | 'enforced';

const SIDES: readonly Side[] = ['unenforced', 'enforced'];
const HEADINGS: Record<Side, string> = {
  unenforced: 'WITHOUT ENFORCEMENT',
  enforced: 'WITH ENFORCEMENT',
};

function summaryAt(events: readonly ReplayEvent[], index: number): string {
  const event = events[index];
  return event === undefined ? 'no events' : eventSummary(event);
}

function tabTarget(key: string, current: number): number | null {
  const last = SIDES.length - 1;
  switch (key) {
    case 'ArrowLeft':
      return current === 0 ? last : current - 1;
    case 'ArrowRight':
      return current === last ? 0 : current + 1;
    case 'Home':
      return 0;
    case 'End':
      return last;
    default:
      return null;
  }
}

export function CompareView({ pair, onStatuses }: CompareViewProps) {
  const { unenforced, enforced } = pair;
  const turns = useMemo(
    () => ({ unenforced: turnsOf(unenforced.events), enforced: turnsOf(enforced.events) }),
    [unenforced.events, enforced.events],
  );
  const controls = useReplay(sharedMax(unenforced.events, enforced.events));
  const { state } = controls;
  const narrow = useMediaQuery(NARROW_QUERY);
  const [active, setActive] = useState<Side>('unenforced');
  const tabRefs = useRef<(HTMLButtonElement | null)[]>([]);
  const baseId = useId();

  useEffect(() => {
    onStatuses?.(compareStatuses(unenforced.events, enforced.events, state.pos));
  }, [onStatuses, unenforced.events, enforced.events, state.pos]);

  const replays: Record<Side, Replay> = { unenforced, enforced };
  const indexOf = (side: Side): number => selectIndex(turns[side], state.pos);

  function onTabKeyDown(e: KeyboardEvent<HTMLButtonElement>, i: number): void {
    const next = tabTarget(e.key, i);
    if (next === null) return;
    e.preventDefault();
    setActive(SIDES[next]);
    tabRefs.current[next]?.focus();
  }

  function panel(side: Side) {
    return (
      <RunPanel
        key={replays[side].meta.id}
        replay={replays[side]}
        index={indexOf(side)}
        heading={HEADINGS[side]}
        onSelectEvent={(i) => controls.scrub(turns[side][i] ?? 0)}
        showDetail={false}
      />
    );
  }

  const live =
    `Turn ${state.pos} of ${state.max}. ` +
    `Without enforcement: ${summaryAt(unenforced.events, indexOf('unenforced'))}. ` +
    `With enforcement: ${summaryAt(enforced.events, indexOf('enforced'))}.`;

  return (
    <>
      <div className="visually-hidden" role="status" aria-live="polite" aria-atomic="true">
        {live}
      </div>
      {narrow ? (
        <>
          <div className="compare-tabs" role="tablist" aria-label="Compare columns">
            {SIDES.map((side, i) => (
              <button
                key={side}
                type="button"
                role="tab"
                id={`${baseId}-tab-${side}`}
                aria-selected={active === side}
                aria-controls={`${baseId}-panel-${side}`}
                tabIndex={active === side ? 0 : -1}
                ref={(el) => {
                  tabRefs.current[i] = el;
                }}
                onClick={() => setActive(side)}
                onKeyDown={(e) => onTabKeyDown(e, i)}
              >
                {active === side ? `${SELECTED_MARKER} ` : ''}
                {HEADINGS[side]}
              </button>
            ))}
          </div>
          <div
            role="tabpanel"
            id={`${baseId}-panel-${active}`}
            aria-labelledby={`${baseId}-tab-${active}`}
          >
            {panel(active)}
          </div>
        </>
      ) : (
        <div className="compare">{SIDES.map((side) => panel(side))}</div>
      )}
      <PlaybackBar
        state={state}
        label={positionLabel('turn', state.pos, state.max, 0)}
        onPlay={controls.play}
        onPause={controls.pause}
        onStepForward={controls.stepForward}
        onStepBack={controls.stepBack}
        onSpeed={controls.setSpeed}
        onScrub={controls.scrub}
      />
    </>
  );
}