// Status line and polite live region (timeline-ui design sections 13 and 15).
import type { StatusView } from '../present';

export interface StatusLineProps {
  view: StatusView;
  live?: string;
}

export function StatusLine({ view, live }: StatusLineProps) {
  const killed = view.status === 'KILLED';
  return (
    <>
      <p className={killed ? 'status status-killed' : 'status'}>
        {view.text}
        {view.killed !== null
          ? ` limit ${view.killed.limit}, observed ${view.killed.observed}`
          : ''}
      </p>
      {live !== undefined ? (
        <div className="visually-hidden" role="status" aria-live="polite" aria-atomic="true">
          {live}
        </div>
      ) : null}
    </>
  );
}