// Permit view model for the PermitCard (design sections 9 and 13).
import type { PermitField, PermitJSON, ReplayEvent } from './types';

export interface PermitFieldView {
  field: PermitField;
  value: string;
  narrowed: boolean;
}

export interface ActionView {
  name: string;
  removed: boolean; // in the home permit, not in the state permit
}

export interface PermitView {
  fields: PermitFieldView[];
  actions: ActionView[];
}

const FIELD_ORDER: readonly PermitField[] = [
  'lifetime_s',
  'max_steps',
  'allowance',
  'allowed_actions',
];

function fieldValue(permit: PermitJSON, field: PermitField): string {
  if (field === 'allowed_actions') return permit.allowed_actions.join(', ');
  return String(permit[field]);
}

function actionViews(statePermit: PermitJSON, home: PermitJSON): ActionView[] {
  const kept = statePermit.allowed_actions;
  const fromHome = home.allowed_actions.map((name) => ({ name, removed: !kept.includes(name) }));
  const extra = kept
    .filter((name) => !home.allowed_actions.includes(name))
    .map((name) => ({ name, removed: false }));
  return [...fromHome, ...extra];
}

export function permitView(
  statePermit: PermitJSON,
  home: PermitJSON,
  narrowed: readonly PermitField[],
): PermitView {
  return {
    fields: FIELD_ORDER.map((field) => ({
      field,
      value: fieldValue(statePermit, field),
      narrowed: narrowed.includes(field),
    })),
    actions: actionViews(statePermit, home),
  };
}

export function latestNarrowed(events: readonly ReplayEvent[], index: number): PermitField[] {
  for (let i = Math.min(index, events.length - 1); i >= 0; i -= 1) {
    const event = events[i];
    if (event !== undefined && event.type === 'BORDER_CHECK') {
      return [...event.data.narrowed_fields];
    }
  }
  return [];
}
