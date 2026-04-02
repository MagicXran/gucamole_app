import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const repoRoot = path.resolve(__dirname, '..');
const dockerfilePath = path.join(repoRoot, 'deploy', 'portal.Dockerfile');

test('portal docker image rebuilds viewer bundle from source', () => {
  const dockerfile = fs.readFileSync(dockerfilePath, 'utf8');

  assert.match(dockerfile, /COPY package\.json package-lock\.json \.\//);
  assert.match(dockerfile, /npm ci/);
  assert.match(dockerfile, /npm run build:viewer/);
});

test('portal docker image starts backend via python entrypoint', () => {
  const dockerfile = fs.readFileSync(dockerfilePath, 'utf8');

  assert.match(dockerfile, /CMD \["python", "backend\/app\.py"\]/);
  assert.doesNotMatch(dockerfile, /CMD \["uvicorn", "backend\.app:app"/);
});
