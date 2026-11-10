import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';

interface Decl {
  property: string;
  value: string;
}

interface Rule {
  selector: string;
  decls: Decl[];
}

interface ParsedCss {
  rules: Rule[];
  keyframeDecls: Decl[];
}

function collapse(text: string): string {
  return text.replace(/\s+/g, ' ').trim();
}

function parseDecls(body: string): Decl[] {
  const decls: Decl[] = [];
  for (const part of body.split(';')) {
    const colon = part.indexOf(':');
    if (colon < 0) continue;
    const property = part.slice(0, colon).trim().toLowerCase();
    const value = collapse(part.slice(colon + 1));
    if (property !== '' && value !== '') decls.push({ property, value });
  }
  return decls;
}

function findClose(text: string, open: number): number {
  let depth = 0;
  for (let i = open; i < text.length; i += 1) {
    const ch = text.charAt(i);
    if (ch === '{') depth += 1;
    if (ch === '}') {
      depth -= 1;
      if (depth === 0) return i;
    }
  }
  return text.length;
}

function walk(text: string, out: ParsedCss): void {
  let pos = 0;
  while (pos < text.length) {
    const open = text.indexOf('{', pos);
    if (open < 0) return;
    const close = findClose(text, open);
    const prelude = collapse(text.slice(pos, open));
    const body = text.slice(open + 1, close);
    if (/^@(-\w+-)?keyframes\b/i.test(prelude)) {
      let inner = 0;
      while (inner < body.length) {
        const innerOpen = body.indexOf('{', inner);
        if (innerOpen < 0) break;
        const innerClose = findClose(body, innerOpen);
        out.keyframeDecls.push(...parseDecls(body.slice(innerOpen + 1, innerClose)));
        inner = innerClose + 1;
      }
    } else if (prelude.startsWith('@')) {
      walk(body, out);
    } else {
      out.rules.push({ selector: prelude, decls: parseDecls(body) });
    }
    pos = close + 1;
  }
}

function parseCss(source: string): ParsedCss {
  const out: ParsedCss = { rules: [], keyframeDecls: [] };
  walk(source.replace(/\/\*[\s\S]*?\*\//g, ''), out);
  return out;
}

function declValue(rules: Rule[], selector: string, property: string): string | undefined {
  let found: string | undefined;
  for (const rule of rules) {
    if (rule.selector !== selector) continue;
    for (const decl of rule.decls) {
      if (decl.property === property) found = decl.value;
    }
  }
  return found;
}

const css = parseCss(readFileSync(new URL('./styles.css', import.meta.url), 'utf8'));

const TINT_SELECTORS = [
  '.timeline-event.selected',
  '.timeline-event.killed',
  '.timeline-event.run-ended-killed',
];
const PLAIN_BACKGROUNDS = ['var(--bg)', 'var(--bg-surface)', 'var(--bg-inset)', 'transparent', 'none'];
const ALLOWED_PAIRS: ReadonlyArray<readonly [string, string]> = [
  ['.timeline-event.selected', 'var(--amber-glow)'],
  ['.timeline-event.killed', 'var(--red-glow)'],
  ['.timeline-event.run-ended-killed', 'var(--red-glow)'],
  ['.meter-fill.ok', 'var(--green)'],
  ['.meter-fill.over', 'var(--red)'],
  ['.dot', 'var(--dot-color)'],
];
const DOT_COLORS = [
  'var(--red)',
  'var(--green)',
  'var(--blue)',
  'var(--orange)',
  'var(--purple)',
  'var(--amber)',
];
const TRANSLUCENT = /rgba\(|hsla\(|#[0-9a-fA-F]{8}\b/i;

// Requirements 5.12, 6.18, 9.1, 11.1, 11.2; design 'styles.backgrounds'.
describe('styles.backgrounds', () => {
  it('has the selected-row tint rule', () => {
    const value = declValue(css.rules, '.timeline-event.selected', 'background');
    expect(value).toBe('var(--amber-glow)');
  });

  it('gives the killed rows the red tint', () => {
    expect(declValue(css.rules, '.timeline-event.killed', 'background')).toBe('var(--red-glow)');
    expect(declValue(css.rules, '.timeline-event.run-ended-killed', 'background')).toBe(
      'var(--red-glow)',
    );
  });

  it('sets amber text on all tint rules', () => {
    for (const selector of TINT_SELECTORS) {
      expect(declValue(css.rules, selector, 'color'), selector).toBe('var(--amber)');
    }
  });

  it('allows only plain backgrounds, two tints and three solid fills', () => {
    const violations: string[] = [];
    for (const rule of css.rules) {
      for (const decl of rule.decls) {
        if (decl.property !== 'background' && decl.property !== 'background-color') continue;
        const pairOk = ALLOWED_PAIRS.some(
          ([selector, value]) => selector === rule.selector && value === decl.value,
        );
        if (!PLAIN_BACKGROUNDS.includes(decl.value) && !pairOk) {
          violations.push(`${rule.selector} { ${decl.property}: ${decl.value} }`);
        }
      }
    }
    expect(violations).toEqual([]);
  });

  it('defines the three solid fills', () => {
    expect(declValue(css.rules, '.meter-fill.ok', 'background')).toBe('var(--green)');
    expect(declValue(css.rules, '.meter-fill.over', 'background')).toBe('var(--red)');
    expect(declValue(css.rules, '.dot', 'background')).toBe('var(--dot-color)');
  });

  it('restricts --dot-color to the palette and declares it at least once', () => {
    const values: string[] = [];
    for (const rule of css.rules) {
      for (const decl of rule.decls) {
        if (decl.property === '--dot-color') values.push(decl.value);
      }
    }
    expect(values.length).toBeGreaterThan(0);
    expect(values.filter((value) => !DOT_COLORS.includes(value))).toEqual([]);
  });

  it('has no translucent colours except the two glow tints in :root', () => {
    const violations: string[] = [];
    const check = (selector: string, decl: Decl): void => {
      if (!TRANSLUCENT.test(decl.value)) return;
      const allowed =
        selector === ':root' &&
        ((decl.property === '--amber-glow' && decl.value.toLowerCase() === '#ffb00033') ||
          (decl.property === '--red-glow' && decl.value.toLowerCase() === '#ff222244'));
      if (!allowed) violations.push(`${selector} { ${decl.property}: ${decl.value} }`);
    };
    for (const rule of css.rules) {
      for (const decl of rule.decls) check(rule.selector, decl);
    }
    for (const decl of css.keyframeDecls) check('@keyframes', decl);
    expect(violations).toEqual([]);
  });

  it('never combines text colour with opacity below 1', () => {
    const violations: string[] = [];
    for (const rule of css.rules) {
      const hasColor = rule.decls.some((decl) => decl.property === 'color');
      if (!hasColor) continue;
      for (const decl of rule.decls) {
        if (decl.property !== 'opacity') continue;
        const numeric = Number(decl.value);
        if (Number.isNaN(numeric) || numeric < 1) violations.push(rule.selector);
      }
    }
    expect(violations).toEqual([]);
  });

  it('defines --row-dim as #c98500', () => {
    expect(declValue(css.rules, ':root', '--row-dim')?.toLowerCase()).toBe('#c98500');
  });
});
