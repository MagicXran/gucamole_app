import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';

const monitorUiPath = path.join(process.cwd(), 'frontend', 'js', 'admin-monitor-ui.js');
const adminHtmlPath = path.join(process.cwd(), 'frontend', 'admin.html');
const adminShellPath = path.join(process.cwd(), 'frontend', 'js', 'admin.js');
const source = fs.readFileSync(monitorUiPath, 'utf8');

function createElement(tagName) {
  return {
    tagName: String(tagName || '').toUpperCase(),
    children: [],
    className: '',
    textContent: '',
    style: {},
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

function createHarness() {
  const elements = {
    'monitor-cards': createElement('div'),
    'monitor-summary': createElement('div'),
  };

  const context = {
    document: {
      getElementById(id) {
        return Object.prototype.hasOwnProperty.call(elements, id) ? elements[id] : null;
      },
      createElement,
    },
    ICON_MAP: {
      desktop: '🖥️',
      cube: '🧊',
    },
    window: null,
  };
  context.window = context;

  vm.runInNewContext(source, context, { filename: monitorUiPath });

  return {
    context,
    elements,
  };
}

test('AdminMonitorUi exports expected monitor card renderer', () => {
  const harness = createHarness();

  assert.equal(typeof harness.context.AdminMonitorUi, 'object');
  assert.equal(typeof harness.context.AdminMonitorUi.renderMonitorCards, 'function');
});

test('renderMonitorCards renders summary and active/inactive classes', () => {
  const harness = createHarness();

  harness.context.AdminMonitorUi.renderMonitorCards({
    total_online: 3,
    total_sessions: 5,
    apps: [
      { app_name: 'Fluent', icon: 'cube', active_count: 2 },
      { app_name: 'Idle App', icon: 'unknown', active_count: 0 },
    ],
  });

  assert.equal(harness.elements['monitor-summary'].textContent, '在线 3 人 / 5 个会话');
  assert.equal(harness.elements['monitor-cards'].children.length, 2);

  const activeCard = harness.elements['monitor-cards'].children[0];
  assert.equal(activeCard.className, 'monitor-card');
  assert.equal(activeCard.children[0].className, 'monitor-card__icon');
  assert.equal(activeCard.children[1].children[1].className, 'monitor-card__count monitor-card__count--active');
  assert.equal(activeCard.children[1].children[1].children[0].className, 'monitor-card__dot monitor-card__dot--green');

  const inactiveCard = harness.elements['monitor-cards'].children[1];
  assert.equal(inactiveCard.children[1].children[1].className, 'monitor-card__count');
  assert.equal(inactiveCard.children[1].children[1].children[0].className, 'monitor-card__dot monitor-card__dot--gray');
});

test('admin.js delegates monitor card rendering to AdminMonitorUi', () => {
  const adminShellSource = fs.readFileSync(adminShellPath, 'utf8');
  const adminHtmlSource = fs.readFileSync(adminHtmlPath, 'utf8');

  assert.match(
    adminShellSource,
    /var\s+renderMonitorCards\s*=\s*function\s*\(data\)\s*{\s*return\s+window\.AdminMonitorUi\.renderMonitorCards\(data\);\s*};/,
  );
  assert.doesNotMatch(adminShellSource, /function\s+renderMonitorCards\s*\(/);

  const monitorScriptIndex = adminHtmlSource.indexOf('<script src="js/admin-monitor-ui.js"></script>');
  const shellScriptIndex = adminHtmlSource.indexOf('<script src="js/admin.js"></script>');
  assert.notEqual(monitorScriptIndex, -1);
  assert.notEqual(shellScriptIndex, -1);
  assert.ok(monitorScriptIndex < shellScriptIndex);
});
