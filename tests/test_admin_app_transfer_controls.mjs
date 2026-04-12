import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';

const adminHtml = fs.readFileSync(path.join(process.cwd(), 'frontend', 'admin.html'), 'utf8');
const source = fs.readFileSync(path.join(process.cwd(), 'frontend', 'js', 'admin.js'), 'utf8');
const appModalSource = fs.readFileSync(path.join(process.cwd(), 'frontend', 'js', 'admin-app-modal-ui.js'), 'utf8');

function extractFunction(name) {
  const asyncMarker = `async function ${name}(`;
  const marker = `function ${name}(`;
  const asyncStart = source.indexOf(asyncMarker);
  const start = asyncStart >= 0 ? asyncStart : source.indexOf(marker);
  assert.notEqual(start, -1, `missing function ${name}`);
  const bodyStart = source.indexOf('{', start);
  assert.notEqual(bodyStart, -1, `missing function body ${name}`);

  let depth = 0;
  for (let i = bodyStart; i < source.length; i += 1) {
    const ch = source[i];
    if (ch === '{') depth += 1;
    if (ch === '}') depth -= 1;
    if (depth === 0) return source.slice(start, i + 1);
  }
  throw new Error(`unterminated function ${name}`);
}

const formatDurationFn = extractFunction('formatDuration');
const monitorStatusFn = extractFunction('buildMonitorSessionStatusMeta');
const monitorRowFn = extractFunction('buildMonitorSessionRowViewModel');
const monitorRowHtmlFn = extractFunction('buildMonitorSessionRowHtml');
const monitorTableActionFn = extractFunction('handleMonitorTableAction');

function createAdminAppUiContext(extraContext = {}) {
  const context = { ...extraContext };
  context.window = context;
  vm.runInNewContext(appModalSource, context);
  assert.ok(context.AdminAppUi, 'missing window.AdminAppUi namespace');
  return context;
}

function createSaveAppHarness(downloadPolicy, uploadPolicy) {
  const elements = {
    'app-color-depth': { value: '' },
    'app-name': { value: 'CFD 求解器' },
    'app-icon': { value: 'desktop' },
    'app-hostname': { value: 'rdp.example.local' },
    'app-port': { value: '3389' },
    'app-rdp-user': { value: 'tester' },
    'app-rdp-pass': { value: '' },
    'app-domain': { value: '' },
    'app-security': { value: 'nla' },
    'app-ignore-cert': { checked: true },
    'app-remote-app': { value: '' },
    'app-remote-dir': { value: '' },
    'app-remote-args': { value: '' },
    'app-disable-gfx': { checked: true },
    'app-resize-method': { value: 'display-update' },
    'app-enable-wallpaper': { checked: false },
    'app-enable-font-smoothing': { checked: true },
    'app-disable-copy': { checked: false },
    'app-disable-paste': { checked: false },
    'app-enable-audio': { checked: true },
    'app-enable-audio-input': { checked: false },
    'app-enable-printing': { checked: false },
    'app-disable-download': { value: downloadPolicy },
    'app-disable-upload': { value: uploadPolicy },
    'app-timezone': { value: '' },
    'app-keyboard-layout': { value: '' },
    'app-pool-id': { value: '2' },
    'app-member-max': { value: '1' },
    'app-script-enabled': { checked: false },
    'app-script-profile-key': { value: '' },
    'app-script-executor': { value: '' },
    'app-script-worker-group': { value: '' },
    'app-script-scratch-root': { value: '' },
    'app-script-python-executable': { value: '' },
    'app-script-python-env': { value: '' },
  };

  const apiCalls = [];
  const toasts = [];
  const context = {
    document: {
      getElementById(id) {
        return Object.prototype.hasOwnProperty.call(elements, id) ? elements[id] : null;
      },
    },
    parseInt,
    JSON,
    showToast(msg, type) {
      toasts.push({ msg, type });
    },
    closeModal() {},
    loadApps() {},
    async api(method, targetPath, payload) {
      apiCalls.push({ method, targetPath, payload });
      return {};
    },
  };

  context.window = context;
  vm.runInNewContext(appModalSource, context);
  return { context, apiCalls, toasts };
}

test('AdminAppUi exposes extracted app modal functions', () => {
  const context = createAdminAppUiContext();

  const requiredFunctions = [
    'loadApps',
    'renderAppsTable',
    'deleteApp',
    'normalizeTriStatePolicy',
    'buildTriStatePolicyOptions',
    'parseTriStatePolicy',
    'ensureWorkerGroupsLoaded',
    'ensureScriptProfilesLoaded',
    'findScriptProfile',
    'updateScriptProfileHint',
    'applySelectedScriptProfile',
    'showAppModal',
    'updateScriptBindingSummary',
    'saveApp',
  ];

  for (const fnName of requiredFunctions) {
    assert.equal(typeof context.AdminAppUi[fnName], 'function', `missing function ${fnName}`);
  }
});

test('admin shell wires app modal logic through AdminAppUi and script include', () => {
  assert.match(adminHtml, /js\/admin-app-modal-ui\.js/);
  assert.doesNotMatch(source, /async function showAppModal\s*\(/);
  assert.doesNotMatch(source, /async function saveApp\s*\(/);
  assert.doesNotMatch(source, /async function loadApps\s*\(/);
  assert.doesNotMatch(source, /function normalizeTriStatePolicy\s*\(/);
  assert.doesNotMatch(source, /function buildTriStatePolicyOptions\s*\(/);
  assert.doesNotMatch(source, /function parseTriStatePolicy\s*\(/);
  assert.doesNotMatch(source, /ensureScriptProfilesLoaded/);
  assert.match(source, /window\.AdminAppUi\.showAppModal/);
  assert.match(source, /window\.AdminAppUi\.saveApp/);
  assert.match(source, /window\.AdminAppUi\.loadApps/);
});

test('buildTriStatePolicyOptions returns selected tri-state option', () => {
  const context = createAdminAppUiContext();

  const inherit = context.AdminAppUi.buildTriStatePolicyOptions(null);
  assert.match(inherit, /<option value="" selected>继承全局<\/option>/);
  assert.match(inherit, /<option value="1">强制禁用<\/option>/);
  assert.match(inherit, /<option value="0">强制允许<\/option>/);

  const forceDisable = context.AdminAppUi.buildTriStatePolicyOptions(1);
  assert.match(forceDisable, /<option value="1" selected>强制禁用<\/option>/);

  const forceAllow = context.AdminAppUi.buildTriStatePolicyOptions(0);
  assert.match(forceAllow, /<option value="0" selected>强制允许<\/option>/);
});

test('parseTriStatePolicy maps empty/1/0 to null/1/0', () => {
  const context = createAdminAppUiContext();

  assert.equal(context.AdminAppUi.parseTriStatePolicy(''), null);
  assert.equal(context.AdminAppUi.parseTriStatePolicy('1'), 1);
  assert.equal(context.AdminAppUi.parseTriStatePolicy('0'), 0);
});

test('saveApp sends tri-state transfer policy payload values', async () => {
  const cases = [
    { input: ['', ''], expected: [null, null] },
    { input: ['1', '0'], expected: [1, 0] },
    { input: ['0', '1'], expected: [0, 1] },
  ];

  for (const entry of cases) {
    const { context, apiCalls, toasts } = createSaveAppHarness(entry.input[0], entry.input[1]);

    await context.AdminAppUi.saveApp(99);

    assert.equal(apiCalls.length, 2);
    assert.equal(apiCalls[0].method, 'PUT');
    assert.equal(apiCalls[0].targetPath, '/apps/99');
    assert.equal(apiCalls[0].payload.disable_download, entry.expected[0]);
    assert.equal(apiCalls[0].payload.disable_upload, entry.expected[1]);
    assert.equal(apiCalls[1].method, 'GET');
    assert.equal(apiCalls[1].targetPath, '/apps');
    assert.equal(toasts[0].msg, '应用已更新');
  }
});

test('buildMonitorSessionStatusMeta maps session statuses to truthful labels', () => {
  const context = {};
  vm.runInNewContext(monitorStatusFn, context);

  const active = context.buildMonitorSessionStatusMeta('active');
  assert.equal(active.label, '在线');
  assert.equal(active.tone, 'badge--active');
  assert.equal(active.reclaimable, true);

  const reclaimPending = context.buildMonitorSessionStatusMeta('reclaim_pending');
  assert.equal(reclaimPending.label, '回收中');
  assert.equal(reclaimPending.tone, 'badge--warning');
  assert.equal(reclaimPending.reclaimable, false);

  const reclaimed = context.buildMonitorSessionStatusMeta('reclaimed');
  assert.equal(reclaimed.label, '已回收');
  assert.equal(reclaimed.tone, 'badge--inactive');
  assert.equal(reclaimed.reclaimable, false);

  const disconnected = context.buildMonitorSessionStatusMeta('disconnected');
  assert.equal(disconnected.label, '已断开');
  assert.equal(disconnected.tone, 'badge--inactive');
  assert.equal(disconnected.reclaimable, false);

  const unknown = context.buildMonitorSessionStatusMeta('mystery_state');
  assert.equal(unknown.label, 'mystery_state');
  assert.equal(unknown.tone, 'badge--inactive');
  assert.equal(unknown.reclaimable, false);
  assert.match(source, /buildMonitorSessionStatusMeta\(session\.status\)/);
});

test('buildMonitorSessionRowViewModel converts raw monitor session into renderable row data', () => {
  const context = {};
  vm.runInNewContext(`${formatDurationFn}\n${monitorStatusFn}\n${monitorRowFn}`, context);

  const row = context.buildMonitorSessionRowViewModel({
    session_id: 'sid-1',
    display_name: '管理员',
    username: 'admin',
    app_name: '远程桌面',
    started_at: '2026-04-12 10:00:00',
    last_heartbeat: '2026-04-12 10:00:05',
    duration_seconds: 125,
    status: 'reclaim_pending',
  });

  assert.equal(row.sessionId, 'sid-1');
  assert.equal(row.userLabel, '管理员');
  assert.equal(row.appName, '远程桌面');
  assert.equal(row.startedAt, '2026-04-12 10:00:00');
  assert.equal(row.lastHeartbeat, '2026-04-12 10:00:05');
  assert.equal(row.durationText, '2m 5s');
  assert.equal(row.statusLabel, '回收中');
  assert.equal(row.statusTone, 'badge--warning');
  assert.equal(row.reclaimable, false);
  assert.match(source, /buildMonitorSessionRowViewModel\(session\)/);
});

test('buildMonitorSessionRowHtml renders truthful badge and reclaim action visibility', () => {
  const context = {
    escapeHtml(value) {
      return String(value)
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;')
        .replaceAll("'", '&#39;');
    },
    escapeAttr(value) {
      return String(value)
        .replaceAll('&', '&amp;')
        .replaceAll('"', '&quot;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;');
    },
  };
  vm.runInNewContext(`${formatDurationFn}\n${monitorStatusFn}\n${monitorRowFn}\n${monitorRowHtmlFn}`, context);

  const activeHtml = context.buildMonitorSessionRowHtml({
    session_id: 'sid-active',
    display_name: '管理员',
    username: 'admin',
    app_name: '远程桌面',
    started_at: '2026-04-12 10:00:00',
    last_heartbeat: '2026-04-12 10:00:05',
    duration_seconds: 5,
    status: 'active',
  });
  assert.match(activeHtml, /badge--active/);
  assert.match(activeHtml, />在线</);
  assert.match(activeHtml, /回收/);
  assert.match(activeHtml, /data-session-id="sid-active"/);
  assert.match(activeHtml, /data-action="reclaim-session"/);
  assert.doesNotMatch(activeHtml, /onclick=/);

  const reclaimingHtml = context.buildMonitorSessionRowHtml({
    session_id: 'sid-reclaiming',
    display_name: '管理员',
    username: 'admin',
    app_name: '远程桌面',
    started_at: '2026-04-12 10:00:00',
    last_heartbeat: '2026-04-12 10:00:05',
    duration_seconds: 125,
    status: 'reclaim_pending',
  });
  assert.match(reclaimingHtml, /badge--warning/);
  assert.match(reclaimingHtml, />回收中</);
  assert.doesNotMatch(reclaimingHtml, /btn btn--danger btn--small/);
  assert.match(source, /buildMonitorSessionRowHtml\(session\)/);
});

test('buildMonitorSessionRowHtml escapes data-session-id for attribute context', () => {
  const context = {
    escapeHtml(value) {
      return String(value)
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;');
    },
    escapeAttr(value) {
      return String(value)
        .replaceAll('&', '&amp;')
        .replaceAll('"', '&quot;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;');
    },
  };
  vm.runInNewContext(`${formatDurationFn}\n${monitorStatusFn}\n${monitorRowFn}\n${monitorRowHtmlFn}`, context);

  const html = context.buildMonitorSessionRowHtml({
    session_id: 'sid" autofocus onfocus="alert(1)&<',
    display_name: '管理员',
    username: 'admin',
    app_name: '远程桌面',
    started_at: '2026-04-12 10:00:00',
    last_heartbeat: '2026-04-12 10:00:05',
    duration_seconds: 5,
    status: 'active',
  });

  assert.match(
    html,
    /data-session-id="sid&quot; autofocus onfocus=&quot;alert\(1\)&amp;&lt;"/,
  );
});

test('handleMonitorTableAction delegates reclaim clicks by data-session-id', async () => {
  const calls = [];
  const button = {
    dataset: { action: 'reclaim-session', sessionId: 'sid-77' },
  };
  const event = {
    target: {
      closest(selector) {
        return selector === '[data-action="reclaim-session"]' ? button : null;
      },
    },
  };
  const context = {
    async reclaimSession(sessionId) {
      calls.push(sessionId);
    },
  };
  vm.runInNewContext(monitorTableActionFn, context);

  await context.handleMonitorTableAction(event);

  assert.deepEqual(calls, ['sid-77']);
  assert.doesNotMatch(source, /onclick="reclaimSession/);
});
