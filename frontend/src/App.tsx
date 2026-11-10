// Application shell: loading, replay selection, single and compare modes (timeline-ui design section 13).
import { useEffect, useRef, useState } from 'react';
import { playbackAnnouncement } from './announce';
import { CompareView } from './components/CompareView';
import { ErrorState } from './components/ErrorState';
import { Note } from './components/Note';
import { PlaybackBar } from './components/PlaybackBar';
import { ReplayPicker } from './components/ReplayPicker';
import { RunPanel } from './components/RunPanel';
import { SUBTITLE } from './constants';
import { loadIndex, loadReplay } from './loader';
import type { FetchLike } from './loader';
import { resolveComparePair } from './pair';
import { cursorBlinks, positionLabel, statusView } from './present';
import type {
  LoadError,
  Replay,
  ReplayIndexEntry,
  Result,
  StateStatus,
} from './types';
import { useReplay } from './useReplay';

type Mode = 'single' | 'compare';
type ReplayResult = Result<Replay, LoadError>;

type Load =
  | { phase: 'loading' }
  | { phase: 'failed'; error: LoadError }
  | { phase: 'ready'; entries: ReplayIndexEntry[]; results: Record<string, ReplayResult> };

const fetchFn: FetchLike = (url) => window.fetch(url);

async function loadAll(): Promise<Load> {
  const index = await loadIndex(fetchFn);
  if (!index.ok) {
    return { phase: 'failed', error: index.error };
  }
  const entries = index.value.replays;
  const loaded = await Promise.all(entries.map((entry) => loadReplay(fetchFn, entry)));
  const results: Record<string, ReplayResult> = {};
  entries.forEach((entry, i) => {
    results[entry.id] = loaded[i];
  });
  return { phase: 'ready', entries, results };
}

interface SingleRunProps {
  replay: Replay;
  onStatus: (status: StateStatus) => void;
}

function SingleRun({ replay, onStatus }: SingleRunProps) {
  const { events } = replay;
  const controls = useReplay(Math.max(events.length - 1, 0));
  const { state } = controls;
  const previous = useRef(state);
  const announcement = playbackAnnouncement(previous.current, state);
  const status = events.length === 0 ? 'ALIVE' : statusView(events, state.pos).status;

  useEffect(() => {
    previous.current = state;
  });
  useEffect(() => {
    onStatus(status);
  }, [status, onStatus]);

  return (
    <>
      <RunPanel
        replay={replay}
        index={state.pos}
        announce
        announcement={announcement}
        showDetail
        onSelectEvent={(i) => controls.scrub(i)}
      />
      <PlaybackBar
        state={state}
        label={positionLabel('event', state.pos, state.max, events.length)}
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

function okReplays(entries: ReplayIndexEntry[], results: Record<string, ReplayResult>): Replay[] {
  const replays: Replay[] = [];
  for (const entry of entries) {
    const result = results[entry.id];
    if (result !== undefined && result.ok) {
      replays.push(result.value);
    }
  }
  return replays;
}

interface MainProps {
  load: Load;
  selectedId: string;
  mode: Mode;
  onStatus: (status: StateStatus) => void;
}

function Main({ load, selectedId, mode, onStatus }: MainProps) {
  if (load.phase === 'loading') {
    return <p>Loading replays…</p>;
  }
  if (load.phase === 'failed') {
    return <ErrorState error={load.error} />;
  }
  if (mode === 'compare') {
    const pair = resolveComparePair(okReplays(load.entries, load.results));
    if (pair.kind === 'unavailable') {
      return <p>{pair.message}</p>;
    }
    return <CompareView key="compare" pair={pair} />;
  }
  const result = load.results[selectedId];
  if (result === undefined) {
    return <p>No replays in the index.</p>;
  }
  if (!result.ok) {
    return <ErrorState error={result.error} />;
  }
  return <SingleRun key={result.value.meta.id} replay={result.value} onStatus={onStatus} />;
}

export function App() {
  const [load, setLoad] = useState<Load>({ phase: 'loading' });
  const [selectedId, setSelectedId] = useState('');
  const [mode, setMode] = useState<Mode>('single');
  const [singleStatus, setSingleStatus] = useState<StateStatus | null>(null);

  useEffect(() => {
    let cancelled = false;
    void loadAll().then((loaded) => {
      if (cancelled) {
        return;
      }
      setLoad(loaded);
      if (loaded.phase === 'ready') {
        setSelectedId(loaded.entries[0]?.id ?? '');
      }
    });
    return () => {
      cancelled = true;
    };
  }, []);

  // Single mode follows the selected run's status at its current event (reported by SingleRun);
  // compare mode uses ['ALIVE'].
  let statuses: StateStatus[] = [];
  if (mode === 'compare') {
    statuses = ['ALIVE'];
  } else if (singleStatus !== null) {
    statuses = [singleStatus];
  }
  const compare = mode === 'compare';

  return (
    <>
      <header>
        <h1>
          TelePermit
          <span
            className={cursorBlinks(statuses) ? 'cursor cursor-alive' : 'cursor'}
            aria-hidden="true"
          />
        </h1>
        <p className="subtitle">{SUBTITLE}</p>
        {load.phase === 'ready' ? (
          <>
            <ReplayPicker
              entries={load.entries}
              selectedId={selectedId}
              onSelect={setSelectedId}
              disabled={compare}
            />
            <button
              type="button"
              aria-pressed={compare}
              onClick={() => setMode(compare ? 'single' : 'compare')}
            >
              {compare ? '[Compare]' : 'Compare'}
            </button>
          </>
        ) : null}
      </header>
      <main>
        <Main load={load} selectedId={selectedId} mode={mode} onStatus={setSingleStatus} />
      </main>
      <Note />
    </>
  );
}
