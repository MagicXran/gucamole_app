import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';

const source = await fs.readFile(new URL('../frontend/js/portal-queue-ui.js', import.meta.url), 'utf8');
const mod = await import(`data:text/javascript;base64,${Buffer.from(source).toString('base64')}`);

test('describeQueueTicket shows ready countdown', () => {
  const info = mod.describeQueueTicket(
    {
      queueId: 7,
      appName: '计算器',
      status: 'ready',
      position: 1,
      readyExpiresAt: '2026-04-01T12:00:20',
    },
    new Date('2026-04-01T12:00:05').getTime(),
  );

  assert.equal(info.label, '已就绪');
  assert.match(info.meta, /15s/);
});

test('describeQueueTicket gives explicit expired message', () => {
  const info = mod.describeQueueTicket(
    {
      queueId: 7,
      appName: '计算器',
      status: 'expired',
      position: 0,
      cancelReason: 'timeout',
    },
    Date.now(),
  );

  assert.equal(info.label, '已超时');
  assert.match(info.meta, /ready 超时/);
});

test('summarizePoolUtilization returns percent and label', () => {
  const summary = mod.summarizePoolUtilization({
    max_concurrent: 4,
    active_count: 3,
    queued_count: 2,
  });

  assert.equal(summary.percent, 75);
  assert.equal(summary.label, '3 / 4');
  assert.equal(summary.queuedLabel, '排队 2');
});
