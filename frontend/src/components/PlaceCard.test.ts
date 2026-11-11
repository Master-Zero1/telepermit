// Regression test for FIX (task 6 follow-up): the agent token is announced once.
// The visible text "agent here" carries the state; the square glyph is decorative.
// Requirements 2.2, 11.4, 11.5. No DOM library is installed, so this reads the source.
import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';

const source = readFileSync(new URL('./PlaceCard.tsx', import.meta.url), 'utf8');
const tokenSpan = /<span className="agent-token"[^>]*>/.exec(source)?.[0] ?? '';

describe('PlaceCard agent token', () => {
  it('hides the decorative token glyph from assistive technology', () => {
    expect(tokenSpan).toContain('aria-hidden="true"');
  });

  it('gives the glyph no role or label of its own', () => {
    expect(tokenSpan).not.toContain('role=');
    expect(tokenSpan).not.toContain('aria-label=');
  });

  it('keeps the visible text that states the token', () => {
    expect(source).toContain('agent here');
    expect(source).toContain('agent not here');
  });
});