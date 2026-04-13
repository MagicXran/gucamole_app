import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';

const source = await fs.readFile(new URL('../frontend/js/portal-tasks.js', import.meta.url), 'utf8');

globalThis.window = globalThis;
globalThis.document = {
  querySelector() { return null; },
  getElementById() { return null; },
};
globalThis.fetch = async () => ({ ok: true, status: 200, json: async () => ({ items: [] }) });
globalThis.getToken = () => 'token';
globalThis.logout = () => {};
globalThis.escapeAttr = (value) => String(value ?? '');
globalThis.escapeHtml = (value) => String(value ?? '');
globalThis.authHeaders = () => ({});
globalThis.showError = () => {};
globalThis.closePortalModal = () => {};
globalThis.switchPortalTab = () => {};
globalThis.formatBytes = (value) => String(value ?? '');
globalThis.confirm = () => true;
globalThis.setInterval = () => 1;
globalThis.clearInterval = () => {};

await import(`data:text/javascript;base64,${Buffer.from(source).toString('base64')}`);

test('describeTaskState flags assigned timeout with explicit guidance', () => {
  const info = globalThis.PortalTasks.describeTaskState(
    {
      status: 'assigned',
      assigned_at: '2026-04-08 19:00:00',
      created_at: '2026-04-08 18:59:30',
    },
    Date.parse('2026-04-08T19:02:00'),
  );

  assert.equal(info.isStalled, true);
  assert.equal(info.tone, 'failed');
  assert.match(info.label, /超时/);
  assert.match(info.message, /Worker 已领取任务/);
});

test('describeTaskState keeps running task unchanged', () => {
  const info = globalThis.PortalTasks.describeTaskState(
    {
      status: 'running',
      assigned_at: '2026-04-08 19:00:00',
    },
    Date.parse('2026-04-08T19:20:00'),
  );

  assert.equal(info.isStalled, false);
  assert.equal(info.tone, 'running');
  assert.equal(info.label, 'running');
});
