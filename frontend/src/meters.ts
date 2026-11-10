// Meter rows, bar percentage and over-limit flag (design section 6).
import type { PermitJSON, ReplayEvent } from './types';

export interface MeterRow {
  key: 'allowance' | 'steps' | 'lifetime';
  label: string;
  observed: number;
  limit: number;
  percent: number;
  over: boolean;
}

const LABEL_ALLOWANCE = 'allowance (teleclicks)';
const LABEL_STEPS = 'steps';
const LABEL_LIFETIME = 'lifetime (s)';

export function barPercent(observed: number, limit: number): number {
  if (limit === 0) {
    return observed > 0 ? 100 : 0;
  }
  return Math.min(Math.max((observed / limit) * 100, 0), 100);
}

export function isOver(observed: number, limit: number): boolean {
  return observed > limit;
}

function makeRow(
  key: MeterRow['key'],
  label: string,
  observed: number,
  limit: number,
): MeterRow {
  return {
    key,
    label,
    observed,
    limit,
    percent: barPercent(observed, limit),
    over: isOver(observed, limit),
  };
}

export function meterRows(home: PermitJSON, event: ReplayEvent): MeterRow[] {
  return [
    makeRow('allowance', LABEL_ALLOWANCE, event.spent, home.allowance),
    makeRow('steps', LABEL_STEPS, event.step, home.max_steps),
    makeRow('lifetime', LABEL_LIFETIME, event.t, home.lifetime_s),
  ];
}
