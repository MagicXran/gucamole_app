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

function createBackupFixture(baseDir) {
  const fixtureDir = fs.mkdtempSync(path.join(baseDir, 'portal-backup-fixture-'));
  fs.writeFileSync(path.join(fixtureDir, 'portal_dump.sql'), 'CREATE DATABASE x;\n', 'utf8');
  const driveDir = path.join(fixtureDir, 'drive');
  fs.mkdirSync(driveDir);
  fs.writeFileSync(path.join(driveDir, 'file.txt'), 'hello', 'utf8');
  const tarResult = spawnSync('bash', ['-lc', 'tar czf drive_files.tar.gz -C drive .'], {
    cwd: fixtureDir,
    encoding: 'utf8',
  });
  if (tarResult.status !== 0) {
    throw new Error(tarResult.stderr || tarResult.stdout || 'tar failed');
  }
  const checksumResult = spawnSync('bash', ['-lc', 'sha256sum portal_dump.sql drive_files.tar.gz > SHA256SUMS'], {
    cwd: fixtureDir,
    encoding: 'utf8',
  });
  if (checksumResult.status !== 0) {
    throw new Error(checksumResult.stderr || checksumResult.stdout || 'sha256sum failed');
  }
  return fixtureDir;
}

function wslPath(p) {
  const normalized = path.resolve(p).replace(/\\/g, '/');
  return `/mnt/${normalized[0].toLowerCase()}${normalized.slice(2)}`;
}

function setupScriptHarness(envText, extraBins = {}) {
  const workDir = fs.mkdtempSync(path.join(os.tmpdir(), 'portal-backup-verify-'));
  const binDir = path.join(workDir, 'bin');
  fs.mkdirSync(binDir);
  fs.writeFileSync(
    path.join(workDir, 'backup.sh'),
    fs.readFileSync(backupScript, 'utf8').replace(/\r\n/g, '\n'),
    'utf8',
  );
  fs.writeFileSync(path.join(workDir, '.env'), envText, 'utf8');
  for (const [name, content] of Object.entries(extraBins)) {
    writeExecutable(path.join(binDir, name), content);
  }
  return { workDir, binDir };
}

test('backup verify succeeds for a complete fixture', () => {
  const { workDir, binDir } = setupScriptHarness('MYSQL_ROOT_PASSWORD=xran\n');
  const fixtureDir = createBackupFixture(workDir);

  const result = spawnSync('bash', ['-lc', `bash ./backup.sh verify "${path.basename(fixtureDir)}"`], {
    cwd: workDir,
    encoding: 'utf8',
    env: {
      ...process.env,
      PATH: `${binDir}${path.delimiter}${process.env.PATH || ''}`,
      PORTAL_PYTHON_BIN: path.join(repoRoot, '.venv', 'Scripts', 'python.exe'),
      PORTAL_SCHEMA_VERIFY_SCRIPT: path.join(repoRoot, 'scripts', 'verify_portal_schema.py'),
    },
  });

  assert.equal(result.status, 0, result.stderr || result.stdout);
  assert.match(result.stdout + result.stderr, /backup verify ok/);
});

test('backup verify fails when portal dump is missing', () => {
  const { workDir, binDir } = setupScriptHarness('MYSQL_ROOT_PASSWORD=xran\n');
  const fixtureDir = fs.mkdtempSync(path.join(workDir, 'portal-backup-missing-'));

  const result = spawnSync('bash', ['-lc', `bash ./backup.sh verify "${path.basename(fixtureDir)}"`], {
    cwd: workDir,
    encoding: 'utf8',
    env: {
      ...process.env,
      PATH: `${binDir}${path.delimiter}${process.env.PATH || ''}`,
    },
  });

  assert.equal(result.status, 1);
  assert.match(result.stdout + result.stderr, /portal_dump\.sql/);
});

test('backup drill runs temp restore flow and schema verification', () => {
  const { workDir, binDir } = setupScriptHarness('MYSQL_ROOT_PASSWORD=xran\n');
  const fixtureDir = createBackupFixture(workDir);
  const drillPort = String(34000 + Math.floor(Math.random() * 1000));
  const scriptsDir = path.join(workDir, 'scripts');
  fs.mkdirSync(scriptsDir);
  fs.writeFileSync(
    path.join(scriptsDir, 'verify_portal_schema.py'),
    [
      'from pathlib import Path',
      "Path('schema_probe_ran').write_text('ok', encoding='utf-8')",
      "print('schema ok')",
    ].join('\n'),
    'utf8',
  );
  const pythonBin = wslPath(path.join(repoRoot, '.venv', 'Scripts', 'python.exe'));

  const result = spawnSync('bash', ['-lc', `export PORTAL_DRILL_DB_PORT=${drillPort}; export PORTAL_PYTHON_BIN="${pythonBin}"; export PORTAL_SCHEMA_VERIFY_SCRIPT="./scripts/verify_portal_schema.py"; bash ./backup.sh drill "${path.basename(fixtureDir)}"`], {
    cwd: workDir,
    encoding: 'utf8',
    env: {
      ...process.env,
      PATH: `${binDir}${path.delimiter}${process.env.PATH || ''}`,
    },
  });

  assert.equal(result.status, 0, result.stderr || result.stdout);
  assert.match(result.stdout + result.stderr, /backup drill ok/);
  assert.equal(fs.readFileSync(path.join(workDir, 'schema_probe_ran'), 'utf8'), 'ok');
});
