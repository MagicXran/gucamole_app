import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';

const repoRoot = process.cwd();
const backupScript = path.join(repoRoot, 'deploy', 'backup.sh');
const composeFile = path.join(repoRoot, 'deploy', 'docker-compose.yml');

function writeExecutable(filePath, content) {
  fs.writeFileSync(filePath, content, 'utf8');
  fs.chmodSync(filePath, 0o755);
}

function runBackupCommand(envText, command = 'status') {
  const workDir = fs.mkdtempSync(path.join(os.tmpdir(), 'portal-backup-env-'));
  const binDir = path.join(workDir, 'bin');
  const bashBinDir = binDir.replace(/\\/g, '/');
  const envPath = path.join(workDir, '.env');
  const dockerLogPath = path.join(workDir, 'docker.log');
  fs.mkdirSync(binDir);
  fs.writeFileSync(
    path.join(workDir, 'backup.sh'),
    fs.readFileSync(backupScript, 'utf8').replace(/\r\n/g, '\n'),
    'utf8',
  );
  fs.writeFileSync(
    path.join(workDir, 'docker-compose.yml'),
    fs.readFileSync(composeFile, 'utf8').replace(/\r\n/g, '\n'),
    'utf8',
  );
  fs.writeFileSync(envPath, envText, 'utf8');
  writeExecutable(path.join(binDir, 'docker'), `#!/usr/bin/env bash
printf '%s\\n' "$*" >> "${dockerLogPath.replace(/\\/g, '/')}"
if [[ "$1" == "compose" && "$*" == *"ps"* && "$*" == *"-q"* && "$*" == *"guac-sql"* ]]; then
  printf 'cid-guac-sql\\n'
  exit 0
fi
if [[ "$1" == "compose" && "$*" == *"ps"* && "$*" == *"-q"* && "$*" == *"portal-backend"* ]]; then
  printf 'cid-portal-backend\\n'
  exit 0
fi
if [[ "$1" == "inspect" && "$2" == "cid-guac-sql" ]]; then
  printf 'volume|portal-test_mysql_data|/var/lib/docker/volumes/portal-test_mysql_data/_data\\n'
  exit 0
fi
if [[ "$1" == "inspect" && "$2" == "cid-portal-backend" ]]; then
  printf 'bind||/srv/portal-test/drive\\n'
  exit 0
fi
if [[ "$1" == "run" ]]; then
  printf '12K\\t/data\\n'
  exit 0
fi
if [[ "$1" == "compose" && "$*" == *"ps"* && "$*" == *"--format"* ]]; then
  printf 'portal-backend\\tUp\\nguac-sql\\tUp\\n'
  exit 0
fi
exit 0
`);
  fs.writeFileSync(
    path.join(binDir, 'docker.cmd'),
    '@echo off\r\nbash "%~dp0docker" %*\r\n',
    'utf8',
  );
  const result = spawnSync('bash', ['-lc', `bash ./backup.sh ${command}`], {
    cwd: workDir,
    encoding: 'utf8',
    env: {
      ...process.env,
      PATH: `${bashBinDir}:${process.env.PATH || ''}`,
    },
  });
  return {
    ...result,
    dockerLog: fs.existsSync(dockerLogPath) ? fs.readFileSync(dockerLogPath, 'utf8') : '',
  };
}

test('backup script accepts legacy root password alias', () => {
  const result = runBackupCommand('GUAC_DB_ROOT_PASSWORD=xran\n');

  assert.equal(result.status, 0, result.stderr || result.stdout);
  assert.doesNotMatch(result.stdout + result.stderr, /未设置 MYSQL_ROOT_PASSWORD/i);
});

test('backup script accepts canonical root password variable', () => {
  const result = runBackupCommand('MYSQL_ROOT_PASSWORD=xran\n');

  assert.equal(result.status, 0, result.stderr || result.stdout);
  assert.doesNotMatch(result.stdout + result.stderr, /未设置 MYSQL_ROOT_PASSWORD/i);
});

test('backup script trims CRLF env values before using passwords', () => {
  const result = runBackupCommand('MYSQL_ROOT_PASSWORD=xran\r\nTZ=Asia/Shanghai\r\n');

  assert.equal(result.status, 0, result.stderr || result.stdout);
  assert.doesNotMatch(result.stdout + result.stderr, /未设置 MYSQL_ROOT_PASSWORD/i);
});

test('backup script still fails when no root password is configured', () => {
  const result = runBackupCommand('TZ=Asia/Shanghai\n');

  assert.equal(result.status, 1);
  assert.match(result.stdout + result.stderr, /MYSQL_ROOT_PASSWORD 或 GUAC_DB_ROOT_PASSWORD/);
});

test('backup script derives compose project and mount sources instead of fixed container or volume names', () => {
  const source = fs.readFileSync(backupScript, 'utf8');

  assert.match(source, /--project-name "\$PORTAL_INSTANCE_ID"/);
  assert.match(source, /resolve_mount_binding/);
  assert.match(source, /inspect_mount_binding/);
  assert.doesNotMatch(source, /MYSQL_CONTAINER="nercar-portal-guac-sql"/);
  assert.doesNotMatch(source, /MYSQL_VOLUME="guacamole_mysql_data"/);
  assert.doesNotMatch(source, /DRIVE_VOLUME="guacamole_guacd_drive"/);
});

test('backup script falls back across shared drive services instead of pinning to portal-backend', () => {
  const source = fs.readFileSync(backupScript, 'utf8');

  assert.match(source, /resolve_drive_mount_binding/);
  assert.match(source, /portal-backend guacd nginx/);
  assert.doesNotMatch(source, /resolve_mount_binding "portal-backend" "\/drive"/);
});
