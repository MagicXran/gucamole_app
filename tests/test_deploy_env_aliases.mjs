import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';

const repoRoot = process.cwd();
const composePath = path.join(repoRoot, 'deploy', 'docker-compose.yml');
const debugComposePath = path.join(repoRoot, 'deploy', 'docker-compose.debug.yml');

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

function renderDebugConfig(envText) {
  const envDir = fs.mkdtempSync(path.join(os.tmpdir(), 'portal-debug-env-'));
  const envPath = path.join(envDir, '.env');
  fs.writeFileSync(envPath, envText, 'utf8');
  const result = spawnSync('docker', [
    'compose',
    '--env-file',
    envPath,
    '-f',
    composePath,
    '-f',
    debugComposePath,
    'config',
  ], {
    cwd: repoRoot,
    encoding: 'utf8',
  });
  if (result.status !== 0) {
    throw new Error(result.stderr || result.stdout || 'docker compose debug config failed');
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
  assert.match(rendered, /PORTAL_DB_PASSWORD: xran/);
});

test('canonical env names still work too', () => {
  const rendered = renderConfig([
    'TZ=Asia/Shanghai',
    'PORTAL_PORT=8880',
    'PORTAL_INSTANCE_ID=portal-main',
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
});

test('instance id drives compose project name without fixed container names or volume aliases', () => {
  const rendered = renderConfig([
    'TZ=Asia/Shanghai',
    'PORTAL_PORT=8880',
    'PORTAL_INSTANCE_ID=portal-feature-a',
    'MYSQL_ROOT_PASSWORD=abcd',
    'MYSQL_PASSWORD=efgh',
    'JSON_SECRET_KEY=00112233445566778899aabbccddeeff',
  ].join('\n'));

  assert.match(rendered, /^name: portal-feature-a$/m);
  assert.doesNotMatch(rendered, /container_name:/);
  assert.doesNotMatch(rendered, /name: guacamole_/);
  assert.doesNotMatch(rendered, /name: nercar-portal-/);
});

test('compose accepts server bind mounts for mysql data and drive mounts', () => {
  const rendered = renderConfig([
    'TZ=Asia/Shanghai',
    'PORTAL_PORT=8880',
    'PORTAL_INSTANCE_ID=portal-prod-a',
    'MYSQL_ROOT_PASSWORD=abcd',
    'MYSQL_PASSWORD=efgh',
    'JSON_SECRET_KEY=00112233445566778899aabbccddeeff',
    'MYSQL_DATA_SOURCE=/srv/portal-a/mysql',
    'GUAC_DRIVE_SOURCE=/srv/portal-a/drive',
  ].join('\n'));

  assert.match(rendered, /source: \/srv\/portal-a\/mysql/);
  assert.match(rendered, /target: \/var\/lib\/mysql/);
  assert.match(rendered, /source: \/srv\/portal-a\/drive/);
  assert.match(rendered, /target: \/drive/);
});

test('compose keeps the development MySQL host port fixed by default', () => {
  const rendered = renderConfig([
    'TZ=Asia/Shanghai',
    'PORTAL_PORT=8880',
    'PORTAL_INSTANCE_ID=portal-feature-b',
    'MYSQL_ROOT_PASSWORD=abcd',
    'MYSQL_PASSWORD=efgh',
    'JSON_SECRET_KEY=00112233445566778899aabbccddeeff',
  ].join('\n'));

  assert.match(rendered, /published: "33060"/);
});

test('compose still supports an explicit MySQL host port when requested', () => {
  const rendered = renderConfig([
    'TZ=Asia/Shanghai',
    'PORTAL_PORT=8880',
    'PORTAL_INSTANCE_ID=portal-feature-c',
    'MYSQL_ROOT_PASSWORD=abcd',
    'MYSQL_PASSWORD=efgh',
    'MYSQL_HOST_PORT=33160',
    'JSON_SECRET_KEY=00112233445566778899aabbccddeeff',
  ].join('\n'));

  assert.match(rendered, /published: "33160"/);
});

test('compose supports binding portal port to a specific host IP', () => {
  const rendered = renderConfig([
    'TZ=Asia/Shanghai',
    'PORTAL_PORT=8880',
    'PORTAL_BIND_IP=192.168.56.25',
    'PORTAL_INSTANCE_ID=portal-feature-d',
    'MYSQL_ROOT_PASSWORD=abcd',
    'MYSQL_PASSWORD=efgh',
    'JSON_SECRET_KEY=00112233445566778899aabbccddeeff',
  ].join('\n'));

  assert.match(rendered, /host_ip: 192\.168\.56\.25/);
  assert.match(rendered, /published: "8880"/);
  assert.match(rendered, /target: 80/);
});

test('guacd uses LOG_LEVEL and avoids deprecated GUACD_LOG_LEVEL env', () => {
  const rendered = renderConfig([
    'TZ=Asia/Shanghai',
    'PORTAL_PORT=8880',
    'PORTAL_INSTANCE_ID=portal-feature-loglevel',
    'MYSQL_ROOT_PASSWORD=abcd',
    'MYSQL_PASSWORD=efgh',
    'JSON_SECRET_KEY=00112233445566778899aabbccddeeff',
  ].join('\n'));

  assert.match(rendered, /LOG_LEVEL: info/);
  assert.doesNotMatch(rendered, /GUACD_LOG_LEVEL:/);
});

test('debug compose does not override external nginx binding', () => {
  const rendered = renderDebugConfig([
    'TZ=Asia/Shanghai',
    'PORTAL_PORT=8880',
    'PORTAL_BIND_IP=192.168.56.25',
    'PORTAL_INSTANCE_ID=portal-debug-a',
    'MYSQL_ROOT_PASSWORD=abcd',
    'MYSQL_PASSWORD=efgh',
    'JSON_SECRET_KEY=00112233445566778899aabbccddeeff',
  ].join('\n'));

  assert.match(rendered, /host_ip: 192\.168\.56\.25/);
  assert.match(rendered, /published: "8880"/);
  assert.doesNotMatch(rendered, /published: "18880"/);
});

test('portal e2e script avoids fixed container identities', () => {
  const e2eSource = fs.readFileSync(path.join(repoRoot, 'tests', 'test_portal_e2e.mjs'), 'utf8');

  assert.doesNotMatch(e2eSource, /nercar-portal-/);
  assert.doesNotMatch(e2eSource, /guacamole_(mysql_data|guacd_drive)/);
  assert.match(e2eSource, /['"]compose['"]/);
  assert.match(e2eSource, /['"]guac-sql['"]/);
  assert.match(e2eSource, /['"]portal-backend['"]/);
});
