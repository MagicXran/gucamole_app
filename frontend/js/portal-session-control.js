const SESSION_RECLAIMED_STATUS = 409;
const SESSION_RECLAIMED_CODES = new Set(['session_reclaimed', 'session_idle_reclaimed']);
export const DEFAULT_SESSION_RECLAIMED_MESSAGE = '该会话已被系统回收，窗口将关闭';

function buildNoopDecision() {
  return { reclaimed: false, message: '' };
}

function pickReadableMessage(payload) {
  if (!payload || typeof payload !== 'object') return '';
  if (typeof payload.detail === 'string' && payload.detail.trim()) return payload.detail.trim();
  if (typeof payload.message === 'string' && payload.message.trim()) return payload.message.trim();
  return '';
}

export function detectSessionReclaimed(status, payload) {
  if (status !== SESSION_RECLAIMED_STATUS || !payload || typeof payload !== 'object') {
    return buildNoopDecision();
  }

  if (!SESSION_RECLAIMED_CODES.has(payload.code)) {
    return buildNoopDecision();
  }

  return {
    reclaimed: true,
    message: pickReadableMessage(payload) || DEFAULT_SESSION_RECLAIMED_MESSAGE,
  };
}

export function createPortalSessionControl(options) {
  const onReclaimed = options && typeof options.onReclaimed === 'function' ? options.onReclaimed : null;
  let stopped = false;
  let reclaimHandled = false;

  function stop() {
    if (stopped) return false;
    stopped = true;
    return true;
  }

  function processResponse(status, payload) {
    const decision = detectSessionReclaimed(status, payload);
    if (!decision.reclaimed) return decision;

    stop();
    if (!reclaimHandled && onReclaimed) {
      reclaimHandled = true;
      onReclaimed(decision.message);
    }
    return decision;
  }

  function processNetworkError() {
    return buildNoopDecision();
  }

  return {
    isStopped() {
      return stopped;
    },
    shouldReport() {
      return !stopped;
    },
    stop,
    processResponse,
    processNetworkError,
  };
}
