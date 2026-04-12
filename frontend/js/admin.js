/**
 * RemoteApp 管理后台 - 前端逻辑
 */

var API_ADMIN = '/api/admin';

function adminAuthHeaders() {
    return {
        'Authorization': 'Bearer ' + getToken(),
        'Content-Type': 'application/json',
    };
}

// ---- Toast 通知 ----
function showToast(msg, type) {
    var existing = document.querySelector('.toast');
    if (existing) existing.remove();

    var el = document.createElement('div');
    el.className = 'toast toast--' + (type || 'success');
    el.textContent = msg;
    document.body.appendChild(el);
    setTimeout(function() { el.remove(); }, 3000);
}

// ---- API 请求封装 ----
async function api(method, path, body) {
    var opts = { method: method, headers: adminAuthHeaders() };
    if (body !== undefined) opts.body = JSON.stringify(body);
    var resp = await fetch(API_ADMIN + path, opts);
    if (resp.status === 401) { logout(); return null; }
    if (resp.status === 403) { showToast('权限不足', 'error'); return null; }
    if (!resp.ok) {
        var err = await resp.json().catch(function() { return {}; });
        throw new Error(err.detail || 'HTTP ' + resp.status);
    }
    if (resp.status === 204) return {};
    return await resp.json();
}


// ============================================
// Tab 切换
// ============================================
var _currentTab = 'monitor';
var _tabLoaded = {};

function switchTab(tab) {
    _currentTab = tab;
    // 激活 tab 按钮
    document.querySelectorAll('.tab-bar__item').forEach(function(btn) {
        btn.classList.toggle('tab-bar__item--active', btn.getAttribute('data-tab') === tab);
    });
    // 显示对应面板
    document.querySelectorAll('.tab-panel').forEach(function(p) {
        p.classList.toggle('tab-panel--active', p.id === 'panel-' + tab);
    });
    // 管理 auto-refresh
    _manageMonitorRefresh(tab === 'monitor');
    // 首次加载数据
    if (!_tabLoaded[tab]) {
        _tabLoaded[tab] = true;
        if (tab === 'monitor') loadMonitor();
        else if (tab === 'pools') loadPools();
        else if (tab === 'workers') loadWorkers();
        else if (tab === 'apps') loadApps();
        else if (tab === 'users') loadUsers();
        else if (tab === 'acl') loadAcl();
        else if (tab === 'audit') loadAuditLogs(1);
    }
}


// ============================================
// 资源池管理
// ============================================
var _pools = [];
async function ensurePoolsLoaded() {
    if (_pools.length) return;
    _pools = await api('GET', '/pools');
}

async function loadPools() {
    try {
        _pools = await api('GET', '/pools');
        renderPoolsTable();
        var queueData = await api('GET', '/pools/queues');
        renderPoolQueueTable(queueData.items || []);
    } catch (e) { showToast('加载资源池失败: ' + e.message, 'error'); }
}

function renderPoolsTable() {
    var tbody = document.querySelector('#pools-table tbody');
    if (!tbody) return;
    tbody.innerHTML = '';
    var queueUi = window.PortalQueueUI || null;

    _pools.forEach(function(pool) {
        var usage = queueUi
            ? queueUi.summarizePoolUtilization(pool)
            : {
                percent: 0,
                label: (pool.active_count || 0) + ' / ' + (pool.max_concurrent || 1),
                queuedLabel: '排队 ' + (pool.queued_count || 0),
            };
        var tr = document.createElement('tr');
        tr.innerHTML =
            '<td>' + pool.id + '</td>' +
            '<td>' + escapeHtml(pool.name) + '</td>' +
            '<td>' + pool.max_concurrent + '</td>' +
            '<td>' + (pool.active_count || 0) + '</td>' +
            '<td>' + (pool.queued_count || 0) + '</td>' +
            '<td><div class="pool-usage"><div class="pool-usage__bar"><div class="pool-usage__fill" style="width:' + usage.percent + '%"></div></div><div class="pool-usage__text">' + escapeHtml(usage.label) + ' · ' + escapeHtml(usage.queuedLabel) + '</div></div></td>' +
            '<td>' + (pool.is_active ? '<span class="badge badge--active">启用</span>' : '<span class="badge badge--inactive">禁用</span>') + '</td>' +
            '<td><button class="btn btn--outline btn--small" onclick="showPoolModal(' + pool.id + ')">编辑</button></td>';
        tbody.appendChild(tr);
    });
}

function renderPoolQueueTable(items) {
    var tbody = document.querySelector('#pool-queue-table tbody');
    if (!tbody) return;
    tbody.innerHTML = '';

    if (!items.length) {
        var tr = document.createElement('tr');
        tr.innerHTML = '<td colspan="6" style="text-align:center;color:#999;">当前无排队记录</td>';
        tbody.appendChild(tr);
        return;
    }

    items.forEach(function(item) {
        var tr = document.createElement('tr');
        tr.innerHTML =
            '<td>' + escapeHtml(item.pool_name) + '</td>' +
            '<td>' + escapeHtml(item.display_name || item.username) + '</td>' +
            '<td>' + escapeHtml(item.status) + '</td>' +
            '<td>' + escapeHtml(item.created_at || '-') + '</td>' +
            '<td>' + escapeHtml(item.ready_expires_at || '-') + (item.cancel_reason ? ('<br><span style="font-size:0.75rem;color:#999;">' + escapeHtml(item.cancel_reason) + '</span>') : '') + '</td>' +
            '<td><button class="btn btn--danger btn--small" onclick="cancelPoolQueue(' + item.queue_id + ')">取消</button></td>';
        tbody.appendChild(tr);
    });
}

function showPoolModal(poolId) {
    var pool = null;
    if (poolId) {
        pool = _pools.find(function(item) { return item.id === poolId; }) || null;
    }

    var html = '<div class="modal-overlay" onclick="closeModal(event)">' +
        '<div class="modal" onclick="event.stopPropagation()">' +
        '<div class="modal__title">' + (pool ? '编辑资源池' : '新建资源池') + '</div>' +
        '<form id="pool-form">' +
        formGroup('名称', 'pool-name', pool ? pool.name : '', 'text', true) +
        '<div class="form-row">' +
        formGroup('图标', 'pool-icon', pool ? pool.icon : 'desktop') +
        formGroup('总并发上限', 'pool-max', pool ? pool.max_concurrent : 1, 'number', true) +
        '</div>' +
        '<div class="form-row">' +
        formGroup('ready 宽限(秒)', 'pool-grace', pool ? pool.dispatch_grace_seconds : 120, 'number', true) +
        formGroup('失联回收(秒)', 'pool-stale', pool ? pool.stale_timeout_seconds : 120, 'number', true) +
        '</div>' +
        formGroup('空闲回收(秒, 留空禁用)', 'pool-idle', pool && pool.idle_timeout_seconds ? pool.idle_timeout_seconds : '', 'number') +
        '<div class="form-group form-group--checkbox">' +
        '<input type="checkbox" id="pool-auto"' + ((!pool || pool.auto_dispatch_enabled) ? ' checked' : '') + '>' +
        '<label for="pool-auto">启用自动放行</label></div>' +
        '<div class="form-group form-group--checkbox">' +
        '<input type="checkbox" id="pool-active"' + ((!pool || pool.is_active) ? ' checked' : '') + '>' +
        '<label for="pool-active">启用</label></div>' +
        '<div class="modal__actions">' +
        '<button type="button" class="btn btn--outline" onclick="closeModal()">取消</button>' +
        '<button type="submit" class="btn btn--primary">' + (pool ? '保存' : '创建') + '</button>' +
        '</div></form></div></div>';

    document.getElementById('modal-container').innerHTML = html;
    document.getElementById('pool-form').onsubmit = function(e) {
        e.preventDefault();
        savePool(pool ? pool.id : null);
    };
}

async function savePool(poolId) {
    var data = {
        name: document.getElementById('pool-name').value.trim(),
        icon: document.getElementById('pool-icon').value.trim() || 'desktop',
        max_concurrent: parseInt(document.getElementById('pool-max').value, 10) || 1,
        auto_dispatch_enabled: document.getElementById('pool-auto').checked,
        dispatch_grace_seconds: parseInt(document.getElementById('pool-grace').value, 10) || 120,
        stale_timeout_seconds: parseInt(document.getElementById('pool-stale').value, 10) || 120,
        idle_timeout_seconds: document.getElementById('pool-idle').value ? parseInt(document.getElementById('pool-idle').value, 10) : null,
        is_active: document.getElementById('pool-active').checked,
    };

    try {
        if (poolId) {
            await api('PUT', '/pools/' + poolId, data);
            showToast('资源池已更新');
        } else {
            await api('POST', '/pools', data);
            showToast('资源池已创建');
        }
        closeModal();
        loadPools();
    } catch (e) { showToast(e.message, 'error'); }
}

async function cancelPoolQueue(queueId) {
    if (!confirm('确定取消这条排队？')) return;
    try {
        await api('POST', '/pools/queues/' + queueId + '/cancel');
        showToast('排队已取消');
        loadPools();
    } catch (e) { showToast(e.message, 'error'); }
}


// ============================================
// Worker / App UI 委托
// ============================================

var loadApps = async function() {
    return window.AdminAppUi.loadApps();
};

var loadWorkers = async function() {
    return window.AdminWorkerUi.loadWorkers();
};

var showWorkerSoftwareInventory = function(workerNodeId) {
    return window.AdminWorkerUi.showWorkerSoftwareInventory(workerNodeId);
};

var showWorkerGroupModal = function() {
    return window.AdminWorkerUi.showWorkerGroupModal();
};

var showWorkerNodeModal = async function() {
    return window.AdminWorkerUi.showWorkerNodeModal();
};

var issueWorkerEnrollment = async function(workerNodeId) {
    return window.AdminWorkerUi.issueWorkerEnrollment(workerNodeId);
};

var rotateWorkerToken = async function(workerNodeId) {
    return window.AdminWorkerUi.rotateWorkerToken(workerNodeId);
};

var revokeWorkerNode = async function(workerNodeId) {
    return window.AdminWorkerUi.revokeWorkerNode(workerNodeId);
};

var showAppModal = async function(app) {
    return window.AdminAppUi.showAppModal(app);
};

var saveApp = async function(appId) {
    return window.AdminAppUi.saveApp(appId);
};

var deleteApp = async function(id) {
    return window.AdminAppUi.deleteApp(id);
};

// ============================================
// 用户 / ACL / 审计 UI 委托
// ============================================

var loadUsers = async function() {
    return window.AdminUserUi.loadUsers();
};

var renderUsersTable = function() {
    return window.AdminUserUi.renderUsersTable();
};

var showUserModal = function(u) {
    return window.AdminUserUi.showUserModal(u);
};

var saveUser = async function(userId) {
    return window.AdminUserUi.saveUser(userId);
};

var deleteUser = async function(id) {
    return window.AdminUserUi.deleteUser(id);
};

var loadAcl = async function() {
    return window.AdminAclUi.loadAcl();
};

var renderAclMatrix = function(users, apps, aclMap) {
    return window.AdminAclUi.renderAclMatrix(users, apps, aclMap);
};

var saveAcl = async function(users, apps) {
    return window.AdminAclUi.saveAcl(users, apps);
};

var ACTION_LABELS = window.AdminAuditUi.ACTION_LABELS;

var loadAuditLogs = async function(page) {
    return window.AdminAuditUi.loadAuditLogs(page);
};

var renderAuditTable = function(items) {
    return window.AdminAuditUi.renderAuditTable(items);
};

var renderAuditPagination = function(total, page, pageSize) {
    return window.AdminAuditUi.renderAuditPagination(total, page, pageSize);
};


// ============================================
// 实时监控
// ============================================

var _monitorTimer = null;

function _manageMonitorRefresh(active) {
    if (_monitorTimer) {
        clearInterval(_monitorTimer);
        _monitorTimer = null;
    }
    if (active) {
        var sel = document.getElementById('monitor-interval');
        var sec = parseInt(sel ? sel.value : 30) || 30;
        _monitorTimer = setInterval(loadMonitor, sec * 1000);
        // 切换刷新间隔时重启定时器
        if (sel && !sel._bound) {
            sel._bound = true;
            sel.addEventListener('change', function() {
                _manageMonitorRefresh(true);
            });
        }
    }
}

async function loadMonitor() {
    try {
        var overview = await api('GET', '/monitor/overview');
        var detail = await api('GET', '/monitor/sessions');
        if (overview) renderMonitorCards(overview);
        if (detail) renderMonitorSessions(detail.sessions || []);
    } catch (e) {
        showToast('加载监控数据失败: ' + e.message, 'error');
    }
}

var renderMonitorCards = function(data) {
    return window.AdminMonitorUi.renderMonitorCards(data);
};

function formatDuration(seconds) {
    if (!seconds || seconds < 0) return '0s';
    var h = Math.floor(seconds / 3600);
    var m = Math.floor((seconds % 3600) / 60);
    var s = seconds % 60;
    if (h > 0) return h + 'h ' + m + 'm';
    if (m > 0) return m + 'm ' + s + 's';
    return s + 's';
}

function buildMonitorSessionStatusMeta(status) {
    var normalized = String(status || '').trim().toLowerCase();
    if (normalized === 'active') {
        return { label: '在线', tone: 'badge--active', reclaimable: true };
    }
    if (normalized === 'reclaim_pending') {
        return { label: '回收中', tone: 'badge--warning', reclaimable: false };
    }
    if (normalized === 'reclaimed') {
        return { label: '已回收', tone: 'badge--inactive', reclaimable: false };
    }
    if (normalized === 'disconnected') {
        return { label: '已断开', tone: 'badge--inactive', reclaimable: false };
    }
    return {
        label: normalized ? normalized : '未知',
        tone: 'badge--inactive',
        reclaimable: false,
    };
}

function buildMonitorSessionRowViewModel(session) {
    var statusMeta = buildMonitorSessionStatusMeta(session.status);
    return {
        sessionId: session.session_id,
        userLabel: session.display_name || session.username || '',
        appName: session.app_name || '',
        startedAt: session.started_at || '',
        durationText: formatDuration(session.duration_seconds),
        lastHeartbeat: session.last_heartbeat || '',
        statusLabel: statusMeta.label,
        statusTone: statusMeta.tone,
        reclaimable: statusMeta.reclaimable,
    };
}

function buildMonitorSessionRowHtml(session) {
    var row = buildMonitorSessionRowViewModel(session);
    var actionHtml = row.reclaimable
        ? '<button class="btn btn--danger btn--small" data-action="reclaim-session" data-session-id="' + escapeAttr(row.sessionId) + '">回收</button>'
        : '<span style="color:#999;font-size:0.8rem;">-</span>';
    return '<tr>' +
        '<td>' + escapeHtml(row.userLabel) + '</td>' +
        '<td>' + escapeHtml(row.appName) + '</td>' +
        '<td style="font-size:0.8rem;">' + escapeHtml(row.startedAt) + '</td>' +
        '<td>' + escapeHtml(row.durationText) + '</td>' +
        '<td style="font-size:0.8rem;">' + escapeHtml(row.lastHeartbeat) + '</td>' +
        '<td><span class="badge ' + escapeHtml(row.statusTone) + '">' + escapeHtml(row.statusLabel) + '</span></td>' +
        '<td>' + actionHtml + '</td>' +
        '</tr>';
}

async function handleMonitorTableAction(event) {
    if (!event || !event.target || !event.target.closest) return;
    var actionEl = event.target.closest('[data-action="reclaim-session"]');
    if (!actionEl) return;
    var sessionId = (actionEl.dataset && actionEl.dataset.sessionId) || '';
    if (!sessionId && actionEl.getAttribute) {
        sessionId = actionEl.getAttribute('data-session-id') || '';
    }
    if (!sessionId) return;
    await reclaimSession(sessionId);
}

function renderMonitorSessions(sessions) {
    var tbody = document.querySelector('#monitor-table tbody');
    if (!tbody) return;
    if (!tbody._monitorActionBound) {
        tbody._monitorActionBound = true;
        tbody.addEventListener('click', function(event) {
            handleMonitorTableAction(event);
        });
    }
    tbody.innerHTML = '';

    if (!sessions.length) {
        var tr = document.createElement('tr');
        var td = document.createElement('td');
        td.colSpan = 7;
        td.style.textAlign = 'center';
        td.style.color = '#999';
        td.textContent = '当前无活跃会话';
        tr.appendChild(td);
        tbody.appendChild(tr);
        return;
    }

    sessions.forEach(function(s) {
        tbody.insertAdjacentHTML('beforeend', buildMonitorSessionRowHtml(s));
    });
}

async function reclaimSession(sessionId) {
    if (!confirm('确定回收这个活跃会话？')) return;
    try {
        await api('POST', '/pools/sessions/' + encodeURIComponent(sessionId) + '/reclaim');
        showToast('会话已回收');
        loadMonitor();
        if (_tabLoaded.pools) loadPools();
    } catch (e) { showToast('回收失败: ' + e.message, 'error'); }
}


// ============================================
// 工具函数
// ============================================

function formGroup(label, id, value, type, required, placeholder) {
    type = type || 'text';
    value = value === undefined || value === null ? '' : value;
    var req = required ? ' required' : '';
    var ph = placeholder ? ' placeholder="' + escapeAttr(placeholder) + '"' : '';
    return '<div class="form-group">' +
        '<label for="' + id + '">' + escapeHtml(label) + '</label>' +
        '<input type="' + type + '" id="' + id + '" value="' + escapeAttr(value) + '"' + req + ph + '>' +
        '</div>';
}

function formGroupSelect(label, id, options, selected) {
    var opts = options.map(function(opt) {
        var sel = opt === selected ? ' selected' : '';
        return '<option value="' + escapeAttr(opt) + '"' + sel + '>' + escapeHtml(opt) + '</option>';
    }).join('');
    return '<div class="form-group">' +
        '<label for="' + id + '">' + escapeHtml(label) + '</label>' +
        '<select id="' + id + '">' + opts + '</select></div>';
}

function closeModal(event) {
    if (event && event.target !== event.currentTarget) return;
    document.getElementById('modal-container').innerHTML = '';
}


// ============================================
// 初始化
// ============================================

function init() {
    // 认证检查
    if (!getToken()) { window.location.href = '/login.html'; return; }
    var user = getUser();
    if (!user || !user.is_admin) {
        window.location.href = '/';
        return;
    }

    // 显示用户信息
    var nameEl = document.getElementById('user-display-name');
    var infoEl = document.getElementById('user-info');
    if (nameEl) nameEl.textContent = user.display_name || user.username;
    if (infoEl) infoEl.style.display = 'flex';

    // Tab 切换事件
    document.getElementById('tab-bar').addEventListener('click', function(e) {
        var tab = e.target.getAttribute('data-tab');
        if (tab) switchTab(tab);
    });

    // 加载默认 tab (实时监控)
    _tabLoaded['monitor'] = true;
    loadMonitor();
    _manageMonitorRefresh(true);
}

document.addEventListener('DOMContentLoaded', init);
