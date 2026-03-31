import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { build } from 'esbuild';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const repoRoot = path.resolve(__dirname, '..');

const entry = path.join(repoRoot, 'frontend', 'js', 'viewer.js');
const outfile = path.join(repoRoot, 'frontend', 'js', 'viewer.bundle.js');

await build({
  entryPoints: [entry],
  outfile,
  bundle: true,
  format: 'esm',
  target: ['chrome118'],
  charset: 'utf8',
  logLevel: 'info',
});
