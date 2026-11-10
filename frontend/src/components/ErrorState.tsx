// Load error display (timeline-ui design section 13).
import type { LoadError } from '../types';

export interface ErrorStateProps {
  error: LoadError;
}

export function ErrorState({ error }: ErrorStateProps) {
  return (
    <div className="error-state" role="alert">
      <h2>Could not load replay</h2>
      <p>{error.message}</p>
    </div>
  );
}
