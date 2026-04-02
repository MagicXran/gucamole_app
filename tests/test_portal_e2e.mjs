import { chromium } from 'playwright';
import fs from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';

const repoRoot = process.cwd();
const deployRoot = path.join(repoRoot, 'deploy');
const deployEnvPath = path.join(deployRoot, '.env');

function readDotEnv(filePath) {
  if (!fs.existsSync(filePath)) {
    return {};
  }
  const values = {};
  const content = fs.readFileSync(filePath, 'utf8');
  for (const rawLine of content.split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line || line.startsWith('#')) {
      continue;
    }
    const separatorIndex = line.indexOf('=');
    if (separatorIndex <= 0) {
      continue;
    }
    const key = line.slice(0, separatorIndex).trim();
    const value = line.slice(separatorIndex + 1).trim();
    values[key] = value;
  }
  return values;
}

const deployEnv = readDotEnv(deployEnvPath);
const portalPort = process.env.PORTAL_PORT || deployEnv.PORTAL_PORT || '8880';
const BASE_URL = process.env.PORTAL_BASE_URL || `http://127.0.0.1:${portalPort}`;
const PORTAL_INSTANCE_ID = process.env.PORTAL_INSTANCE_ID || deployEnv.PORTAL_INSTANCE_ID || '';
const MYSQL_ROOT_PASSWORD =
  process.env.MYSQL_ROOT_PASSWORD
  || process.env.GUAC_DB_ROOT_PASSWORD
  || deployEnv.MYSQL_ROOT_PASSWORD
  || deployEnv.GUAC_DB_ROOT_PASSWORD
  || 'xran';

function composeArgs(args) {
  const base = ['compose'];
  if (fs.existsSync(deployEnvPath)) {
    base.push('--env-file', deployEnvPath);
  }
  if (PORTAL_INSTANCE_ID) {
    base.push('--project-name', PORTAL_INSTANCE_ID);
  }
  return [...base, ...args];
}

function runCompose(args, options = {}) {
  const result = spawnSync('docker', composeArgs(args), {
    cwd: deployRoot,
    encoding: 'utf8',
    env: process.env,
    ...options,
  });
  if (result.status !== 0) {
    throw new Error(result.stderr || result.stdout || 'docker compose command failed');
  }
  return result.stdout;
}

const MYSQL_ARGS = [
  'exec',
  '-T',
  'guac-sql',
  'mysql',
  '-uroot',
  `-p${MYSQL_ROOT_PASSWORD}`,
  '--default-character-set=utf8mb4',
  '-N',
  '-B',
];

function runMysql(sql) {
  return runCompose(MYSQL_ARGS, { input: sql });
}

function queryRows(sql) {
  const output = runMysql(`${sql}\n`);
  return output
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => line.split('\t'));
}

function prepareData() {
  const [[poolMaxConcurrent = '1']] = queryRows(`
USE guacamole_portal_db;
SELECT max_concurrent FROM resource_pool WHERE id = 2;
`);
  const [[memberMaxConcurrent = '1']] = queryRows(`
USE guacamole_portal_db;
SELECT member_max_concurrent FROM remote_app WHERE id = 2;
`);
  const aclRows = queryRows(`
USE guacamole_portal_db;
SELECT COUNT(*) FROM remote_app_acl WHERE user_id = 2 AND app_id = 2;
`);
  const [[aclCount = '0']] = aclRows;

  runMysql(`
USE guacamole_portal_db;
UPDATE resource_pool SET max_concurrent = 2 WHERE id = 2;
UPDATE remote_app SET member_max_concurrent = 2 WHERE id = 2;
INSERT IGNORE INTO remote_app_acl (user_id, app_id) VALUES (2, 2);
UPDATE active_session
SET status='disconnected', ended_at=NOW(), reclaim_reason=NULL
WHERE user_id = 2 AND status IN ('active', 'reclaim_pending');
DELETE FROM token_cache WHERE username='portal_u2';
`);

  runCompose(
    ['exec', '-T', 'portal-backend', 'python', '-'],
    {
      input: [
        'from pathlib import Path',
        'from vtkmodules.vtkCommonCore import vtkPoints',
        'from vtkmodules.vtkCommonDataModel import vtkTetra, vtkUnstructuredGrid',
        'from vtkmodules.vtkIOXML import vtkXMLUnstructuredGridWriter',
        "root = Path('/drive/portal_u1/Output/_e2e_viewer')",
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
    },
  );

  return {
    poolMaxConcurrent,
    memberMaxConcurrent,
    aclInserted: aclCount === '0',
  };
}

function cleanupData(snapshot) {
  runMysql(`
USE guacamole_portal_db;
UPDATE resource_pool SET max_concurrent = ${Number(snapshot.poolMaxConcurrent)} WHERE id = 2;
UPDATE remote_app SET member_max_concurrent = ${Number(snapshot.memberMaxConcurrent)} WHERE id = 2;
${snapshot.aclInserted ? 'DELETE FROM remote_app_acl WHERE user_id = 2 AND app_id = 2;' : ''}
UPDATE active_session
SET status='disconnected', ended_at=NOW(), reclaim_reason=NULL
WHERE user_id = 2 AND status IN ('active', 'reclaim_pending');
DELETE FROM token_cache WHERE username='portal_u2';
`);
  runCompose(
    ['exec', '-T', 'portal-backend', 'python', '-'],
    {
      input: [
        'from pathlib import Path',
        "Path('/drive/portal_u1/Output/_e2e_viewer').mkdir(parents=True, exist_ok=True)",
        "target = Path('/drive/portal_u1/Output/_e2e_viewer')",
        'if target.exists():',
        '    import shutil',
        '    shutil.rmtree(target)',
      ].join('\n'),
    },
  );
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
  const browser = await chromium.launch({ headless: true });
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

  try {
    await login(adminPage, 'admin', 'admin123');
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
    await adminPage.locator('span.files-table__name').filter({ hasText: '_e2e_viewer' }).first().click();
    await adminPage.fill('#files-search', 'sample');
    await adminPage.check('#files-group-ext');
    await adminPage.waitForTimeout(500);
    const fileTree = {
      groupHeaders: await adminPage.locator('.files-group-header td').allInnerTexts(),
      rows: await adminPage.locator('#files-table tbody tr').allInnerTexts(),
      hasViewButton: await adminPage.locator('button', { hasText: '查看' }).count(),
    };

    await adminPage.goto(`${BASE_URL}/viewer.html?path=_e2e_viewer/sample.vtu`, { waitUntil: 'networkidle' });
    await adminPage.waitForTimeout(4000);
    const viewer = {
      datasetPath: await adminPage.locator('#dataset-path').innerText(),
      modelInfo: await adminPage.locator('#model-info').innerText(),
      statusBarVisible: await adminPage.locator('#status-bar').isVisible(),
    };

    await login(testPage, 'test', 'test123');
    await testPage.waitForSelector('.app-card');
    const popupNotepadPromise = testPage.waitForEvent('popup', { timeout: 15000 });
    await testPage.locator('.app-card').filter({ hasText: '记事本' }).first().click();
    const popupNotepad = await popupNotepadPromise;
    await popupNotepad.waitForTimeout(3000);

    const popupCalcPromise = testPage.waitForEvent('popup', { timeout: 15000 });
    await testPage.locator('.app-card').filter({ hasText: '计算器' }).first().click();
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
      if (text.includes('测试用户') && text.includes('计算器')) {
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

    const sessionOutput = runCompose(MYSQL_ARGS, {
      input: `
USE guacamole_portal_db;
SELECT app_id, status, COALESCE(reclaim_reason, '') AS reclaim_reason
FROM active_session
WHERE user_id = 2
ORDER BY id DESC
LIMIT 5;
`,
    });
    const sessionRows = sessionOutput
      .split(/\r?\n/)
      .map((line) => line.trim())
      .filter(Boolean)
      .map((line) => line.split('\t'));
    const calcReclaimed = sessionRows.some((row) => row[0] === '2' && row[1] === 'disconnected' && row[2] === 'admin');
    const notepadActive = sessionRows.some((row) => row[0] === '1' && row[1] === 'active');

    const summary = { portal, fileTree, viewer, poolUsageCount, reclaim, calcReclaimed, notepadActive, artifacts };
    console.log(JSON.stringify(summary, null, 2));

    if (artifacts.consoleErrors.length || artifacts.pageErrors.length || artifacts.failedRequests.length) {
      throw new Error('browser artifacts contain errors');
    }
    if (!portal.appCardCount) {
      throw new Error('portal app cards missing');
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
    await browser.close();
    cleanupData(snapshot);
  }
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
