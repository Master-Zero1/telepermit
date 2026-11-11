// Replay picker (timeline-ui design section 13).
import { useId } from 'react';
import type { ChangeEvent } from 'react';
import { driverLabel } from '../present';
import type { ReplayIndexEntry } from '../types';

export interface ReplayPickerProps {
  entries: ReplayIndexEntry[];
  selectedId: string;
  onSelect: (id: string) => void;
  disabled: boolean;
}

export function ReplayPicker({ entries, selectedId, onSelect, disabled }: ReplayPickerProps) {
  const id = useId();
  return (
    <div className="replay-picker">
      <label htmlFor={id}>Replay</label>
      <select
        id={id}
        value={selectedId}
        disabled={disabled}
        onChange={(e: ChangeEvent<HTMLSelectElement>) => onSelect(e.target.value)}
      >
        {entries.map((entry) => (
          <option key={entry.id} value={entry.id}>
            {`${entry.title} — ${driverLabel(entry.driver)}`}
          </option>
        ))}
      </select>
    </div>
  );
}