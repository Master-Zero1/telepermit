// Test-only typing for node:fs (no @types/node is installed). Never imported by app code.
declare module 'node:fs' {
  export function readFileSync(path: URL, encoding: 'utf8'): string;
  export function readdirSync(path: URL): string[];
}
