import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join, relative, resolve } from 'node:path';

import { describe, expect, it } from 'vitest';

const ROOT = resolve(__dirname, '..');
const HEX_RE = /#[0-9a-fA-F]{3,8}\b/;

const ALLOW_FILES = new Set<string>([
  'lib/tokens.ts',
  'features/import/types.ts',
  'lib/no-hex.test.ts',
]);

const SKIP_DIRS = new Set<string>(['node_modules', '__snapshots__']);

function walk(dir: string): string[] {
  const out: string[] = [];
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry);
    const st = statSync(full);
    if (st.isDirectory()) {
      if (SKIP_DIRS.has(entry)) continue;
      out.push(...walk(full));
    } else if (/\.(ts|tsx)$/.test(entry)) {
      out.push(full);
    }
  }
  return out;
}

describe('no hex colour literals outside tokens.ts', () => {
  const offenders: string[] = [];
  for (const file of walk(ROOT)) {
    const rel = relative(ROOT, file).replace(/\\/g, '/');
    if (ALLOW_FILES.has(rel)) continue;
    const content = readFileSync(file, 'utf-8');
    if (HEX_RE.test(content)) offenders.push(rel);
  }

  it.each(offenders.length > 0 ? offenders : ['(none)'])(
    'file %s should not contain hex colours',
    (file) => {
      expect(file).toBe('(none)');
    },
  );
});
