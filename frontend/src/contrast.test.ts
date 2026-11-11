// Contrast checks for the timeline palette.
// Validates Requirements 5.10, 5.12, 9.1 and 11.1; see design.md section 16.
import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import { compositeOver, contrastRatio, relativeLuminance } from './contrast';

const BG_BASE = '#0a0a0a';
const BG_SURFACE = '#111111';

const AMBER = '#ffb000';
const AMBER_DIM = '#a06800';
const ROW_DIM = '#c98500';
const GREEN = '#00ff88';
const BLUE = '#4488ff';
const ORANGE = '#ff6600';
const PURPLE = '#aa66ff';
const RED = '#ff2222';

const RED_GLOW = '#ff222244';
const AMBER_GLOW = '#ffb00033';

const MIN_TEXT = 4.5;
const MIN_MARKER = 3;

const css = readFileSync(new URL('./styles.css', import.meta.url), 'utf8');

type Declarations = Map<string, string>;

interface Rule {
  selector: string;
  declarations: Declarations;
}

function parseRules(source: string): Rule[] {
  const stripped = source.replace(/\/\*[\s\S]*?\*\//g, '');
  const rules: Rule[] = [];
  const rulePattern = /([^{}]+)\{([^{}]*)\}/g;
  for (const match of stripped.matchAll(rulePattern)) {
    const declarations: Declarations = new Map();
    for (const part of (match[2] ?? '').split(';')) {
      const colon = part.indexOf(':');
      if (colon > 0) {
        declarations.set(part.slice(0, colon).trim(), part.slice(colon + 1).trim());
      }
    }
    rules.push({ selector: (match[1] ?? '').trim(), declarations });
  }
  return rules;
}

function escapeRegExp(text: string): string {
  return text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function bodyOf(selector: string): Declarations {
  const pattern = new RegExp(`(?:^|[}{;])\\s*${escapeRegExp(selector)}\\s*\\{([^{}]*)\\}`, 'g');
  const stripped = css.replace(/\/\*[\s\S]*?\*\//g, '');
  const merged: Declarations = new Map();
  for (const match of stripped.matchAll(pattern)) {
    for (const part of (match[1] ?? '').split(';')) {
      const colon = part.indexOf(':');
      if (colon > 0) {
        merged.set(part.slice(0, colon).trim(), part.slice(colon + 1).trim());
      }
    }
  }
  return merged;
}

function tints(): string[] {
  return [BG_BASE, BG_SURFACE].flatMap((bg) => [
    compositeOver(RED_GLOW, bg),
    compositeOver(AMBER_GLOW, bg),
  ]);
}

describe('contrast', () => {
  it('computes known reference values', () => {
    expect(contrastRatio('#000000', '#ffffff')).toBeCloseTo(21, 5);
    expect(contrastRatio('#ffb000', '#ffb000')).toBe(1);
    expect(contrastRatio(AMBER, BG_BASE)).toBeCloseTo(contrastRatio(BG_BASE, AMBER), 10);
    expect(relativeLuminance('#000000')).toBe(0);
    expect(relativeLuminance('#ffffff')).toBeCloseTo(1, 5);
  });

  it('keeps every text colour at 4.5 or more on the plain backgrounds', () => {
    const measured: [string, number, number][] = [
      [ROW_DIM, 6.447, 6.149],
      [AMBER, 10.806, 10.307],
      [GREEN, 14.763, 14.081],
      [BLUE, 5.856, 5.585],
      [ORANGE, 6.743, 6.432],
      [PURPLE, 5.707, 5.443],
      [RED, 5.189, 4.949],
    ];
    for (const [colour, onBase, onSurface] of measured) {
      expect(contrastRatio(colour, BG_BASE)).toBeCloseTo(onBase, 2);
      expect(contrastRatio(colour, BG_SURFACE)).toBeCloseTo(onSurface, 2);
      expect(contrastRatio(colour, BG_BASE)).toBeGreaterThanOrEqual(MIN_TEXT);
      expect(contrastRatio(colour, BG_SURFACE)).toBeGreaterThanOrEqual(MIN_TEXT);
    }
  });

  it('shows amber-dim is below 4.5 on both plain backgrounds', () => {
    expect(contrastRatio(AMBER_DIM, BG_BASE)).toBeCloseTo(4.219, 2);
    expect(contrastRatio(AMBER_DIM, BG_SURFACE)).toBeCloseTo(4.024, 2);
    expect(contrastRatio(AMBER_DIM, BG_BASE)).toBeLessThan(MIN_TEXT);
    expect(contrastRatio(AMBER_DIM, BG_SURFACE)).toBeLessThan(MIN_TEXT);
  });

  it('composites translucent tints over opaque backgrounds', () => {
    expect(compositeOver(RED_GLOW, BG_BASE)).toBe('#4b1010');
    expect(compositeOver(RED_GLOW, BG_SURFACE)).toBe('#501616');
    expect(compositeOver(AMBER_GLOW, BG_BASE)).toBe('#3b2b08');
    expect(compositeOver(AMBER_GLOW, BG_SURFACE)).toBe('#41310e');
  });

  it('keeps amber at 4.5 or more on all four tints', () => {
    const expected: [string, number][] = [
      [compositeOver(RED_GLOW, BG_BASE), 8.301],
      [compositeOver(RED_GLOW, BG_SURFACE), 7.811],
      [compositeOver(AMBER_GLOW, BG_BASE), 7.467],
      [compositeOver(AMBER_GLOW, BG_SURFACE), 6.862],
    ];
    for (const [tint, ratio] of expected) {
      expect(contrastRatio(AMBER, tint)).toBeCloseTo(ratio, 2);
      expect(contrastRatio(AMBER, tint)).toBeGreaterThanOrEqual(MIN_TEXT);
    }
  });

  it('shows red text on the red tints is below 4.5 but at least 3', () => {
    const expected: [string, number][] = [
      [compositeOver(RED_GLOW, BG_BASE), 3.986],
      [compositeOver(RED_GLOW, BG_SURFACE), 3.751],
    ];
    for (const [tint, ratio] of expected) {
      expect(contrastRatio(RED, tint)).toBeCloseTo(ratio, 2);
      expect(contrastRatio(RED, tint)).toBeLessThan(MIN_TEXT);
      expect(contrastRatio(RED, tint)).toBeGreaterThanOrEqual(MIN_MARKER);
    }
  });

  it('keeps marker and border colours at 3 or more on every tint', () => {
    for (const tint of tints()) {
      for (const colour of [RED, BLUE, PURPLE, ORANGE, GREEN]) {
        expect(contrastRatio(colour, tint)).toBeGreaterThanOrEqual(MIN_MARKER);
      }
    }
  });

  it('sets tinted timeline rows to var(--amber) text', () => {
    for (const selector of [
      '.timeline-event.selected',
      '.timeline-event.killed',
      '.timeline-event.run-ended-killed',
    ]) {
      const color = bodyOf(selector).get('color');
      expect(color).toBe('var(--amber)');
      expect(color).not.toBe('var(--red)');
    }
  });

  it('never gives a tinted timeline row a coloured text value', () => {
    const forbidden = [
      'var(--red)',
      'var(--blue)',
      'var(--purple)',
      'var(--orange)',
      'var(--row-dim)',
      'var(--green)',
    ];
    for (const selector of [
      '.timeline-event.selected',
      '.timeline-event.killed',
      '.timeline-event.run-ended-killed',
    ]) {
      expect(forbidden).not.toContain(bodyOf(selector).get('color'));
    }
  });

  it('defines the row-dim and glow tokens in :root', () => {
    const root = bodyOf(':root');
    expect(root.get('--row-dim')).toBe('#c98500');
    expect(root.get('--amber-glow')).toBe('#ffb00033');
    expect(root.get('--red-glow')).toBe('#ff222244');
  });

  it('declares no opacity on timeline event rules', () => {
    const eventRules = parseRules(css).filter((rule) => rule.selector.startsWith('.timeline-event'));
    expect(eventRules.length).toBeGreaterThan(0);
    for (const rule of eventRules) {
      expect(rule.declarations.has('opacity')).toBe(false);
    }
  });
});
