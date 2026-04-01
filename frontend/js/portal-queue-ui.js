function parseReadyExpiry(value) {
    if (!value) return null;
    var timestamp = Date.parse(value);
    return Number.isNaN(timestamp) ? null : timestamp;
}

export function describeQueueTicket(ticket, nowMs) {
    var label = '排队中';
    var meta = '队列编号 #' + ticket.queueId + ' · 当前位置 ' + (ticket.position > 0 ? ('#' + ticket.position) : '-');

    if (ticket.status === 'ready') {
        label = '已就绪';
        var expiresAt = parseReadyExpiry(ticket.readyExpiresAt);
        if (expiresAt) {
            var secondsLeft = Math.max(0, Math.ceil((expiresAt - nowMs) / 1000));
            meta += ' · 剩余 ' + secondsLeft + 's';
        }
    } else if (ticket.status === 'launching') {
        label = '正在启动';
    } else if (ticket.status === 'expired') {
        label = '已超时';
        meta = 'ready 超时，请重新排队';
    } else if (ticket.status === 'cancelled') {
        label = '已取消';
        meta = ticket.cancelReason === 'member_unavailable'
            ? '资源已被其他用户占用，请重新排队'
            : '排队已取消';
    } else if (ticket.status === 'fulfilled') {
        label = '已完成';
        meta = '资源已分配';
    }

    return { label: label, meta: meta };
}

export function summarizePoolUtilization(pool) {
    var maxConcurrent = Math.max(1, Number(pool.max_concurrent || 1));
    var activeCount = Math.max(0, Number(pool.active_count || 0));
    var queuedCount = Math.max(0, Number(pool.queued_count || 0));
    return {
        percent: Math.min(100, Math.round((activeCount / maxConcurrent) * 100)),
        label: activeCount + ' / ' + maxConcurrent,
        queuedLabel: '排队 ' + queuedCount,
    };
}

if (typeof window !== 'undefined') {
    window.PortalQueueUI = {
        describeQueueTicket: describeQueueTicket,
        summarizePoolUtilization: summarizePoolUtilization,
    };
}
