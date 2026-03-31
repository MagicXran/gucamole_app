import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const repoRoot = path.resolve(__dirname, '..');
const buildScript = path.join(repoRoot, 'scripts', 'build-viewer-bundle.mjs');
const bundlePath = path.join(repoRoot, 'frontend', 'js', 'viewer.bundle.js');
const viewerHtmlPath = path.join(repoRoot, 'frontend', 'viewer.html');

test('viewer bundle can be rebuilt from source', () => {
  const result = spawnSync(process.execPath, [buildScript], {
    cwd: repoRoot,
    encoding: 'utf8',
  });

  assert.equal(result.status, 0, result.stderr || result.stdout);
  assert.ok(fs.existsSync(bundlePath), 'viewer bundle should exist after build');
  assert.ok(fs.statSync(bundlePath).size > 1024, 'viewer bundle should not be empty');

  const viewerHtml = fs.readFileSync(viewerHtmlPath, 'utf8');
  assert.match(viewerHtml, /js\/viewer\.bundle\.js/, 'viewer page should load the built bundle');
});
