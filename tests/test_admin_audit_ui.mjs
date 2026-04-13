import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';

const repoRoot = process.cwd();
const auditUiPath = path.join(repoRoot, 'frontend', 'js', 'admin-audit-ui.js');
const adminShellPath = path.join(repoRoot, 'frontend', 'js', 'admin.js');

function createElement(tagName) {
  return {
    tagName: String(tagName || '').toUpperCase(),
    children: [],
    style: {},
    className: '',
    textContent: '',
    value: '',
    colSpan: 1,
    onclick: null,
    appendChild(child) {
      this.children.push(child);
      return child;
    },
    set innerHTML(value) {
      this._innerHTML = String(value ?? '');
      if (this._innerHTML === '') this.children = [];
    },
    get innerHTML() {
      return this._innerHTML || '';
    },
  };
}

function createHarness(options = {}) {
  const elements = {
    'filter-username': { value: options.username || '' },
    'filter-action': { value: options.action || '' },
    'filter-date-start': { value: options.dateStart || '' },
    'filter-date-end': { value: options.dateEnd || '' },
    'audit-pagination': createElement('div'),
  };
  const auditTable = createElement('table');
  const auditTbody = createElement('tbody');
  auditTable.appendChild(auditTbody);
  elements['audit-table'] = auditTable;

  const toasts = [];
  const apiCalls = [];
  const apiImpl = options.apiImpl || (async () => ({ items: [], total: 0, page: 1, page_size: 20 }));

  const context = {
    document: {
      getElementById(id) {
        return Object.prototype.hasOwnProperty.call(elements, id) ? elements[id] : null;
      },
      querySelector(selector) {
        if (selector === '#audit-table tbody') return auditTbody;
        return null;
      },
      createElement,
    },
    async api(method, targetPath) {
      apiCalls.push({ method, targetPath });
      return apiImpl(method, targetPath);
    },
    showToast(message, tone) {
      toasts.push({ message, tone });
    },
    setTimeout,
    clearTimeout,
    window: null,
  };
  context.window = context;

  const source = fs.readFileSync(auditUiPath, 'utf8');
  vm.runInNewContext(source, context, { filename: auditUiPath });

  return {
    context,
    elements,
    auditTbody,
    toasts,
    apiCalls,
  };
}

test('AdminAuditUi exposes expected audit namespace members', () => {
  const harness = createHarness();
  const { AdminAuditUi } = harness.context;

  assert.equal(typeof AdminAuditUi, 'object');
  assert.equal(typeof AdminAuditUi.ACTION_LABELS, 'object');
  assert.equal(typeof AdminAuditUi.loadAuditLogs, 'function');
  assert.equal(typeof AdminAuditUi.renderAuditTable, 'function');
  assert.equal(typeof AdminAuditUi.renderAuditPagination, 'function');
  assert.equal(AdminAuditUi.ACTION_LABELS.login, '登录');
});

test('loadAuditLogs requests audit endpoint with filters and updates table/pagination', async () => {
  const harness = createHarness({
    username: ' alice ',
    action: 'login',
    dateStart: '2026-04-01',
    dateEnd: '2026-04-10',
    apiImpl: async () => ({
      items: [],
      total: 0,
      page: 1,
      page_size: 20,
    }),
  });

  await harness.context.AdminAuditUi.loadAuditLogs(3);

  assert.equal(harness.apiCalls.length, 1);
  assert.equal(harness.apiCalls[0].method, 'GET');
  assert.equal(
    harness.apiCalls[0].targetPath,
    '/audit-logs?page=3&page_size=20&username=alice&action=login&date_start=2026-04-01&date_end=2026-04-10',
  );
  assert.equal(harness.auditTbody.children.length, 1);
  assert.equal(harness.auditTbody.children[0].children[0].textContent, '暂无记录');
  assert.equal(harness.elements['audit-pagination'].children.length, 1);
  assert.equal(harness.elements['audit-pagination'].children[0].textContent, '第 1 / 1 页 (共 0 条)');
});

test('loadAuditLogs reports API errors via toast', async () => {
  const harness = createHarness({
    apiImpl: async () => {
      throw new Error('boom');
    },
  });

  await harness.context.AdminAuditUi.loadAuditLogs(1);

  assert.equal(harness.toasts.length, 1);
  assert.equal(harness.toasts[0].message, '加载审计日志失败: boom');
  assert.equal(harness.toasts[0].tone, 'error');
});

test('renderAuditTable maps action labels and fallback values', () => {
  const harness = createHarness();
  harness.context.AdminAuditUi.renderAuditTable([
    {
      created_at: '2026-04-12 10:00:00',
      username: 'admin',
      action: 'login',
      target_name: '',
      ip_address: '',
      detail: '',
    },
    {
      created_at: '2026-04-12 11:00:00',
      username: 'tester',
      action: 'custom_action',
      target_name: 'target-x',
      ip_address: '127.0.0.1',
      detail: 'ok',
    },
  ]);

  assert.equal(harness.auditTbody.children.length, 2);
  assert.equal(harness.auditTbody.children[0].children[2].textContent, '登录');
  assert.equal(harness.auditTbody.children[0].children[3].textContent, '-');
  assert.equal(harness.auditTbody.children[0].children[4].textContent, '-');
  assert.equal(harness.auditTbody.children[0].children[5].textContent, '-');
  assert.equal(harness.auditTbody.children[1].children[2].textContent, 'custom_action');
});

test('renderAuditPagination renders controls and buttons trigger page reload', async () => {
  const harness = createHarness({
    apiImpl: async () => ({ items: [], total: 40, page: 1, page_size: 20 }),
  });

  harness.context.AdminAuditUi.renderAuditPagination(60, 2, 20);
  assert.equal(harness.elements['audit-pagination'].children.length, 3);
  assert.equal(harness.elements['audit-pagination'].children[0].textContent, '上一页');
  assert.equal(harness.elements['audit-pagination'].children[1].textContent, '第 2 / 3 页 (共 60 条)');
  assert.equal(harness.elements['audit-pagination'].children[2].textContent, '下一页');

  const prevButton = harness.elements['audit-pagination'].children[0];
  const nextButton = harness.elements['audit-pagination'].children[2];

  prevButton.onclick();
  await new Promise((resolve) => setTimeout(resolve, 0));
  assert.equal(harness.apiCalls[0].targetPath, '/audit-logs?page=1&page_size=20');

  nextButton.onclick();
  await new Promise((resolve) => setTimeout(resolve, 0));
  assert.equal(harness.apiCalls[1].targetPath, '/audit-logs?page=3&page_size=20');
});

test('admin.js delegates audit operations to AdminAuditUi namespace', () => {
  const adminShellSource = fs.readFileSync(adminShellPath, 'utf8');

  assert.match(
    adminShellSource,
    /var\s+ACTION_LABELS\s*=\s*window\.AdminAuditUi\.ACTION_LABELS;/,
  );
  assert.match(
    adminShellSource,
    /var\s+loadAuditLogs\s*=\s*async\s+function\s*\(page\)\s*{\s*return\s+window\.AdminAuditUi\.loadAuditLogs\(page\);\s*};/,
  );
  assert.match(
    adminShellSource,
    /var\s+renderAuditTable\s*=\s*function\s*\(items\)\s*{\s*return\s+window\.AdminAuditUi\.renderAuditTable\(items\);\s*};/,
  );
  assert.match(
    adminShellSource,
    /var\s+renderAuditPagination\s*=\s*function\s*\(total,\s*page,\s*pageSize\)\s*{\s*return\s+window\.AdminAuditUi\.renderAuditPagination\(total,\s*page,\s*pageSize\);\s*};/,
  );
  assert.doesNotMatch(adminShellSource, /var\s+_auditPage\s*=\s*1;/);
});
