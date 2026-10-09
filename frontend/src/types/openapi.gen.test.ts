// @vitest-environment node
import { execFileSync } from 'node:child_process';
import { mkdtempSync, readFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { describe, it, expect } from 'vitest';

describe('Generated API types (Task 1.3)', () => {
  it('match the committed api/openapi.json', () => {
    const out = join(mkdtempSync(join(tmpdir(), 'openapi-')), 'openapi.gen.ts');
    execFileSync('npx', ['openapi-typescript', '../api/openapi.json', '-o', out], { stdio: 'ignore' });

    expect(readFileSync('src/types/openapi.gen.ts', 'utf-8'), 'run `npm run generate-client`').toBe(
      readFileSync(out, 'utf-8'),
    );
  });
});
