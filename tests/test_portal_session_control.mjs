import test from 'node:test';
import assert from 'node:assert/strict';

import {
  DEFAULT_SESSION_RECLAIMED_MESSAGE,
  createPortalSessionControl,
  detectSessionReclaimed,
} from '../frontend/js/portal-session-control.js';

test('detectSessionReclaimed identifies admin reclaim response', () => {
  const decision = detectSessionReclaimed(409, {
    code: 'session_reclaimed',
    detail: '会话已被管理员回收',
  });

  assert.equal(decision.reclaimed, true);
  assert.equal(decision.message, '会话已被管理员回收');
});

test('detectSessionReclaimed identifies idle reclaim response', () => {
  const decision = detectSessionReclaimed(409, {
    code: 'session_idle_reclaimed',
    detail: '会话因长时间空闲被系统回收',
  });

  assert.equal(decision.reclaimed, true);
  assert.equal(decision.message, '会话因长时间空闲被系统回收');
});

test('detectSessionReclaimed ignores network jitter-like responses', () => {
  assert.deepEqual(
    detectSessionReclaimed(503, { code: 'service_unavailable' }),
    { reclaimed: false, message: '' },
  );
  assert.deepEqual(
    detectSessionReclaimed(409, { code: 'other_conflict' }),
    { reclaimed: false, message: '' },
  );
  assert.deepEqual(
    detectSessionReclaimed(409, null),
    { reclaimed: false, message: '' },
  );
});

test('session control stops reporting once reclaimed', () => {
  const notices = [];
  const control = createPortalSessionControl({
    onReclaimed(message) {
      notices.push(message);
    },
  });

  assert.equal(control.shouldReport(), true);
  assert.equal(control.isStopped(), false);

  const first = control.processResponse(409, {
    code: 'session_reclaimed',
  });
  const second = control.processResponse(409, {
    code: 'session_reclaimed',
    detail: '第二次不应重复处理',
  });

  assert.equal(first.reclaimed, true);
  assert.equal(first.message, DEFAULT_SESSION_RECLAIMED_MESSAGE);
  assert.equal(second.reclaimed, true);
  assert.equal(control.isStopped(), true);
  assert.equal(control.shouldReport(), false);
  assert.deepEqual(notices, [DEFAULT_SESSION_RECLAIMED_MESSAGE]);
});

test('network errors should not stop reporting', () => {
  const control = createPortalSessionControl();

  const decision = control.processNetworkError(new Error('network down'));

  assert.deepEqual(decision, { reclaimed: false, message: '' });
  assert.equal(control.isStopped(), false);
  assert.equal(control.shouldReport(), true);
});
