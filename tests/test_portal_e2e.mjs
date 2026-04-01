import fs from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';

import { chromium } from 'playwright';

const repoRoot = process.cwd();

function readEnvFile(filePath) {
  if (!fs.existsSync(filePath)) {
    return {};
  }

  const env = {};
  const text = fs.readFileSync(filePath, 'utf8');
  for (const rawLine of text.split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line || line.startsWith('#') || !line.includes('=')) {
      continue;
    }
    const [keyPart, ...valueParts] = line.split('=');
    const key = keyPart.trim();
    let value = valueParts.join('=').trim();
    if (value.length >= 2 && value[0] === value[value.length - 1] && (`"'`.includes(value[0]))) {
      value = value.slice(1, -1);
    }
    if (key) {
      env[key] = value;
    }
  }
  return env;
}

function resolveConfig(names, fallback) {
  const deployEnv = readEnvFile(path.join(repoRoot, 'deploy', '.env'));
  for (const source of [process.env, deployEnv]) {
    for (const name of names) {
      const value = source[name];
      if (value) {
        return value;
      }
    }
  }
  if (fallback !== undefined) {
    return fallback;
  }
  throw new Error(`missing required config: ${names.join(' / ')}`);
}

const BASE_URL = `http://127.0.0.1:${resolveConfig(['PORTAL_PORT'], '8880')}`;
const MYSQL_ROOT_PASSWORD = resolveConfig(['MYSQL_ROOT_PASSWORD', 'GUAC_DB_ROOT_PASSWORD']);
const MYSQL_ARGS = [
  'exec',
  '-i',
  'nercar-portal-guac-sql',
  'mysql',
  '-uroot',
  `-p${MYSQL_ROOT_PASSWORD}`,
  '--default-character-set=utf8mb4',
  '-N',
  '-B',
];

const E2E = {
  adminUsername: 'e2e_admin',
  adminPassword: 'E2E_admin_123!',
  adminHash: '$2b$12$fTo5s/L/v/ZR56NaMzTBzukuZcmnjMJ7bjdF10SY2z5hS9pbr5ZYi',
  adminDisplay: 'E2E 管理员',
  testUsername: 'e2e_user',
  testPassword: 'E2E_user_123!',
  testHash: '$2b$12$xou1nm.SnhktTYxZw4EMb.LW0vSxyj.NWsb6OXWQ5MfzRvkaQ.PwO',
  testDisplay: 'E2E 测试用户',
  notepadPoolName: 'E2E 池-记事本',
  calcPoolName: 'E2E 池-计算器',
  notepadAppName: 'E2E 记事本',
  calcAppName: 'E2E 计算器',
  notepadRemoteApp: '||notepad',
  calcRemoteApp: '||calc',
  rdpHost: '192.168.1.6',
  rdpPort: 3389,
  rdpUsername: 'e2e',
  rdpPassword: 'not-used',
  viewerDirName: '_e2e_viewer',
};

function sqlQuote(value) {
  return `'${String(value).replace(/'/g, "''")}'`;
}

function runMysql(sql) {
  const result = spawnSync('docker', MYSQL_ARGS, {
    input: sql,
    encoding: 'utf8',
  });
  if (result.status !== 0) {
    throw new Error(result.stderr || result.stdout || 'mysql failed');
  }
  return result.stdout;
}

function queryRows(sql) {
  const output = runMysql(`${sql}\n`);
  return output
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => line.split('\t'));
}

function queryScalar(sql) {
  const rows = queryRows(sql);
  return rows[0]?.[0] ?? '';
}

function deleteViewerData(userIds) {
  for (const userId of userIds.filter(Boolean)) {
    spawnSync(
      'docker',
      ['exec', '-i', 'nercar-portal-backend', 'python', '-'],
      {
        input: [
          'from pathlib import Path',
          'import shutil',
          `target = Path('/drive/portal_u${userId}/Output/${E2E.viewerDirName}')`,
          'if target.exists():',
          '    shutil.rmtree(target)',
        ].join('\n'),
        encoding: 'utf8',
      },
    );
  }
}

function cleanupData(snapshot = {}) {
  const usernameList = [E2E.adminUsername, E2E.testUsername].map(sqlQuote).join(', ');
  const appNameList = [E2E.notepadAppName, E2E.calcAppName].map(sqlQuote).join(', ');
  const poolNameList = [E2E.notepadPoolName, E2E.calcPoolName].map(sqlQuote).join(', ');

  const userRows = queryRows(`
USE guacamole_portal_db;
SELECT id, username FROM portal_user WHERE username IN (${usernameList});
`);
  const appRows = queryRows(`
USE guacamole_portal_db;
SELECT id, name FROM remote_app WHERE name IN (${appNameList});
`);
  const poolRows = queryRows(`
USE guacamole_portal_db;
SELECT id, name FROM resource_pool WHERE name IN (${poolNameList});
`);

  const userIds = userRows.map(([id]) => Number(id));
  const appIds = appRows.map(([id]) => Number(id));
  const poolIds = poolRows.map(([id]) => Number(id));
  const tokenUsernames = userIds.map((id) => sqlQuote(`portal_u${id}`));

  const userIdList = userIds.length ? userIds.join(', ') : 'NULL';
  const appIdList = appIds.length ? appIds.join(', ') : 'NULL';
  const poolIdList = poolIds.length ? poolIds.join(', ') : 'NULL';

  runMysql(`
USE guacamole_portal_db;
DELETE FROM active_session
WHERE user_id IN (${userIdList}) OR app_id IN (${appIdList});
DELETE FROM launch_queue
WHERE user_id IN (${userIdList})
   OR pool_id IN (${poolIdList})
   OR requested_app_id IN (${appIdList})
   OR assigned_app_id IN (${appIdList});
DELETE FROM remote_app_acl
WHERE user_id IN (${userIdList}) OR app_id IN (${appIdList});
${tokenUsernames.length ? `DELETE FROM token_cache WHERE username IN (${tokenUsernames.join(', ')});` : ''}
DELETE FROM remote_app WHERE id IN (${appIdList});
DELETE FROM resource_pool WHERE id IN (${poolIdList});
DELETE FROM portal_user WHERE id IN (${userIdList});
`);

  const cleanupIds = new Set(userIds);
  if (snapshot.adminUserId) {
    cleanupIds.add(snapshot.adminUserId);
  }
  deleteViewerData([...cleanupIds]);
}

function prepareData() {
  cleanupData();

  runMysql(`
USE guacamole_portal_db;
INSERT INTO portal_user (username, password_hash, display_name, is_admin, is_active)
VALUES
  (${sqlQuote(E2E.adminUsername)}, ${sqlQuote(E2E.adminHash)}, ${sqlQuote(E2E.adminDisplay)}, 1, 1),
  (${sqlQuote(E2E.testUsername)}, ${sqlQuote(E2E.testHash)}, ${sqlQuote(E2E.testDisplay)}, 0, 1);
INSERT INTO resource_pool
  (name, icon, max_concurrent, auto_dispatch_enabled, dispatch_grace_seconds, stale_timeout_seconds, idle_timeout_seconds, is_active)
VALUES
  (${sqlQuote(E2E.notepadPoolName)}, 'edit', 1, 1, 120, 120, NULL, 1),
  (${sqlQuote(E2E.calcPoolName)}, 'calculate', 2, 1, 120, 120, NULL, 1);
`);

  const adminUserId = Number(queryScalar(`
USE guacamole_portal_db;
SELECT id FROM portal_user WHERE username = ${sqlQuote(E2E.adminUsername)};
`));
  const testUserId = Number(queryScalar(`
USE guacamole_portal_db;
SELECT id FROM portal_user WHERE username = ${sqlQuote(E2E.testUsername)};
`));
  const notepadPoolId = Number(queryScalar(`
USE guacamole_portal_db;
SELECT id FROM resource_pool WHERE name = ${sqlQuote(E2E.notepadPoolName)};
`));
  const calcPoolId = Number(queryScalar(`
USE guacamole_portal_db;
SELECT id FROM resource_pool WHERE name = ${sqlQuote(E2E.calcPoolName)};
`));

  runMysql(`
USE guacamole_portal_db;
INSERT INTO remote_app
  (name, icon, hostname, port, rdp_username, rdp_password, remote_app, pool_id, member_max_concurrent)
VALUES
  (${sqlQuote(E2E.notepadAppName)}, 'edit', ${sqlQuote(E2E.rdpHost)}, ${E2E.rdpPort}, ${sqlQuote(E2E.rdpUsername)}, ${sqlQuote(E2E.rdpPassword)}, ${sqlQuote(E2E.notepadRemoteApp)}, ${notepadPoolId}, 1),
  (${sqlQuote(E2E.calcAppName)}, 'calculate', ${sqlQuote(E2E.rdpHost)}, ${E2E.rdpPort}, ${sqlQuote(E2E.rdpUsername)}, ${sqlQuote(E2E.rdpPassword)}, ${sqlQuote(E2E.calcRemoteApp)}, ${calcPoolId}, 2);
`);

  const notepadAppId = Number(queryScalar(`
USE guacamole_portal_db;
SELECT id FROM remote_app WHERE name = ${sqlQuote(E2E.notepadAppName)};
`));
  const calcAppId = Number(queryScalar(`
USE guacamole_portal_db;
SELECT id FROM remote_app WHERE name = ${sqlQuote(E2E.calcAppName)};
`));

  runMysql(`
USE guacamole_portal_db;
INSERT INTO remote_app_acl (user_id, app_id)
VALUES
  (${adminUserId}, ${notepadAppId}),
  (${adminUserId}, ${calcAppId}),
  (${testUserId}, ${notepadAppId}),
  (${testUserId}, ${calcAppId});
DELETE FROM token_cache
WHERE username IN (${sqlQuote(`portal_u${adminUserId}`)}, ${sqlQuote(`portal_u${testUserId}`)});
`);

  const seed = spawnSync(
    'docker',
    ['exec', '-i', 'nercar-portal-backend', 'python', '-'],
    {
      input: [
        'from pathlib import Path',
        'from vtkmodules.vtkCommonCore import vtkPoints',
        'from vtkmodules.vtkCommonDataModel import vtkTetra, vtkUnstructuredGrid',
        'from vtkmodules.vtkIOXML import vtkXMLUnstructuredGridWriter',
        `root = Path('/drive/portal_u${adminUserId}/Output/${E2E.viewerDirName}')`,
        'root.mkdir(parents=True, exist_ok=True)',
        "(root / 'mesh.obj').write_text('o e2e\\n', encoding='utf-8')",
        "file_path = root / 'sample.vtu'",
        'points = vtkPoints()',
        'points.InsertNextPoint(0.0, 0.0, 0.0)',
        'points.InsertNextPoint(1.0, 0.0, 0.0)',
        'points.InsertNextPoint(0.0, 1.0, 0.0)',
        'points.InsertNextPoint(0.0, 0.0, 1.0)',
        'tetra = vtkTetra()',
        'for idx in range(4): tetra.GetPointIds().SetId(idx, idx)',
        'grid = vtkUnstructuredGrid()',
        'grid.SetPoints(points)',
        'grid.InsertNextCell(tetra.GetCellType(), tetra.GetPointIds())',
        'writer = vtkXMLUnstructuredGridWriter()',
        'writer.SetFileName(str(file_path))',
        'writer.SetInputData(grid)',
        'writer.Write()',
      ].join('\n'),
      encoding: 'utf8',
    },
  );
  if (seed.status !== 0) {
    throw new Error(seed.stderr || seed.stdout || 'seed failed');
  }

  return {
    adminUserId,
    testUserId,
    notepadAppId,
    calcAppId,
  };
}

async function login(page, username, password) {
  await page.goto(`${BASE_URL}/login.html`, { waitUntil: 'networkidle' });
  await page.fill('#username', username);
  await page.fill('#password', password);
  await Promise.all([
    page.waitForURL((url) => !url.toString().includes('/login.html'), { timeout: 15000 }),
    page.click('button[type=submit]'),
  ]);
}

async function main() {
  const snapshot = prepareData();
  let browser;

  try {
    browser = await chromium.launch({ headless: true });
    const adminCtx = await browser.newContext({ viewport: { width: 1440, height: 960 } });
    const testCtx = await browser.newContext({ viewport: { width: 1440, height: 960 } });
    const adminPage = await adminCtx.newPage();
    const testPage = await testCtx.newPage();
    const artifacts = { consoleErrors: [], pageErrors: [], failedRequests: [] };

    for (const page of [adminPage, testPage]) {
      page.on('console', (msg) => {
        if (msg.type() === 'error') artifacts.consoleErrors.push(msg.text());
      });
      page.on('pageerror', (err) => {
        artifacts.pageErrors.push({ message: err.message, stack: err.stack });
      });
      page.on('requestfailed', (req) => {
        artifacts.failedRequests.push(`${req.method()} ${req.url()} :: ${req.failure() ? req.failure().errorText : 'unknown'}`);
      });
    }

    await login(adminPage, E2E.adminUsername, E2E.adminPassword);
    await adminPage.waitForSelector('.app-card');
    const portal = {
      title: await adminPage.title(),
      appCardCount: await adminPage.locator('.app-card').count(),
      userText: await adminPage.locator('#user-display-name').innerText(),
    };

    await Promise.all([
      adminPage.waitForResponse((resp) => resp.url().includes('/api/files/list?path=') && resp.status() === 200),
      adminPage.evaluate(() => switchPortalTab('files')),
    ]);
    await adminPage.waitForTimeout(1000);
    await Promise.all([
      adminPage.waitForResponse((resp) => resp.url().includes('/api/files/list?path=Output') && resp.status() === 200),
      adminPage.locator('span.files-table__name').filter({ hasText: 'Output' }).first().click(),
    ]);
    await adminPage.locator('span.files-table__name').filter({ hasText: E2E.viewerDirName }).first().click();
    await adminPage.fill('#files-search', 'sample');
    await adminPage.check('#files-group-ext');
    await adminPage.waitForTimeout(500);
    const fileTree = {
      groupHeaders: await adminPage.locator('.files-group-header td').allInnerTexts(),
      rows: await adminPage.locator('#files-table tbody tr').allInnerTexts(),
      hasViewButton: await adminPage.locator('button', { hasText: '查看' }).count(),
    };

    await adminPage.goto(`${BASE_URL}/viewer.html?path=${E2E.viewerDirName}/sample.vtu`, { waitUntil: 'networkidle' });
    await adminPage.waitForTimeout(4000);
    const viewer = {
      datasetPath: await adminPage.locator('#dataset-path').innerText(),
      modelInfo: await adminPage.locator('#model-info').innerText(),
      statusBarVisible: await adminPage.locator('#status-bar').isVisible(),
    };

    await login(testPage, E2E.testUsername, E2E.testPassword);
    await testPage.waitForSelector('.app-card');
    const popupNotepadPromise = testPage.waitForEvent('popup', { timeout: 15000 });
    await testPage.locator('.app-card').filter({ hasText: E2E.notepadPoolName }).first().click();
    const popupNotepad = await popupNotepadPromise;
    await popupNotepad.waitForTimeout(3000);

    const popupCalcPromise = testPage.waitForEvent('popup', { timeout: 15000 });
    await testPage.locator('.app-card').filter({ hasText: E2E.calcPoolName }).first().click();
    const popupCalc = await popupCalcPromise;
    await popupCalc.waitForTimeout(4000);

    adminPage.on('dialog', async (dialog) => { await dialog.accept(); });
    await adminPage.goto(`${BASE_URL}/admin.html`, { waitUntil: 'networkidle' });
    await adminPage.waitForTimeout(2500);
    await adminPage.click('[data-tab="pools"]');
    await adminPage.waitForTimeout(1500);
    const poolUsageCount = await adminPage.locator('.pool-usage').count();
    await adminPage.click('[data-tab="monitor"]');
    await adminPage.waitForTimeout(1500);

    const rows = adminPage.locator('#monitor-table tbody tr');
    const count = await rows.count();
    let calcRow = null;
    for (let i = 0; i < count; i += 1) {
      const row = rows.nth(i);
      const text = await row.innerText();
      if (text.includes(E2E.testDisplay) && text.includes(E2E.calcAppName)) {
        calcRow = row;
        break;
      }
    }
    if (!calcRow) {
      throw new Error('calculator monitor row not found');
    }
    await calcRow.getByRole('button', { name: '回收' }).click();

    let calcClosed = false;
    try {
      await popupCalc.waitForEvent('close', { timeout: 25000 });
      calcClosed = true;
    } catch {
      calcClosed = false;
    }

    await popupNotepad.waitForTimeout(2000);
    const reclaim = {
      calcClosed,
      notepadStillOpen: !popupNotepad.isClosed(),
    };

    const sessionResult = runMysql(`
USE guacamole_portal_db;
SELECT app_id, status, COALESCE(reclaim_reason, '') AS reclaim_reason
FROM active_session
WHERE user_id = ${snapshot.testUserId}
ORDER BY id DESC
LIMIT 5;
`);
    const sessionRows = sessionResult
      .split(/\r?\n/)
      .map((line) => line.trim())
      .filter(Boolean)
      .map((line) => line.split('\t'));
    const calcReclaimed = sessionRows.some(
      (row) => Number(row[0]) === snapshot.calcAppId && row[1] === 'disconnected' && row[2] === 'admin',
    );
    const notepadActive = sessionRows.some(
      (row) => Number(row[0]) === snapshot.notepadAppId && row[1] === 'active',
    );

    const summary = { portal, fileTree, viewer, poolUsageCount, reclaim, calcReclaimed, notepadActive, artifacts };
    console.log(JSON.stringify(summary, null, 2));

    if (artifacts.consoleErrors.length || artifacts.pageErrors.length || artifacts.failedRequests.length) {
      throw new Error('browser artifacts contain errors');
    }
    if (!portal.appCardCount) {
      throw new Error('portal app cards missing');
    }
    if (!portal.userText.includes(E2E.adminDisplay)) {
      throw new Error('portal admin identity missing');
    }
    if (!fileTree.groupHeaders.some((label) => label.toLowerCase() === '.vtu')) {
      throw new Error('file tree did not group VTU results');
    }
    if (!fileTree.hasViewButton) {
      throw new Error('file tree did not expose viewer action');
    }
    if (!viewer.statusBarVisible) {
      throw new Error('viewer did not load model');
    }
    if (!viewer.modelInfo.includes('sample.vtu')) {
      throw new Error('viewer did not load VTU preview');
    }
    if (!poolUsageCount) {
      throw new Error('admin pool usage UI missing');
    }
    if (!reclaim.calcClosed || !reclaim.notepadStillOpen) {
      throw new Error('reclaim behavior regression');
    }
    if (!calcReclaimed || !notepadActive) {
      throw new Error('database session state regression');
    }
  } finally {
    if (browser) {
      await browser.close();
    }
    cleanupData(snapshot);
  }
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
