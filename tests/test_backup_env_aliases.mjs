import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';

const repoRoot = process.cwd();
const backupScript = path.join(repoRoot, 'deploy', 'backup.sh');

function writeExecutable(filePath, content) {
  fs.writeFileSync(filePath, content, 'utf8');
  fs.chmodSync(filePath, 0o755);
}

function runBackupStatus(envText) {
  const workDir = fs.mkdtempSync(path.join(os.tmpdir(), 'portal-backup-env-'));
  const binDir = path.join(workDir, 'bin');
  const envPath = path.join(workDir, '.env');
  fs.mkdirSync(binDir);
  fs.writeFileSync(
    path.join(workDir, 'backup.sh'),
    fs.readFileSync(backupScript, 'utf8').replace(/\r\n/g, '\n'),
    'utf8',
  );
  fs.writeFileSync(envPath, envText, 'utf8');
  writeExecutable(path.join(binDir, 'docker'), `#!/usr/bin/env bash
if [[ "$1" == "volume" && "$2" == "inspect" ]]; then
  exit 1
fi
if [[ "$1" == "ps" ]]; then
  exit 0
fi
exit 0
`);
  return spawnSync('bash', ['-lc', 'bash ./backup.sh status'], {
    cwd: workDir,
    encoding: 'utf8',
    env: {
      ...process.env,
      PATH: `${binDir}${path.delimiter}${process.env.PATH || ''}`,
    },
  });
}

test('backup script accepts legacy root password alias', () => {
  const result = runBackupStatus('GUAC_DB_ROOT_PASSWORD=xran\n');

  assert.equal(result.status, 0, result.stderr || result.stdout);
  assert.doesNotMatch(result.stdout + result.stderr, /未设置 MYSQL_ROOT_PASSWORD/i);
});

test('backup script accepts canonical root password variable', () => {
  const result = runBackupStatus('MYSQL_ROOT_PASSWORD=xran\n');

  assert.equal(result.status, 0, result.stderr || result.stdout);
  assert.doesNotMatch(result.stdout + result.stderr, /未设置 MYSQL_ROOT_PASSWORD/i);
});

test('backup script still fails when no root password is configured', () => {
  const result = runBackupStatus('TZ=Asia/Shanghai\n');

  assert.equal(result.status, 1);
  assert.match(result.stdout + result.stderr, /MYSQL_ROOT_PASSWORD 或 GUAC_DB_ROOT_PASSWORD/);
});
