import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';

const repoRoot = process.cwd();
const composePath = path.join(repoRoot, 'deploy', 'docker-compose.yml');

function renderConfig(envText) {
  const envDir = fs.mkdtempSync(path.join(os.tmpdir(), 'portal-env-'));
  const envPath = path.join(envDir, '.env');
  fs.writeFileSync(envPath, envText, 'utf8');
  const result = spawnSync('docker', [
    'compose',
    '--env-file',
    envPath,
    '-f',
    composePath,
    'config',
  ], {
    cwd: repoRoot,
    encoding: 'utf8',
  });
  if (result.status !== 0) {
    throw new Error(result.stderr || result.stdout || 'docker compose config failed');
  }
  return result.stdout;
}

test('legacy root env aliases still resolve compose secrets', () => {
  const rendered = renderConfig([
    'TZ=Asia/Shanghai',
    'PORTAL_PORT=8880',
    'GUAC_DB_ROOT_PASSWORD=xran',
    'GUAC_DB_PASSWORD=xran',
    'GUACAMOLE_JSON_SECRET_KEY=4c0b569e4c96df157eee1b65dd0e4d41',
  ].join('\n'));

  assert.match(rendered, /MYSQL_DATABASE: guacamole_db/);
  assert.match(rendered, /MYSQL_ROOT_PASSWORD: xran/);
  assert.match(rendered, /MYSQL_USER: guacamole_user/);
  assert.match(rendered, /MYSQL_PASSWORD: xran/);
  assert.match(rendered, /JSON_SECRET_KEY: 4c0b569e4c96df157eee1b65dd0e4d41/);
  assert.match(rendered, /GUACD_LOG_LEVEL: info/);
  assert.match(rendered, /PORTAL_DB_PASSWORD: xran/);
  // Hardening: no repo-shipped JWT secret fallback; legacy secret vars can still satisfy it.
  assert.match(rendered, /PORTAL_JWT_SECRET: 4c0b569e4c96df157eee1b65dd0e4d41/);
});

test('canonical env names still work too', () => {
  const rendered = renderConfig([
    'TZ=Asia/Shanghai',
    'PORTAL_PORT=8880',
    'MYSQL_ROOT_PASSWORD=abcd',
    'MYSQL_PASSWORD=efgh',
    'MYSQL_USER=guacamole_user',
    'MYSQL_DATABASE=guacamole_db',
    'JSON_SECRET_KEY=00112233445566778899aabbccddeeff',
  ].join('\n'));

  assert.match(rendered, /MYSQL_ROOT_PASSWORD: abcd/);
  assert.match(rendered, /MYSQL_PASSWORD: efgh/);
  assert.match(rendered, /MYSQL_USER: guacamole_user/);
  assert.match(rendered, /MYSQL_DATABASE: guacamole_db/);
  assert.match(rendered, /JSON_SECRET_KEY: 00112233445566778899aabbccddeeff/);
  assert.match(rendered, /GUACD_LOG_LEVEL: info/);
  assert.match(rendered, /PORTAL_JWT_SECRET: 00112233445566778899aabbccddeeff/);
});

test('PORTAL_JWT_SECRET still wins when explicitly configured', () => {
  const rendered = renderConfig([
    'TZ=Asia/Shanghai',
    'PORTAL_PORT=8880',
    'MYSQL_ROOT_PASSWORD=abcd',
    'MYSQL_PASSWORD=efgh',
    'MYSQL_USER=guacamole_user',
    'MYSQL_DATABASE=guacamole_db',
    'JSON_SECRET_KEY=00112233445566778899aabbccddeeff',
    'PORTAL_JWT_SECRET=jwt_override_value',
  ].join('\n'));

  assert.match(rendered, /PORTAL_JWT_SECRET: jwt_override_value/);
});
