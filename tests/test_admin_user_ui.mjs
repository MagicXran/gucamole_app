import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';

const userUiPath = path.join(process.cwd(), 'frontend', 'js', 'admin-user-ui.js');
const adminHtmlPath = path.join(process.cwd(), 'frontend', 'admin.html');
const adminShellPath = path.join(process.cwd(), 'frontend', 'js', 'admin.js');
const source = fs.readFileSync(userUiPath, 'utf8');

function toPlain(value) {
  return JSON.parse(JSON.stringify(value));
}

function escapeHtml(value) {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

function escapeAttr(value) {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('"', '&quot;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;');
}

function createNode(tagName) {
  let inner = '';
  return {
    tagName: String(tagName || '').toUpperCase(),
    children: [],
    style: {},
    className: '',
    textContent: '',
    value: '',
    checked: false,
    onclick: null,
    onsubmit: null,
    appendChild(child) {
      this.children.push(child);
      return child;
    },
    setAttribute(name, value) {
      this[name] = String(value);
    },
    get innerHTML() {
      return inner;
    },
    set innerHTML(value) {
      inner = String(value);
      if (inner === '') this.children = [];
    },
  };
}

function createHarness() {
  const usersTbody = createNode('tbody');
  const modalContainer = createNode('div');
  const userForm = createNode('form');

  const elements = {
    'modal-container': modalContainer,
    'user-form': userForm,
  };

  const apiCalls = [];
  const toasts = [];
  const confirmAnswers = [];
  const apiResults = new Map();

  const document = {
    querySelector(selector) {
      if (selector === '#users-table tbody') return usersTbody;
      return null;
    },
    createElement(tagName) {
      return createNode(tagName);
    },
    getElementById(id) {
      return Object.prototype.hasOwnProperty.call(elements, id) ? elements[id] : null;
    },
  };

  const context = {
    document,
    parseInt,
    console,
    api: async (method, targetPath, payload) => {
      apiCalls.push({ method, targetPath, payload });
      const key = `${method} ${targetPath}`;
      if (apiResults.has(key)) {
        const resolved = apiResults.get(key);
        return typeof resolved === 'function' ? resolved({ method, targetPath, payload }) : resolved;
      }
      return {};
    },
    showToast(msg, type) {
      toasts.push({ msg, type });
    },
    closeModalCalls: 0,
    closeModal() {
      context.closeModalCalls += 1;
    },
    confirm() {
      return confirmAnswers.length ? confirmAnswers.shift() : true;
    },
    escapeHtml,
    escapeAttr,
    formGroup(label, id, value, type, required) {
      const inputType = type || 'text';
      const req = required ? ' required' : '';
      return `<div class="form-group"><label>${escapeHtml(label)}</label><input id="${id}" type="${inputType}" value="${escapeAttr(value ?? '')}"${req}></div>`;
    },
    formGroupSelect(label, id, options, selected) {
      const optionsHtml = options.map((opt) => `<option value="${escapeAttr(opt)}"${opt === selected ? ' selected' : ''}>${escapeHtml(opt)}</option>`).join('');
      return `<div class="form-group"><label>${escapeHtml(label)}</label><select id="${id}">${optionsHtml}</select></div>`;
    },
    _quotaBytesToLabel(bytes) {
      if (!bytes) return '默认(10GB)';
      const gb = Math.round(bytes / 1073741824);
      return `${gb} GB`;
    },
    _quotaLabelToGb(label) {
      if (label === '不限制') return 9999;
      if (label === '默认(10GB)') return 0;
      const match = String(label).match(/(\d+)/);
      return match ? parseInt(match[1], 10) : 0;
    },
  };

  context.window = context;

  function setElement(id, value, checked) {
    const el = createNode('input');
    if (value !== undefined) el.value = value;
    if (checked !== undefined) el.checked = checked;
    elements[id] = el;
    return el;
  }

  function loadModule() {
    vm.runInNewContext(source, context, { filename: userUiPath });
  }

  return {
    context,
    elements,
    usersTbody,
    modalContainer,
    apiCalls,
    toasts,
    confirmAnswers,
    apiResults,
    setElement,
    loadModule,
  };
}

test('AdminUserUi exports extracted user management functions', () => {
  const harness = createHarness();
  harness.loadModule();

  const required = [
    'loadUsers',
    'renderUsersTable',
    'showUserModal',
    'saveUser',
    'deleteUser',
    '_quotaBytesToLabel',
    '_quotaLabelToGb',
  ];

  assert.equal(typeof harness.context.AdminUserUi, 'object');
  for (const name of required) {
    assert.equal(typeof harness.context.AdminUserUi[name], 'function', `missing ${name}`);
  }
});

test('loadUsers renders user rows and action buttons correctly', async () => {
  const harness = createHarness();
  harness.loadModule();

  harness.apiResults.set('GET /users', [
    {
      id: 1,
      username: 'admin',
      display_name: '管理员',
      department: '平台部',
      is_admin: true,
      used_display: '1 GB',
      quota_display: '10 GB',
      is_active: true,
    },
    {
      id: 2,
      username: 'guest',
      display_name: '访客',
      department: '',
      is_admin: false,
      used_display: '0 B',
      quota_display: '5 GB',
      is_active: false,
    },
  ]);

  await harness.context.AdminUserUi.loadUsers();

  assert.deepEqual(harness.apiCalls[0], { method: 'GET', targetPath: '/users', payload: undefined });
  assert.equal(harness.usersTbody.children.length, 2);

  const firstRow = harness.usersTbody.children[0];
  assert.equal(firstRow.children[0].textContent, 1);
  assert.equal(firstRow.children[1].textContent, 'admin');
  assert.equal(firstRow.children[2].textContent, '管理员');
  assert.equal(firstRow.children[3].textContent, '平台部');
  assert.equal(firstRow.children[4].children[0].textContent, '管理员');
  assert.equal(firstRow.children[5].textContent, '1 GB / 10 GB');
  assert.equal(firstRow.children[6].children[0].textContent, '正常');
  assert.equal(firstRow.children[7].children.length, 2);

  const secondRow = harness.usersTbody.children[1];
  assert.equal(secondRow.children[3].textContent, '-');
  assert.equal(secondRow.children[4].textContent, '普通用户');
  assert.equal(secondRow.children[6].children[0].textContent, '已禁用');
  assert.equal(secondRow.children[7].children.length, 1);
});

test('showUserModal renders create/edit variants and binds form submit', () => {
  const harness = createHarness();
  harness.loadModule();

  harness.context.AdminUserUi.showUserModal(null);
  assert.match(harness.modalContainer.innerHTML, /新建用户/);
  assert.match(harness.modalContainer.innerHTML, /user-username/);
  assert.match(harness.modalContainer.innerHTML, /user-department/);
  assert.equal(typeof harness.elements['user-form'].onsubmit, 'function');

  harness.context.AdminUserUi.showUserModal({
    id: 8,
    username: 'alice',
    display_name: 'Alice',
    department: '研发一部',
    is_admin: true,
    is_active: true,
    quota_bytes: 21474836480,
  });
  assert.match(harness.modalContainer.innerHTML, /编辑用户/);
  assert.match(harness.modalContainer.innerHTML, /value="alice" disabled/);
  assert.match(harness.modalContainer.innerHTML, /value="研发一部"/);
  assert.match(harness.modalContainer.innerHTML, /user-is-active/);
});

test('saveUser blocks create when username/password missing', async () => {
  const harness = createHarness();
  harness.loadModule();

  harness.setElement('user-quota', '默认(10GB)');
  harness.setElement('user-username', '   ');
  harness.setElement('user-password', '');
  harness.setElement('user-display', '访客');
  harness.setElement('user-is-admin', '', false);

  await harness.context.AdminUserUi.saveUser(null);

  assert.equal(harness.apiCalls.length, 0);
  assert.deepEqual(harness.toasts[0], { msg: '用户名和密码为必填项', type: 'error' });
});

test('saveUser creates user then reloads list', async () => {
  const harness = createHarness();
  harness.loadModule();

  harness.apiResults.set('GET /users', []);
  harness.setElement('user-quota', '20 GB');
  harness.setElement('user-username', ' new_user  ');
  harness.setElement('user-password', 'pw123');
  harness.setElement('user-display', ' 新用户 ');
  harness.setElement('user-department', ' 研发一部 ');
  harness.setElement('user-is-admin', '', true);

  await harness.context.AdminUserUi.saveUser(null);

  assert.equal(harness.apiCalls.length, 2);
  assert.equal(harness.apiCalls[0].method, 'POST');
  assert.equal(harness.apiCalls[0].targetPath, '/users');
  assert.deepEqual(toPlain(harness.apiCalls[0].payload), {
    quota_gb: 20,
    username: 'new_user',
    password: 'pw123',
    display_name: '新用户',
    department: '研发一部',
    is_admin: true,
  });
  assert.equal(harness.apiCalls[1].method, 'GET');
  assert.equal(harness.apiCalls[1].targetPath, '/users');
  assert.equal(harness.toasts[0].msg, '用户已创建');
  assert.equal(harness.context.closeModalCalls, 1);
});

test('saveUser updates user without forcing password change', async () => {
  const harness = createHarness();
  harness.loadModule();

  harness.apiResults.set('GET /users', []);
  harness.setElement('user-quota', '默认(10GB)');
  harness.setElement('user-password', '');
  harness.setElement('user-display', ' Alice  ');
  harness.setElement('user-department', ' 平台部 ');
  harness.setElement('user-is-admin', '', true);
  harness.setElement('user-is-active', '', false);

  await harness.context.AdminUserUi.saveUser(8);

  assert.equal(harness.apiCalls.length, 2);
  assert.equal(harness.apiCalls[0].method, 'PUT');
  assert.equal(harness.apiCalls[0].targetPath, '/users/8');
  assert.equal(Object.prototype.hasOwnProperty.call(harness.apiCalls[0].payload, 'password'), false);
  assert.deepEqual(toPlain(harness.apiCalls[0].payload), {
    quota_gb: 0,
    display_name: 'Alice',
    department: '平台部',
    is_admin: true,
    is_active: false,
  });
  assert.equal(harness.toasts[0].msg, '用户已更新');
});

test('admin.html users table exposes department column in legacy shell', () => {
  const html = fs.readFileSync(adminHtmlPath, 'utf8');

  assert.match(
    html,
    /<table class="admin-table" id="users-table">[\s\S]*?<th>ID<\/th><th>用户名<\/th><th>显示名<\/th>\s*<th>部门<\/th><th>角色<\/th><th>空间<\/th><th>状态<\/th><th>操作<\/th>/,
  );
});

test('deleteUser obeys confirmation and reloads on success', async () => {
  const harness = createHarness();
  harness.loadModule();

  harness.confirmAnswers.push(false);
  await harness.context.AdminUserUi.deleteUser(3);
  assert.equal(harness.apiCalls.length, 0);

  harness.confirmAnswers.push(true);
  harness.apiResults.set('GET /users', []);
  await harness.context.AdminUserUi.deleteUser(3);

  assert.equal(harness.apiCalls.length, 2);
  assert.equal(harness.apiCalls[0].method, 'DELETE');
  assert.equal(harness.apiCalls[0].targetPath, '/users/3');
  assert.equal(harness.apiCalls[1].method, 'GET');
  assert.equal(harness.apiCalls[1].targetPath, '/users');
  assert.equal(harness.toasts[0].msg, '用户已禁用');
});

test('admin.html loads extracted user/acl/audit scripts before admin.js', () => {
  const html = fs.readFileSync(adminHtmlPath, 'utf8');
  const scriptSrcs = [...html.matchAll(/<script\s+src="([^"]+)"/g)].map((item) => item[1]);

  const userIndex = scriptSrcs.indexOf('js/admin-user-ui.js');
  const aclIndex = scriptSrcs.indexOf('js/admin-acl-ui.js');
  const auditIndex = scriptSrcs.indexOf('js/admin-audit-ui.js');
  const shellIndex = scriptSrcs.indexOf('js/admin.js');

  assert.notEqual(userIndex, -1);
  assert.notEqual(aclIndex, -1);
  assert.notEqual(auditIndex, -1);
  assert.notEqual(shellIndex, -1);
  assert.ok(userIndex < shellIndex);
  assert.ok(aclIndex < shellIndex);
  assert.ok(auditIndex < shellIndex);
});

test('admin.js delegates user operations to AdminUserUi namespace', () => {
  const adminShellSource = fs.readFileSync(adminShellPath, 'utf8');

  assert.match(
    adminShellSource,
    /var\s+loadUsers\s*=\s*async\s+function\s*\(\)\s*{\s*return\s+window\.AdminUserUi\.loadUsers\(\);\s*};/,
  );
  assert.match(
    adminShellSource,
    /var\s+showUserModal\s*=\s*function\s*\(u\)\s*{\s*return\s+window\.AdminUserUi\.showUserModal\(u\);\s*};/,
  );
  assert.match(
    adminShellSource,
    /var\s+saveUser\s*=\s*async\s+function\s*\(userId\)\s*{\s*return\s+window\.AdminUserUi\.saveUser\(userId\);\s*};/,
  );
  assert.match(
    adminShellSource,
    /var\s+deleteUser\s*=\s*async\s+function\s*\(id\)\s*{\s*return\s+window\.AdminUserUi\.deleteUser\(id\);\s*};/,
  );
  assert.doesNotMatch(adminShellSource, /var\s+_users\s*=\s*\[\s*];/);
  assert.doesNotMatch(adminShellSource, /function _quotaBytesToLabel\s*\(/);
  assert.doesNotMatch(adminShellSource, /function _quotaLabelToGb\s*\(/);
});
