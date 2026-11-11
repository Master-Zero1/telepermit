// Place card and border badge view (design section 13).
import type { BorderBadge } from '../badge';

export interface PlaceCardProps {
  place: string;
  label: string;
  hasToken: boolean;
}

export function PlaceCard({ place, label, hasToken }: PlaceCardProps) {
  return (
    <section className="place-card" data-place={place} aria-label={`Place: ${label}`}>
      <h3>{label}</h3>
      {hasToken ? (
        <p>
          <span className="agent-token" aria-hidden="true">
            ■
          </span>
          agent here
        </p>
      ) : (
        <p className="visually-hidden">agent not here</p>
      )}
    </section>
  );
}

export interface BorderBadgeViewProps {
  badge: BorderBadge;
}

export function BorderBadgeView({ badge }: BorderBadgeViewProps) {
  const className = badge.tone === 'none' ? 'border-badge' : `border-badge tone-${badge.tone}`;
  return (
    <p className={className}>
      {badge.text}
      {badge.reason !== null ? ` (${badge.reason})` : ''}
    </p>
  );
}
