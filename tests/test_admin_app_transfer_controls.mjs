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

function createElement(initial = {}) {
  return {
    value: '',
    checked: false,
    disabled: false,
    innerHTML: '',
    textContent: '',
    onsubmit: null,
    onclick: null,
    _listeners: {},
    addEventListener(type, handler) {
      this._listeners[type] = handler;
    },
    dispatch(type) {
      if (this._listeners[type]) {
        this._listeners[type]({ target: this });
      }
    },
    ...initial,
  };
}

function escapeHtml(value) {
  return String(value)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

function escapeAttr(value) {
  return String(value)
    .replaceAll('&', '&amp;')
    .replaceAll('"', '&quot;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;');
}

function formGroup(label, id, value = '', type = 'text', required = false, placeholder = '') {
  const req = required ? ' required' : '';
  const ph = placeholder ? ` placeholder="${escapeAttr(placeholder)}"` : '';
  return `<div class="form-group"><label for="${id}">${escapeHtml(label)}</label><input type="${type}" id="${id}" value="${escapeAttr(value)}"${req}${ph}></div>`;
}

function formGroupSelect(label, id, options, selected) {
  const optionHtml = options.map((option) => {
    const value = typeof option === 'string' ? option : option.value;
    const text = typeof option === 'string' ? option : option.label;
    const selectedAttr = value === selected ? ' selected' : '';
    return `<option value="${escapeAttr(value)}"${selectedAttr}>${escapeHtml(text)}</option>`;
  }).join('');
  return `<div class="form-group"><label for="${id}">${escapeHtml(label)}</label><select id="${id}">${optionHtml}</select></div>`;
}

function createModalHarness(options = {}) {
  const apiCalls = [];
  const toasts = [];
  const elements = {};
  const poolId = options.poolId ?? 7;

  function registerModalElements(html) {
    for (const match of html.matchAll(/id="([^"]+)"/g)) {
      const id = match[1];
      if (!Object.prototype.hasOwnProperty.call(elements, id)) {
        elements[id] = createElement();
      }
      const escapedId = id.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
      const valueMatch = html.match(new RegExp(`id="${escapedId}"[^>]*value="([^"]*)"`, 'm'));
      if (valueMatch) {
        elements[id].value = valueMatch[1]
          .replaceAll('&quot;', '"')
          .replaceAll('&amp;', '&')
          .replaceAll('&lt;', '<')
          .replaceAll('&gt;', '>');
      }
      elements[id].checked = new RegExp(`id="${escapedId}"[^>]*checked`, 'm').test(html);
    }
  }

  const modalContainer = createElement();
  Object.defineProperty(modalContainer, 'innerHTML', {
    configurable: true,
    enumerable: true,
    get() {
      return this._innerHTML || '';
    },
    set(value) {
      this._innerHTML = value;
      registerModalElements(value);
    },
  });
  elements['modal-container'] = modalContainer;

  const context = {
    _pools: options.pools || [],
    document: {
      getElementById(id) {
        return Object.prototype.hasOwnProperty.call(elements, id) ? elements[id] : null;
      },
    },
    parseInt,
    JSON,
    confirm() {
      return true;
    },
    escapeHtml,
    escapeAttr,
    formGroup,
    formGroupSelect,
    closeModal() {},
    loadApps() {},
    showToast(msg, type) {
      toasts.push({ msg, type });
    },
    async api(method, targetPath, payload) {
      apiCalls.push({ method, targetPath, payload });
      if (method === 'GET' && targetPath === '/pools') {
        return options.poolList || [{ id: poolId, name: '共享资源池' }];
      }
      if (method === 'GET' && targetPath === '/workers/groups') {
        return options.workerGroupsResponse || { items: options.workerGroups || [] };
      }
      if (method === 'GET' && targetPath === '/script-profiles') {
        return options.scriptProfilesResponse || { items: options.scriptProfiles || [] };
      }
      if (method === 'GET' && targetPath === `/pools/${poolId}/attachments`) {
        return options.attachmentsResponse || {
          pool_id: poolId,
          tutorial_docs: [],
          video_resources: [],
          plugin_downloads: [],
        };
      }
      return {};
    },
  };

  context.ensurePoolsLoaded = async function ensurePoolsLoaded() {
    if (context._pools.length) return;
    context._pools = await context.api('GET', '/pools');
  };

  context.window = context;
  vm.runInNewContext(appModalSource, context);
  return { context, apiCalls, toasts, elements };
}

function createSaveAppHarness(downloadPolicy, uploadPolicy, options = {}) {
  const elements = {
    'app-color-depth': { value: '' },
    'app-name': { value: 'CFD 求解器' },
    'app-icon': { value: 'desktop' },
    'app-kind': { value: options.appKind || 'commercial_software' },
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
    'loadPoolAttachmentEditors',
    'savePoolAttachments',
    'clearPoolAttachments',
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

test('showAppModal renders app_kind selector and backfills current value', async () => {
  const { context, elements } = createModalHarness();

  await context.AdminAppUi.showAppModal({
    id: 99,
    name: 'Fluent',
    icon: 'desktop',
    app_kind: 'compute_tool',
    hostname: 'rdp.example.local',
    port: 3389,
    pool_id: 7,
    member_max_concurrent: 1,
    ignore_cert: true,
    is_active: true,
  });

  const html = elements['modal-container'].innerHTML;
  assert.match(html, /id="app-kind"/);
  assert.match(html, /<option value="commercial_software">商业软件<\/option>/);
  assert.match(html, /<option value="simulation_app">仿真APP<\/option>/);
  assert.match(html, /<option value="compute_tool" selected>计算工具<\/option>/);
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

test('saveApp sends selected app_kind in payload', async () => {
  const { context, apiCalls } = createSaveAppHarness('', '', { appKind: 'simulation_app' });

  await context.AdminAppUi.saveApp(77);

  assert.equal(apiCalls[0].payload.app_kind, 'simulation_app');
});

test('showAppModal loads pool attachment editors for current pool', async () => {
  const { context, apiCalls, elements } = createModalHarness({
    attachmentsResponse: {
      pool_id: 7,
      tutorial_docs: [{ id: 1, title: '用户手册', summary: 'PDF', link_url: 'https://example/doc', sort_order: 0 }],
      video_resources: [{ id: 2, title: '演示视频', summary: 'MP4', link_url: 'https://example/video', sort_order: 1 }],
      plugin_downloads: [{ id: 3, title: '插件包', summary: 'ZIP', link_url: 'https://example/plugin', sort_order: 2 }],
    },
  });

  await context.AdminAppUi.showAppModal({
    id: 99,
    name: 'Fluent',
    icon: 'desktop',
    app_kind: 'commercial_software',
    hostname: 'rdp.example.local',
    port: 3389,
    pool_id: 7,
    member_max_concurrent: 1,
    ignore_cert: true,
    is_active: true,
  });

  assert.ok(
    apiCalls.some((call) => call.method === 'GET' && call.targetPath === '/pools/7/attachments'),
    'showAppModal should load current pool attachments',
  );
  assert.match(elements['modal-container'].innerHTML, /资源池共享附件/);
  assert.equal(
    elements['pool-attachment-tutorial-docs'].value,
    '用户手册 | PDF | https://example/doc',
  );
  assert.equal(
    elements['pool-attachment-video-resources'].value,
    '演示视频 | MP4 | https://example/video',
  );
  assert.equal(
    elements['pool-attachment-plugin-downloads'].value,
    '插件包 | ZIP | https://example/plugin',
  );
});

test('savePoolAttachments parses textarea editors and sends grouped payload', async () => {
  const { context, apiCalls, toasts, elements } = createModalHarness();
  elements['pool-attachment-tutorial-docs'] = createElement({
    value: '用户手册 | PDF | https://example/doc\n二号手册 | https://example/doc-2',
  });
  elements['pool-attachment-video-resources'] = createElement({
    value: '演示视频 | MP4 | https://example/video',
  });
  elements['pool-attachment-plugin-downloads'] = createElement({
    value: '插件包 | ZIP | https://example/plugin',
  });
  elements['pool-attachment-status'] = createElement();

  await context.AdminAppUi.savePoolAttachments(7);

  assert.deepEqual(JSON.parse(JSON.stringify(apiCalls[0])), {
    method: 'PUT',
    targetPath: '/pools/7/attachments',
    payload: {
      tutorial_docs: [
        { title: '用户手册', summary: 'PDF', link_url: 'https://example/doc', sort_order: 0 },
        { title: '二号手册', summary: '', link_url: 'https://example/doc-2', sort_order: 1 },
      ],
      video_resources: [
        { title: '演示视频', summary: 'MP4', link_url: 'https://example/video', sort_order: 0 },
      ],
      plugin_downloads: [
        { title: '插件包', summary: 'ZIP', link_url: 'https://example/plugin', sort_order: 0 },
      ],
    },
  });
  assert.equal(toasts[0].msg, '资源池附件已保存');
});

test('savePoolAttachments surfaces malformed attachment rows with toast and skips api write', async () => {
  const { context, apiCalls, toasts, elements } = createModalHarness();
  elements['pool-attachment-tutorial-docs'] = createElement({
    value: '只有标题没有链接',
  });
  elements['pool-attachment-video-resources'] = createElement({ value: '' });
  elements['pool-attachment-plugin-downloads'] = createElement({ value: '' });
  elements['pool-attachment-status'] = createElement();

  const result = await context.AdminAppUi.savePoolAttachments(7);

  assert.equal(result, null);
  assert.equal(apiCalls.length, 0);
  assert.match(elements['pool-attachment-status'].textContent, /格式不对|缺标题或链接/);
  assert.match(toasts[0].msg, /格式不对|缺标题或链接/);
});

test('clearPoolAttachments empties editors and persists empty groups', async () => {
  const { context, apiCalls, elements } = createModalHarness();
  elements['pool-attachment-tutorial-docs'] = createElement({ value: '用户手册 | PDF | https://example/doc' });
  elements['pool-attachment-video-resources'] = createElement({ value: '演示视频 | MP4 | https://example/video' });
  elements['pool-attachment-plugin-downloads'] = createElement({ value: '插件包 | ZIP | https://example/plugin' });
  elements['pool-attachment-status'] = createElement();

  await context.AdminAppUi.clearPoolAttachments(7);

  assert.equal(elements['pool-attachment-tutorial-docs'].value, '');
  assert.equal(elements['pool-attachment-video-resources'].value, '');
  assert.equal(elements['pool-attachment-plugin-downloads'].value, '');
  assert.deepEqual(JSON.parse(JSON.stringify(apiCalls[0])), {
    method: 'PUT',
    targetPath: '/pools/7/attachments',
    payload: {
      tutorial_docs: [],
      video_resources: [],
      plugin_downloads: [],
    },
  });
});

test('changing pool selection does not retarget attachment writes before app save', async () => {
  const { context, apiCalls, elements } = createModalHarness({
    poolList: [
      { id: 7, name: '原始资源池' },
      { id: 11, name: '新资源池' },
    ],
    attachmentsResponse: {
      pool_id: 7,
      tutorial_docs: [{ id: 1, title: '原始手册', summary: '', link_url: 'https://example/original', sort_order: 0 }],
      video_resources: [],
      plugin_downloads: [],
    },
  });

  await context.AdminAppUi.showAppModal({
    id: 99,
    name: 'Fluent',
    icon: 'desktop',
    app_kind: 'commercial_software',
    hostname: 'rdp.example.local',
    port: 3389,
    pool_id: 7,
    member_max_concurrent: 1,
    ignore_cert: true,
    is_active: true,
  });

  elements['app-pool-id'].value = '11';
  elements['app-pool-id'].dispatch('change');
  assert.match(elements['pool-attachment-status'].textContent, /仍绑定|原资源池|保存 App 后/);
  elements['pool-attachment-tutorial-docs'].value = '改过的手册 | https://example/changed';

  await context.AdminAppUi.savePoolAttachments();

  const attachmentCalls = apiCalls.filter((call) => /\/attachments$/.test(call.targetPath));
  assert.equal(attachmentCalls[0].targetPath, '/pools/7/attachments');
  assert.equal(attachmentCalls[1].targetPath, '/pools/7/attachments');
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
