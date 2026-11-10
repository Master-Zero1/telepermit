import { readdirSync, readFileSync } from 'node:fs';
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

// Scope definitions for 'source guards' (task 12.1):
// - APP files: every .ts / .tsx under frontend/src EXCEPT files ending in .test.ts,
//   anything under src/test/ and anything under src/test-types/.
// - SHIPPED files: the APP files plus styles.css and frontend/index.html. Test files are
//   never bundled or served, so the URL guard does not scan them (owner decision, task 12.1).
// Comments (// line, /* */ block, <!-- --> in html) are stripped before scanning, because a
// URL inside a comment is not a request. String literals are still scanned.
interface SourceFile {
  rel: string;
  text: string;
}

const SRC_URL = new URL('./', import.meta.url);

function listSrcFiles(dir: URL, prefix: string, out: string[]): void {
  for (const name of readdirSync(dir)) {
    if (name.includes('.')) {
      out.push(`${prefix}${name}`);
    } else {
      listSrcFiles(new URL(`${name}/`, dir), `${prefix}${name}/`, out);
    }
  }
}

function stripBlockComments(text: string): string {
  return text.replace(/\/\*[\s\S]*?\*\//g, '');
}

function stripHtmlComments(text: string): string {
  return text.replace(/<!--[\s\S]*?-->/g, '');
}

// Removes // and /* */ comments from TS/TSX while leaving string literals intact.
function stripCodeComments(text: string): string {
  let out = '';
  let i = 0;
  while (i < text.length) {
    const ch = text.charAt(i);
    const next = text.charAt(i + 1);
    if (ch === "'" || ch === '"' || ch === '`') {
      let j = i + 1;
      while (j < text.length && text.charAt(j) !== ch) {
        j += text.charAt(j) === '\\' ? 2 : 1;
      }
      out += text.slice(i, j + 1);
      i = j + 1;
    } else if (ch === '/' && next === '/') {
      while (i < text.length && text.charAt(i) !== '\n') i += 1;
    } else if (ch === '/' && next === '*') {
      const end = text.indexOf('*/', i + 2);
      i = end < 0 ? text.length : end + 2;
    } else {
      out += ch;
      i += 1;
    }
  }
  return out;
}

function isAppFile(rel: string): boolean {
  if (!rel.endsWith('.ts') && !rel.endsWith('.tsx')) return false;
  if (rel.endsWith('.test.ts')) return false;
  return !rel.startsWith('test/') && !rel.startsWith('test-types/');
}

function loadSource(rel: string): SourceFile {
  const raw = readFileSync(new URL(rel, SRC_URL), 'utf8');
  const text = rel.endsWith('.css') ? stripBlockComments(raw) : stripCodeComments(raw);
  return { rel, text };
}

function scan(files: SourceFile[], pattern: RegExp): string[] {
  const hits: string[] = [];
  for (const file of files) {
    const re = new RegExp(pattern.source, pattern.flags.includes('g') ? pattern.flags : `${pattern.flags}g`);
    for (const match of file.text.matchAll(re)) hits.push(`${file.rel}: ${match[0]}`);
  }
  return hits;
}

const allRels: string[] = [];
listSrcFiles(SRC_URL, '', allRels);
const appFiles: SourceFile[] = allRels.filter(isAppFile).map(loadSource);
const URL_PATTERN = /https?:\/\//;
const shippedFiles: SourceFile[] = [
  ...appFiles,
  loadSource('styles.css'),
  {
    rel: '../index.html',
    text: stripHtmlComments(readFileSync(new URL('../index.html', import.meta.url), 'utf8')),
  },
];

describe('source guards', () => {
  it('walks a non-empty app file list containing App.tsx and loader.ts', () => {
    const rels = appFiles.map((file) => file.rel);
    expect(rels.length).toBeGreaterThan(0);
    expect(rels).toContain('App.tsx');
    expect(rels).toContain('loader.ts');
  });

  // Requirements 10.1, 10.2: no external URLs in shipped files, no @import in styles or index.html.
  it('has no http(s) URLs in shipped files and no @import in styles or index.html', () => {
    const importScope = shippedFiles.filter(
      (file) => file.rel === 'styles.css' || file.rel === '../index.html',
    );
    expect([...scan(shippedFiles, URL_PATTERN), ...scan(importScope, /@import/)]).toEqual([]);
  });

  // Self-test: the narrowed URL guard still catches a URL in an app file, and ignores comments.
  it('URL guard self-test: flags an http(s) URL in an app file but not in a comment', () => {
    const fake: SourceFile = {
      rel: 'Fake.tsx',
      text: stripCodeComments(
        [
          '// see http://comment.example',
          "const a = 'https://x.example/a.json';",
          'const b = `http://y.example`;',
        ].join('\n'),
      ),
    };
    expect(scan([fake], URL_PATTERN)).toEqual(['Fake.tsx: https://', 'Fake.tsx: http://']);
  });

  it('scans app files, styles.css and index.html, and no test files', () => {
    const rels = shippedFiles.map((file) => file.rel);
    expect(rels).toContain('App.tsx');
    expect(rels).toContain('styles.css');
    expect(rels).toContain('../index.html');
    const testRels = rels.filter(
      (rel) => rel.endsWith('.test.ts') || rel.startsWith('test/') || rel.startsWith('test-types/'),
    );
    expect(testRels).toEqual([]);
  });

  // Requirement 10.1: network access only through App.tsx and loader.ts.
  it('calls fetch( only in App.tsx and loader.ts', () => {
    const others = appFiles.filter((file) => file.rel !== 'App.tsx' && file.rel !== 'loader.ts');
    expect(scan(others, /\bfetch\s*\(/)).toEqual([]);
  });

  // Requirement 10.5: no any in app code.
  it('has no any types in app files', () => {
    expect(scan(appFiles, /:\s*any\b|\bas\s+any\b|<any>|\bany\[\]/)).toEqual([]);
  });

  // Requirement 10.5: no non-null assertions in app code (!= and !== are not matched).
  it('has no non-null assertions in app files', () => {
    expect(scan(appFiles, /[\w)\]]!(?=[.);,\]])/)).toEqual([]);
  });

  // Requirement 10.5: no raw HTML injection.
  it('never uses dangerouslySetInnerHTML in app files', () => {
    expect(scan(appFiles, /dangerouslySetInnerHTML/)).toEqual([]);
  });

  // Requirement 10.7: no modal dialogs.
  it('has no alert, confirm, prompt or dialog in app files', () => {
    expect(scan(appFiles, /\b(?:alert|confirm|prompt)\s*\(|<dialog\b/)).toEqual([]);
  });

  // Requirement 10.4; design: the test-only node shim is never imported by app code.
  it('never references test-only modules or node: from app files', () => {
    expect(scan(appFiles, /test-types|node-fs\.d\.ts|\.\/test\/|\.\.\/test\/|node:/)).toEqual([]);
  });

  // Requirement 10.6: relative base so the build works on any Pages path.
  it("sets base: './' in vite.config.ts", () => {
    const config = readFileSync(new URL('../vite.config.ts', import.meta.url), 'utf8');
    expect(config).toContain("base: './'");
  });

  // Requirement 10.4: no dependency beyond the baseline.
  it('keeps package.json dependencies at the baseline', () => {
    const pkg: unknown = JSON.parse(readFileSync(new URL('../package.json', import.meta.url), 'utf8'));
    const keys = (field: string): string[] => {
      const section = (pkg as Record<string, unknown>)[field];
      return Object.keys((section ?? {}) as Record<string, unknown>).sort();
    };
    expect(keys('dependencies')).toEqual(['react', 'react-dom']);
    expect(keys('devDependencies')).toEqual([
      '@types/react',
      '@types/react-dom',
      '@vitejs/plugin-react',
      'typescript',
      'vite',
      'vitest',
    ]);
  });
});
