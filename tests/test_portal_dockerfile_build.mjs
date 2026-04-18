import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const repoRoot = path.resolve(__dirname, '..');
const dockerfilePath = path.join(repoRoot, 'deploy', 'portal.Dockerfile');
const dockerignorePath = path.join(repoRoot, '.dockerignore');

test('portal docker image rebuilds viewer bundle from source', () => {
  const dockerfile = fs.readFileSync(dockerfilePath, 'utf8');

  assert.match(dockerfile, /COPY package\.json package-lock\.json \.\//);
  assert.match(dockerfile, /npm ci/);
  assert.match(dockerfile, /npm run build:viewer/);
});

test('portal docker image rebuilds vue portal shell from source', () => {
  const dockerfile = fs.readFileSync(dockerfilePath, 'utf8');

  assert.match(dockerfile, /COPY portal_ui\/package\.json portal_ui\/package-lock\.json \.\/portal_ui\//);
  assert.match(dockerfile, /npm --prefix portal_ui ci/);
  assert.match(dockerfile, /COPY portal_ui\/ \.\/portal_ui\//);
  assert.match(dockerfile, /npm --prefix portal_ui run build/);
  assert.match(dockerfile, /COPY --from=viewer-builder \/app\/frontend\/portal \.\/frontend\/portal/);
});

test('portal docker image starts backend via python entrypoint', () => {
  const dockerfile = fs.readFileSync(dockerfilePath, 'utf8');

  assert.match(dockerfile, /CMD \["python", "backend\/app\.py"\]/);
  assert.doesNotMatch(dockerfile, /CMD \["uvicorn", "backend\.app:app"/);
});

test('docker build ignores local portal_ui node_modules and built assets', () => {
  const dockerignore = fs.readFileSync(dockerignorePath, 'utf8');

  assert.match(dockerignore, /^portal_ui\/node_modules\/?$/m);
  assert.match(dockerignore, /^frontend\/portal\/?$/m);
});
