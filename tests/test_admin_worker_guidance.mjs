import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';

const repoRoot = process.cwd();
const adminHtmlPath = path.join(repoRoot, 'frontend', 'admin.html');
const workerUiJsPath = path.join(repoRoot, 'frontend', 'js', 'admin-worker-ui.js');

test('admin html includes worker guidance surface', () => {
  const html = fs.readFileSync(adminHtmlPath, 'utf8');

  assert.match(html, /Worker 配置向导/);
  assert.match(html, /节点组/);
  assert.match(html, /Worker 节点/);
  assert.match(html, /脚本应用绑定/);
  assert.match(html, /js\/admin-worker-ui\.js/);
});

test('admin worker ui module exposes worker helpers', () => {
  const source = fs.readFileSync(workerUiJsPath, 'utf8');
  const context = {
    window: {},
    document: {
      addEventListener() {},
      querySelector() { return null; },
      querySelectorAll() { return []; },
      getElementById() { return null; },
      createElement() {
        return {
          style: {},
          appendChild() {},
          setAttribute() {},
          classList: { toggle() {} },
        };
      },
      body: { appendChild() {} },
    },
    console,
    setTimeout() { return 0; },
    clearTimeout() {},
    setInterval() { return 0; },
    clearInterval() {},
    getToken() { return 'token'; },
    getUser() { return { is_admin: true, username: 'admin' }; },
    logout() {},
    fetch: async () => ({ ok: true, status: 200, json: async () => ({ items: [] }) }),
    escapeHtml(value) { return String(value ?? ''); },
    escapeAttr(value) { return String(value ?? ''); },
    ICON_MAP: {},
    confirm() { return true; },
  };
  context.window = context;

  vm.runInNewContext(source, context, { filename: workerUiJsPath });

  assert.equal(typeof context.AdminWorkerUi, 'object');
  assert.equal(typeof context.AdminWorkerUi.buildGuideCards, 'function');
  assert.equal(typeof context.AdminWorkerUi.renderWorkerGuide, 'function');
  assert.equal(typeof context.AdminWorkerUi.describeNodeReadiness, 'function');
  assert.equal(typeof context.AdminWorkerUi.loadWorkers, 'function');

  assert.equal(typeof context.AdminWorkerUx, 'object');
  assert.equal(typeof context.AdminWorkerUx.buildGuideCards, 'function');
  assert.equal(typeof context.AdminWorkerUx.describeNodeReadiness, 'function');
});

test('admin.js delegates worker concerns to AdminWorkerUi instead of defining them inline', () => {
  const source = fs.readFileSync(path.join(repoRoot, 'frontend', 'js', 'admin.js'), 'utf8');

  assert.doesNotMatch(source, /function buildGuideCards\s*\(/);
  assert.doesNotMatch(source, /function showWorkerGroupModal\s*\(/);
  assert.doesNotMatch(source, /async function loadWorkers\s*\(/);
  assert.match(source, /window\.AdminWorkerUi\.loadWorkers/);
  assert.match(source, /window\.AdminWorkerUi\.showWorkerGroupModal/);
});
