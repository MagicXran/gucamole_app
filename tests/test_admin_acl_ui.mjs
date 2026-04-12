import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';

const modulePath = path.join(process.cwd(), 'frontend', 'js', 'admin-acl-ui.js');
const adminShellPath = path.join(process.cwd(), 'frontend', 'js', 'admin.js');
const source = fs.readFileSync(modulePath, 'utf8');

class FakeElement {
  constructor(tagName, ownerDocument) {
    this.tagName = String(tagName || '').toUpperCase();
    this.ownerDocument = ownerDocument;
    this.children = [];
    this.parentNode = null;
    this.className = '';
    this.type = '';
    this.checked = false;
    this.onclick = null;
    this.attributes = {};
    this._textContent = '';
    this._innerHTML = '';
  }

  appendChild(child) {
    child.parentNode = this;
    this.children.push(child);
    return child;
  }

  setAttribute(name, value) {
    this.attributes[name] = String(value);
  }

  getAttribute(name) {
    return Object.prototype.hasOwnProperty.call(this.attributes, name)
      ? this.attributes[name]
      : null;
  }

  set textContent(value) {
    this._textContent = String(value);
  }

  get textContent() {
    return this._textContent;
  }

  set innerHTML(value) {
    this._innerHTML = String(value);
    this.children = [];
    this._textContent = '';
  }

  get innerHTML() {
    return this._innerHTML;
  }
}

class FakeDocument {
  constructor() {
    this.elementsById = new Map();
    this.allElements = [];
  }

  createElement(tagName) {
    const element = new FakeElement(tagName, this);
    this.allElements.push(element);
    return element;
  }

  getElementById(id) {
    return this.elementsById.get(id) || null;
  }

  setElementById(id, element) {
    this.elementsById.set(id, element);
  }

  querySelectorAll(selector) {
    const match = /^input\[data-user-id="([^"]+)"\]$/.exec(selector);
    if (!match) return [];
    const userId = match[1];
    return this.allElements.filter((element) => (
      element.tagName === 'INPUT'
      && element.getAttribute('data-user-id') === userId
    ));
  }
}

function createHarness(overrides = {}) {
  const document = new FakeDocument();
  const aclContainer = document.createElement('div');
  document.setElementById('acl-content', aclContainer);

  const apiCalls = [];
  const toasts = [];

  const context = {
    document,
    parseInt,
    async api(method, targetPath, payload) {
      apiCalls.push({ method, targetPath, payload });
      return {};
    },
    showToast(msg, type) {
      toasts.push({ msg, type });
    },
    ...overrides,
  };
  context.window = context;

  vm.runInNewContext(source, context, { filename: modulePath });

  return { context, document, aclContainer, apiCalls, toasts };
}

test('AdminAclUi exposes extracted ACL functions', () => {
  const { context } = createHarness();

  assert.equal(typeof context.AdminAclUi, 'object');
  assert.equal(typeof context.AdminAclUi.loadAcl, 'function');
  assert.equal(typeof context.AdminAclUi.renderAclMatrix, 'function');
  assert.equal(typeof context.AdminAclUi.saveAcl, 'function');
});

test('loadAcl keeps active users/apps and renders matrix defaults', async () => {
  const users = [
    { id: 1, username: 'alpha', display_name: 'Alpha', is_active: true },
    { id: 2, username: 'beta', display_name: 'Beta', is_active: false },
    { id: 3, username: 'gamma', display_name: 'Gamma', is_active: true },
  ];
  const apps = [
    { id: 11, name: 'Fluent', is_active: true },
    { id: 12, name: 'Abaqus', is_active: false },
  ];
  const { context, aclContainer, apiCalls } = createHarness({
    async api(method, targetPath, payload) {
      apiCalls.push({ method, targetPath, payload });
      if (method === 'GET' && targetPath === '/users') return users;
      if (method === 'GET' && targetPath === '/apps') return apps;
      if (method === 'GET' && targetPath === '/users/1/acl') return { app_ids: [11] };
      if (method === 'GET' && targetPath === '/users/3/acl') return { app_ids: [] };
      throw new Error(`unexpected api call ${method} ${targetPath}`);
    },
  });

  await context.AdminAclUi.loadAcl();

  assert.deepEqual(
    apiCalls.map((entry) => `${entry.method} ${entry.targetPath}`),
    ['GET /users', 'GET /apps', 'GET /users/1/acl', 'GET /users/3/acl'],
  );

  assert.equal(aclContainer.children.length, 2);
  const table = aclContainer.children[0];
  const thead = table.children[0];
  const tbody = table.children[1];

  assert.equal(thead.children[0].children.length, 2);
  assert.equal(thead.children[0].children[1].textContent, 'Fluent');
  assert.equal(tbody.children.length, 2);
  assert.equal(tbody.children[0].children[0].textContent, 'Alpha');
  assert.equal(tbody.children[1].children[0].textContent, 'Gamma');

  const firstRowCheckbox = tbody.children[0].children[1].children[0];
  const secondRowCheckbox = tbody.children[1].children[1].children[0];
  assert.equal(firstRowCheckbox.checked, true);
  assert.equal(secondRowCheckbox.checked, false);
  assert.equal(firstRowCheckbox.getAttribute('data-user-id'), '1');
  assert.equal(firstRowCheckbox.getAttribute('data-app-id'), '11');
});

test('renderAclMatrix shows empty-state message when data missing', () => {
  const { context, aclContainer } = createHarness();

  context.AdminAclUi.renderAclMatrix([], [{ id: 9, name: 'Solver' }], {});

  assert.equal(aclContainer.textContent, '暂无活跃用户或应用');
  assert.equal(aclContainer.children.length, 0);
});

test('saveAcl submits checked app ids per user', async () => {
  const users = [{ id: 7 }, { id: 8 }];
  const { context, document, apiCalls, toasts } = createHarness();

  const user7App11 = document.createElement('input');
  user7App11.type = 'checkbox';
  user7App11.checked = true;
  user7App11.setAttribute('data-user-id', 7);
  user7App11.setAttribute('data-app-id', '11');

  const user7App12 = document.createElement('input');
  user7App12.type = 'checkbox';
  user7App12.checked = false;
  user7App12.setAttribute('data-user-id', 7);
  user7App12.setAttribute('data-app-id', '12');

  const user8App13 = document.createElement('input');
  user8App13.type = 'checkbox';
  user8App13.checked = true;
  user8App13.setAttribute('data-user-id', 8);
  user8App13.setAttribute('data-app-id', '13');

  await context.AdminAclUi.saveAcl(users, []);

  assert.deepEqual(JSON.parse(JSON.stringify(apiCalls)), [
    { method: 'PUT', targetPath: '/users/7/acl', payload: { app_ids: [11] } },
    { method: 'PUT', targetPath: '/users/8/acl', payload: { app_ids: [13] } },
  ]);
  assert.deepEqual(toasts, [{ msg: '权限已保存', type: undefined }]);
});

test('loadAcl and saveAcl emit failure toasts on error', async () => {
  const users = [{ id: 5, username: 'u5', is_active: true }];
  const apps = [{ id: 2, name: 'CAD', is_active: true }];

  const loadHarness = createHarness({
    async api(method, targetPath) {
      if (method === 'GET' && targetPath === '/users') return users;
      if (method === 'GET' && targetPath === '/apps') return apps;
      throw new Error('acl down');
    },
  });

  await loadHarness.context.AdminAclUi.loadAcl();
  assert.deepEqual(loadHarness.toasts, [{ msg: '加载权限失败: acl down', type: 'error' }]);

  const saveHarness = createHarness({
    async api() {
      throw new Error('write denied');
    },
  });

  await saveHarness.context.AdminAclUi.saveAcl([{ id: 9 }], []);
  assert.deepEqual(saveHarness.toasts, [{ msg: '保存权限失败: write denied', type: 'error' }]);
});

test('admin.js delegates ACL operations to AdminAclUi namespace', () => {
  const adminShellSource = fs.readFileSync(adminShellPath, 'utf8');

  assert.match(
    adminShellSource,
    /var\s+loadAcl\s*=\s*async\s+function\s*\(\)\s*{\s*return\s+window\.AdminAclUi\.loadAcl\(\);\s*};/,
  );
  assert.match(
    adminShellSource,
    /var\s+renderAclMatrix\s*=\s*function\s*\(users,\s*apps,\s*aclMap\)\s*{\s*return\s+window\.AdminAclUi\.renderAclMatrix\(users,\s*apps,\s*aclMap\);\s*};/,
  );
  assert.match(
    adminShellSource,
    /var\s+saveAcl\s*=\s*async\s+function\s*\(users,\s*apps\)\s*{\s*return\s+window\.AdminAclUi\.saveAcl\(users,\s*apps\);\s*};/,
  );
  assert.doesNotMatch(adminShellSource, /function\s+renderAclMatrix\s*\(/);
});
