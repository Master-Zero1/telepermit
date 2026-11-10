// Permit card (design sections 9 and 13).
import { Fragment } from 'react';
import type { ActionView, PermitView } from '../permitView';

export interface PermitCardProps {
  view: PermitView;
}

function ActionList({ actions }: { actions: ActionView[] }) {
  return (
    <>
      {actions.map((action, i) => (
        <Fragment key={action.name}>
          {i > 0 ? ', ' : ''}
          {action.removed ? (
            <>
              <s className="removed">{action.name}</s>
              <span className="visually-hidden"> (removed)</span>
            </>
          ) : (
            <span>{action.name}</span>
          )}
        </Fragment>
      ))}
    </>
  );
}

export function PermitCard({ view }: PermitCardProps) {
  return (
    <section className="permit-card" aria-label="Current permit">
      <h3>Permit</h3>
      <dl>
        {view.fields.map((f) => (
          <Fragment key={f.field}>
            <dt>{f.field}</dt>
            <dd className={f.narrowed ? 'narrowed' : undefined}>
              {f.narrowed ? <span aria-hidden="true">▼ </span> : null}
              {f.field === 'allowed_actions' ? <ActionList actions={view.actions} /> : f.value}
              {f.narrowed ? ' narrowed' : ''}
            </dd>
          </Fragment>
        ))}
      </dl>
    </section>
  );
}
