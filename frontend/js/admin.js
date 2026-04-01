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
// 应用管理
// ============================================
var _apps = [];

async function loadApps() {
    try {
        _apps = await api('GET', '/apps');
        renderAppsTable();
    } catch (e) { showToast('加载应用失败: ' + e.message, 'error'); }
}

function renderAppsTable() {
    var tbody = document.querySelector('#apps-table tbody');
    tbody.innerHTML = '';
    _apps.forEach(function(app) {
        var tr = document.createElement('tr');

        var cells = [
            app.id,
            escapeHtml(app.name),
            escapeHtml(app.hostname),
            app.port,
            escapeHtml(app.remote_app || '-'),
        ];
        cells.forEach(function(val) {
            var td = document.createElement('td');
            td.textContent = val;
            tr.appendChild(td);
        });

        // 状态
        var statusTd = document.createElement('td');
        var badge = document.createElement('span');
        badge.className = 'badge ' + (app.is_active ? 'badge--active' : 'badge--inactive');
        badge.textContent = app.is_active ? '启用' : '禁用';
        statusTd.appendChild(badge);
        tr.appendChild(statusTd);

        // 操作
        var actionTd = document.createElement('td');
        var editBtn = document.createElement('button');
        editBtn.className = 'btn btn--outline btn--small';
        editBtn.textContent = '编辑';
        editBtn.onclick = function() { showAppModal(app); };
        actionTd.appendChild(editBtn);

        if (app.is_active) {
            var delBtn = document.createElement('button');
            delBtn.className = 'btn btn--danger btn--small';
            delBtn.style.marginLeft = '0.3rem';
            delBtn.textContent = '禁用';
            delBtn.onclick = function() { deleteApp(app.id); };
            actionTd.appendChild(delBtn);
        }
        tr.appendChild(actionTd);

        tbody.appendChild(tr);
    });
}

function _chk(label, id, checked) {
    return '<div class="form-group form-group--checkbox">' +
        '<input type="checkbox" id="' + id + '"' + (checked ? ' checked' : '') + '>' +
        '<label for="' + id + '">' + escapeHtml(label) + '</label></div>';
}

async function showAppModal(app) {
    await ensurePoolsLoaded();
    if (!_pools.length) {
        showToast('请先创建资源池，再创建应用', 'error');
        return;
    }
    var isEdit = !!app;
    var title = isEdit ? '编辑应用' : '新建应用';

    // 高级参数默认值
    var adv = {
        color_depth: app ? app.color_depth : null,
        disable_gfx: app ? app.disable_gfx : true,
        resize_method: app ? (app.resize_method || 'display-update') : 'display-update',
        enable_wallpaper: app ? app.enable_wallpaper : false,
        enable_font_smoothing: app ? (app.enable_font_smoothing !== false && app.enable_font_smoothing !== 0) : true,
        disable_copy: app ? app.disable_copy : false,
        disable_paste: app ? app.disable_paste : false,
        enable_audio: app ? (app.enable_audio !== false && app.enable_audio !== 0) : true,
        enable_audio_input: app ? app.enable_audio_input : false,
        enable_printing: app ? app.enable_printing : false,
        timezone: app ? (app.timezone || '') : '',
        keyboard_layout: app ? (app.keyboard_layout || '') : '',
    };

    // 色深选项
    var depthOpts = [
        {v: '', l: '自动'},
        {v: '8', l: '8 位 (256色)'},
        {v: '16', l: '16 位 (高彩)'},
        {v: '24', l: '24 位 (真彩)'},
    ];
    var depthVal = adv.color_depth ? String(adv.color_depth) : '';
    var depthSelect = '<div class="form-group"><label>色深</label><select id="app-color-depth">';
    depthOpts.forEach(function(o) {
        depthSelect += '<option value="' + o.v + '"' + (o.v === depthVal ? ' selected' : '') + '>' + o.l + '</option>';
    });
    depthSelect += '</select></div>';

    // 时区选项
    var tzOpts = ['', 'Asia/Shanghai', 'Asia/Hong_Kong', 'Asia/Taipei', 'Asia/Tokyo', 'Asia/Seoul', 'UTC', 'America/New_York', 'Europe/London'];
    var tzSelect = '<div class="form-group"><label>时区</label><select id="app-timezone">';
    tzOpts.forEach(function(tz) {
        tzSelect += '<option value="' + tz + '"' + (tz === adv.timezone ? ' selected' : '') + '>' + (tz || '自动') + '</option>';
    });
    tzSelect += '</select></div>';

    // 键盘布局选项
    var kbOpts = [
        {v: '', l: '自动'},
        {v: 'en-us-qwerty', l: 'English (US)'},
        {v: 'ja-jp-qwerty', l: '日本語'},
        {v: 'de-de-qwertz', l: 'Deutsch'},
        {v: 'fr-fr-azerty', l: 'Français'},
        {v: 'zh-cn-qwerty', l: '中文'},
        {v: 'ko-kr', l: '한국어'},
    ];
    var kbSelect = '<div class="form-group"><label>键盘布局</label><select id="app-keyboard-layout">';
    kbOpts.forEach(function(o) {
        kbSelect += '<option value="' + o.v + '"' + (o.v === adv.keyboard_layout ? ' selected' : '') + '>' + o.l + '</option>';
    });
    kbSelect += '</select></div>';

    var poolOptions = _pools.map(function(pool) {
        var selected = app && pool.id === app.pool_id ? ' selected' : '';
        return '<option value="' + pool.id + '"' + selected + '>' + escapeHtml(pool.name) + '</option>';
    }).join('');
    var defaultPoolId = app && app.pool_id ? app.pool_id : _pools[0].id;
    var poolSelect = '<div class="form-group"><label>资源池</label><select id="app-pool-id">' +
        _pools.map(function(pool) {
            var selected = pool.id === defaultPoolId ? ' selected' : '';
            return '<option value="' + pool.id + '"' + selected + '>' + escapeHtml(pool.name) + '</option>';
        }).join('') + '</select></div>';

    var advancedHtml =
        '<details class="advanced-params">' +
        '<summary>高级 RDP 参数</summary>' +
        '<div class="advanced-params__body">' +
        // 显示与性能
        '<div class="advanced-params__section">' +
        '<div class="advanced-params__section-title">显示与性能</div>' +
        '<div class="form-row">' +
        depthSelect +
        formGroupSelect('缩放模式', 'app-resize-method', ['display-update', 'reconnect'], adv.resize_method) +
        '</div>' +
        _chk('禁用 GFX Pipeline (推荐)', 'app-disable-gfx', adv.disable_gfx) +
        _chk('显示桌面壁纸', 'app-enable-wallpaper', adv.enable_wallpaper) +
        _chk('字体平滑 (ClearType)', 'app-enable-font-smoothing', adv.enable_font_smoothing) +
        '</div>' +
        // 安全与剪贴板
        '<div class="advanced-params__section">' +
        '<div class="advanced-params__section-title">安全与剪贴板</div>' +
        _chk('禁止远程→本地复制', 'app-disable-copy', adv.disable_copy) +
        _chk('禁止本地→远程粘贴', 'app-disable-paste', adv.disable_paste) +
        '</div>' +
        // 音频与设备
        '<div class="advanced-params__section">' +
        '<div class="advanced-params__section-title">音频与设备</div>' +
        _chk('音频输出', 'app-enable-audio', adv.enable_audio) +
        _chk('麦克风输入', 'app-enable-audio-input', adv.enable_audio_input) +
        _chk('虚拟打印机 (PDF)', 'app-enable-printing', adv.enable_printing) +
        '</div>' +
        // 本地化
        '<div class="advanced-params__section">' +
        '<div class="advanced-params__section-title">本地化</div>' +
        '<div class="form-row">' +
        tzSelect + kbSelect +
        '</div></div>' +
        '</div></details>';

    var html = '<div class="modal-overlay" onclick="closeModal(event)">' +
        '<div class="modal" onclick="event.stopPropagation()">' +
        '<div class="modal__title">' + escapeHtml(title) + '</div>' +
        '<form id="app-form">' +
        '<div class="form-row">' +
        formGroup('名称', 'app-name', app ? app.name : '', 'text', true) +
        formGroup('图标', 'app-icon', app ? app.icon : 'desktop') +
        '</div>' +
        '<div class="form-row">' +
        formGroup('主机', 'app-hostname', app ? app.hostname : '', 'text', true) +
        formGroup('端口', 'app-port', app ? app.port : 3389, 'number') +
        '</div>' +
        '<div class="form-row">' +
        formGroup('RDP 用户名', 'app-rdp-user', app ? (app.rdp_username || '') : '') +
        formGroup('RDP 密码', 'app-rdp-pass', app ? (app.rdp_password || '') : '', 'password') +
        '</div>' +
        '<div class="form-row">' +
        formGroup('域名', 'app-domain', app ? (app.domain || '') : '') +
        formGroupSelect('安全模式', 'app-security', ['nla', 'tls', 'rdp', 'any'], app ? (app.security || 'nla') : 'nla') +
        '</div>' +
        formGroup('RemoteApp', 'app-remote-app', app ? (app.remote_app || '') : '', 'text', false, '如 ||notepad') +
        '<div class="form-row">' +
        formGroup('工作目录', 'app-remote-dir', app ? (app.remote_app_dir || '') : '') +
        formGroup('命令参数', 'app-remote-args', app ? (app.remote_app_args || '') : '') +
        '</div>' +
        '<div class="form-row">' +
        poolSelect +
        formGroup('成员并发上限', 'app-member-max', app ? (app.member_max_concurrent || 1) : 1, 'number', true) +
        '</div>' +
        '<div class="form-group form-group--checkbox">' +
        '<input type="checkbox" id="app-ignore-cert"' + ((!app || app.ignore_cert) ? ' checked' : '') + '>' +
        '<label for="app-ignore-cert">忽略证书错误</label>' +
        '</div>' +
        advancedHtml +
        (isEdit ? '<div class="form-group form-group--checkbox">' +
        '<input type="checkbox" id="app-is-active"' + (app.is_active ? ' checked' : '') + '>' +
        '<label for="app-is-active">启用</label></div>' : '') +
        '<div class="modal__actions">' +
        '<button type="button" class="btn btn--outline" onclick="closeModal()">取消</button>' +
        '<button type="submit" class="btn btn--primary">' + (isEdit ? '保存' : '创建') + '</button>' +
        '</div>' +
        '</form></div></div>';

    document.getElementById('modal-container').innerHTML = html;
    document.getElementById('app-form').onsubmit = function(e) {
        e.preventDefault();
        saveApp(isEdit ? app.id : null);
    };
}

async function saveApp(appId) {
    var depthVal = document.getElementById('app-color-depth').value;
    var data = {
        name: document.getElementById('app-name').value.trim(),
        icon: document.getElementById('app-icon').value.trim() || 'desktop',
        hostname: document.getElementById('app-hostname').value.trim(),
        port: parseInt(document.getElementById('app-port').value) || 3389,
        rdp_username: document.getElementById('app-rdp-user').value.trim(),
        rdp_password: document.getElementById('app-rdp-pass').value.trim(),
        domain: document.getElementById('app-domain').value.trim(),
        security: document.getElementById('app-security').value,
        ignore_cert: document.getElementById('app-ignore-cert').checked,
        remote_app: document.getElementById('app-remote-app').value.trim(),
        remote_app_dir: document.getElementById('app-remote-dir').value.trim(),
        remote_app_args: document.getElementById('app-remote-args').value.trim(),
        // RDP 高级参数
        color_depth: depthVal ? parseInt(depthVal) : null,
        disable_gfx: document.getElementById('app-disable-gfx').checked,
        resize_method: document.getElementById('app-resize-method').value,
        enable_wallpaper: document.getElementById('app-enable-wallpaper').checked,
        enable_font_smoothing: document.getElementById('app-enable-font-smoothing').checked,
        disable_copy: document.getElementById('app-disable-copy').checked,
        disable_paste: document.getElementById('app-disable-paste').checked,
        enable_audio: document.getElementById('app-enable-audio').checked,
        enable_audio_input: document.getElementById('app-enable-audio-input').checked,
        enable_printing: document.getElementById('app-enable-printing').checked,
        timezone: document.getElementById('app-timezone').value || null,
        keyboard_layout: document.getElementById('app-keyboard-layout').value || null,
        pool_id: document.getElementById('app-pool-id').value ? parseInt(document.getElementById('app-pool-id').value, 10) : null,
        member_max_concurrent: parseInt(document.getElementById('app-member-max').value, 10) || 1,
    };

    if (!data.name || !data.hostname) {
        showToast('名称和主机为必填项', 'error');
        return;
    }
    if (!data.pool_id) {
        showToast('请选择资源池', 'error');
        return;
    }

    var isActiveEl = document.getElementById('app-is-active');
    if (isActiveEl) data.is_active = isActiveEl.checked;

    try {
        if (appId) {
            await api('PUT', '/apps/' + appId, data);
            showToast('应用已更新');
        } else {
            await api('POST', '/apps', data);
            showToast('应用已创建');
        }
        closeModal();
        loadApps();
    } catch (e) { showToast(e.message, 'error'); }
}

async function deleteApp(id) {
    if (!confirm('确定要禁用此应用？')) return;
    try {
        await api('DELETE', '/apps/' + id);
        showToast('应用已禁用');
        loadApps();
    } catch (e) { showToast(e.message, 'error'); }
}


// ============================================
// 用户管理
// ============================================
var _users = [];

async function loadUsers() {
    try {
        _users = await api('GET', '/users');
        renderUsersTable();
    } catch (e) { showToast('加载用户失败: ' + e.message, 'error'); }
}

function renderUsersTable() {
    var tbody = document.querySelector('#users-table tbody');
    tbody.innerHTML = '';
    _users.forEach(function(u) {
        var tr = document.createElement('tr');

        var idTd = document.createElement('td');
        idTd.textContent = u.id;
        tr.appendChild(idTd);

        var unameTd = document.createElement('td');
        unameTd.textContent = u.username;
        tr.appendChild(unameTd);

        var dnameTd = document.createElement('td');
        dnameTd.textContent = u.display_name;
        tr.appendChild(dnameTd);

        // 角色
        var roleTd = document.createElement('td');
        if (u.is_admin) {
            var adminBadge = document.createElement('span');
            adminBadge.className = 'badge badge--admin';
            adminBadge.textContent = '管理员';
            roleTd.appendChild(adminBadge);
        } else {
            roleTd.textContent = '普通用户';
        }
        tr.appendChild(roleTd);

        // 空间
        var spaceTd = document.createElement('td');
        spaceTd.style.fontSize = '0.82rem';
        spaceTd.style.color = '#555';
        spaceTd.textContent = (u.used_display || '0 B') + ' / ' + (u.quota_display || '-');
        tr.appendChild(spaceTd);

        // 状态
        var statusTd = document.createElement('td');
        var badge = document.createElement('span');
        badge.className = 'badge ' + (u.is_active ? 'badge--active' : 'badge--inactive');
        badge.textContent = u.is_active ? '正常' : '已禁用';
        statusTd.appendChild(badge);
        tr.appendChild(statusTd);

        // 操作
        var actionTd = document.createElement('td');
        var editBtn = document.createElement('button');
        editBtn.className = 'btn btn--outline btn--small';
        editBtn.textContent = '编辑';
        editBtn.onclick = function() { showUserModal(u); };
        actionTd.appendChild(editBtn);

        if (u.is_active) {
            var delBtn = document.createElement('button');
            delBtn.className = 'btn btn--danger btn--small';
            delBtn.style.marginLeft = '0.3rem';
            delBtn.textContent = '禁用';
            delBtn.onclick = function() { deleteUser(u.id); };
            actionTd.appendChild(delBtn);
        }
        tr.appendChild(actionTd);

        tbody.appendChild(tr);
    });
}

function showUserModal(u) {
    var isEdit = !!u;
    var title = isEdit ? '编辑用户' : '新建用户';

    var html = '<div class="modal-overlay" onclick="closeModal(event)">' +
        '<div class="modal" onclick="event.stopPropagation()">' +
        '<div class="modal__title">' + escapeHtml(title) + '</div>' +
        '<form id="user-form">' +
        (isEdit ? '<div class="form-group"><label>用户名</label><input type="text" value="' + escapeAttr(u.username) + '" disabled></div>' :
            formGroup('用户名', 'user-username', '', 'text', true)) +
        formGroup(isEdit ? '新密码（留空不改）' : '密码', 'user-password', '', 'password', !isEdit) +
        formGroup('显示名称', 'user-display', isEdit ? u.display_name : '') +
        formGroupSelect('个人空间配额', 'user-quota', ['默认(10GB)', '5 GB', '10 GB', '20 GB', '50 GB', '100 GB', '不限制'],
            isEdit && u.quota_bytes ? _quotaBytesToLabel(u.quota_bytes) : '默认(10GB)') +
        '<div class="form-group form-group--checkbox">' +
        '<input type="checkbox" id="user-is-admin"' + (isEdit && u.is_admin ? ' checked' : '') + '>' +
        '<label for="user-is-admin">管理员</label>' +
        '</div>' +
        (isEdit ? '<div class="form-group form-group--checkbox">' +
        '<input type="checkbox" id="user-is-active"' + (u.is_active ? ' checked' : '') + '>' +
        '<label for="user-is-active">启用</label></div>' : '') +
        '<div class="modal__actions">' +
        '<button type="button" class="btn btn--outline" onclick="closeModal()">取消</button>' +
        '<button type="submit" class="btn btn--primary">' + (isEdit ? '保存' : '创建') + '</button>' +
        '</div>' +
        '</form></div></div>';

    document.getElementById('modal-container').innerHTML = html;
    document.getElementById('user-form').onsubmit = function(e) {
        e.preventDefault();
        saveUser(isEdit ? u.id : null);
    };
}

async function saveUser(userId) {
    var data = {};

    // 配额
    var quotaVal = document.getElementById('user-quota').value;
    data.quota_gb = _quotaLabelToGb(quotaVal);

    if (userId) {
        // 编辑
        var pw = document.getElementById('user-password').value;
        if (pw) data.password = pw;
        data.display_name = document.getElementById('user-display').value.trim();
        data.is_admin = document.getElementById('user-is-admin').checked;
        var activeEl = document.getElementById('user-is-active');
        if (activeEl) data.is_active = activeEl.checked;
    } else {
        // 新建
        data.username = document.getElementById('user-username').value.trim();
        data.password = document.getElementById('user-password').value;
        data.display_name = document.getElementById('user-display').value.trim();
        data.is_admin = document.getElementById('user-is-admin').checked;

        if (!data.username || !data.password) {
            showToast('用户名和密码为必填项', 'error');
            return;
        }
    }

    try {
        if (userId) {
            await api('PUT', '/users/' + userId, data);
            showToast('用户已更新');
        } else {
            await api('POST', '/users', data);
            showToast('用户已创建');
        }
        closeModal();
        loadUsers();
    } catch (e) { showToast(e.message, 'error'); }
}

async function deleteUser(id) {
    if (!confirm('确定要禁用此用户？')) return;
    try {
        await api('DELETE', '/users/' + id);
        showToast('用户已禁用');
        loadUsers();
    } catch (e) { showToast(e.message, 'error'); }
}


// ============================================
// ACL 权限矩阵
// ============================================

async function loadAcl() {
    try {
        var users = await api('GET', '/users');
        var apps = await api('GET', '/apps');
        // 只显示活跃的
        var activeUsers = users.filter(function(u) { return u.is_active; });
        var activeApps = apps.filter(function(a) { return a.is_active; });

        // 加载每个用户的 ACL
        var aclMap = {};
        for (var i = 0; i < activeUsers.length; i++) {
            var aclData = await api('GET', '/users/' + activeUsers[i].id + '/acl');
            aclMap[activeUsers[i].id] = aclData.app_ids || [];
        }

        renderAclMatrix(activeUsers, activeApps, aclMap);
    } catch (e) { showToast('加载权限失败: ' + e.message, 'error'); }
}

function renderAclMatrix(users, apps, aclMap) {
    var container = document.getElementById('acl-content');
    container.innerHTML = '';

    if (!users.length || !apps.length) {
        container.textContent = '暂无活跃用户或应用';
        return;
    }

    var table = document.createElement('table');
    table.className = 'acl-matrix';

    // 表头
    var thead = document.createElement('thead');
    var headerRow = document.createElement('tr');
    var th0 = document.createElement('th');
    th0.textContent = '用户 \\ 应用';
    headerRow.appendChild(th0);
    apps.forEach(function(app) {
        var th = document.createElement('th');
        th.textContent = app.name;
        headerRow.appendChild(th);
    });
    thead.appendChild(headerRow);
    table.appendChild(thead);

    // 数据行
    var tbody = document.createElement('tbody');
    users.forEach(function(user) {
        var tr = document.createElement('tr');
        var nameTd = document.createElement('td');
        nameTd.textContent = user.display_name || user.username;
        tr.appendChild(nameTd);

        var userAcl = aclMap[user.id] || [];
        apps.forEach(function(app) {
            var td = document.createElement('td');
            var cb = document.createElement('input');
            cb.type = 'checkbox';
            cb.checked = userAcl.indexOf(app.id) !== -1;
            cb.setAttribute('data-user-id', user.id);
            cb.setAttribute('data-app-id', app.id);
            td.appendChild(cb);
            tr.appendChild(td);
        });

        tbody.appendChild(tr);
    });
    table.appendChild(tbody);
    container.appendChild(table);

    // 保存按钮
    var saveBar = document.createElement('div');
    saveBar.className = 'acl-save-bar';
    var saveBtn = document.createElement('button');
    saveBtn.className = 'btn btn--primary';
    saveBtn.textContent = '保存权限';
    saveBtn.onclick = function() { saveAcl(users, apps); };
    saveBar.appendChild(saveBtn);
    container.appendChild(saveBar);
}

async function saveAcl(users, apps) {
    try {
        for (var i = 0; i < users.length; i++) {
            var userId = users[i].id;
            var appIds = [];
            var checkboxes = document.querySelectorAll('input[data-user-id="' + userId + '"]');
            checkboxes.forEach(function(cb) {
                if (cb.checked) appIds.push(parseInt(cb.getAttribute('data-app-id')));
            });
            await api('PUT', '/users/' + userId + '/acl', { app_ids: appIds });
        }
        showToast('权限已保存');
    } catch (e) { showToast('保存权限失败: ' + e.message, 'error'); }
}


// ============================================
// 审计日志
// ============================================

var _auditPage = 1;

async function loadAuditLogs(page) {
    _auditPage = page || 1;
    var params = 'page=' + _auditPage + '&page_size=20';

    var username = document.getElementById('filter-username').value.trim();
    var action = document.getElementById('filter-action').value;
    var dateStart = document.getElementById('filter-date-start').value;
    var dateEnd = document.getElementById('filter-date-end').value;

    if (username) params += '&username=' + encodeURIComponent(username);
    if (action) params += '&action=' + encodeURIComponent(action);
    if (dateStart) params += '&date_start=' + dateStart;
    if (dateEnd) params += '&date_end=' + dateEnd;

    try {
        var data = await api('GET', '/audit-logs?' + params);
        renderAuditTable(data.items);
        renderAuditPagination(data.total, data.page, data.page_size);
    } catch (e) { showToast('加载审计日志失败: ' + e.message, 'error'); }
}

var ACTION_LABELS = {
    'login': '登录',
    'login_failed': '登录失败',
    'launch_app': '启动应用',
    'admin_create_app': '创建应用',
    'admin_update_app': '修改应用',
    'admin_delete_app': '禁用应用',
    'admin_create_user': '创建用户',
    'admin_update_user': '修改用户',
    'admin_delete_user': '禁用用户',
    'admin_update_acl': '修改权限',
    'file_upload': '上传文件',
    'file_download': '下载文件',
    'file_delete': '删除文件',
};

function renderAuditTable(items) {
    var tbody = document.querySelector('#audit-table tbody');
    tbody.innerHTML = '';

    if (!items || !items.length) {
        var tr = document.createElement('tr');
        var td = document.createElement('td');
        td.colSpan = 6;
        td.style.textAlign = 'center';
        td.style.color = '#999';
        td.textContent = '暂无记录';
        tr.appendChild(td);
        tbody.appendChild(tr);
        return;
    }

    items.forEach(function(log) {
        var tr = document.createElement('tr');

        var timeTd = document.createElement('td');
        timeTd.textContent = log.created_at || '';
        timeTd.style.fontSize = '0.8rem';
        tr.appendChild(timeTd);

        var userTd = document.createElement('td');
        userTd.textContent = log.username;
        tr.appendChild(userTd);

        var actionTd = document.createElement('td');
        actionTd.textContent = ACTION_LABELS[log.action] || log.action;
        tr.appendChild(actionTd);

        var targetTd = document.createElement('td');
        targetTd.textContent = log.target_name || '-';
        tr.appendChild(targetTd);

        var ipTd = document.createElement('td');
        ipTd.textContent = log.ip_address || '-';
        ipTd.style.fontSize = '0.8rem';
        tr.appendChild(ipTd);

        var detailTd = document.createElement('td');
        detailTd.textContent = log.detail || '-';
        detailTd.style.fontSize = '0.8rem';
        detailTd.style.maxWidth = '200px';
        detailTd.style.overflow = 'hidden';
        detailTd.style.textOverflow = 'ellipsis';
        detailTd.style.whiteSpace = 'nowrap';
        tr.appendChild(detailTd);

        tbody.appendChild(tr);
    });
}

function renderAuditPagination(total, page, pageSize) {
    var el = document.getElementById('audit-pagination');
    el.innerHTML = '';

    var totalPages = Math.ceil(total / pageSize) || 1;

    if (page > 1) {
        var prevBtn = document.createElement('button');
        prevBtn.className = 'btn btn--outline btn--small';
        prevBtn.textContent = '上一页';
        prevBtn.onclick = function() { loadAuditLogs(page - 1); };
        el.appendChild(prevBtn);
    }

    var info = document.createElement('span');
    info.textContent = '第 ' + page + ' / ' + totalPages + ' 页 (共 ' + total + ' 条)';
    el.appendChild(info);

    if (page < totalPages) {
        var nextBtn = document.createElement('button');
        nextBtn.className = 'btn btn--outline btn--small';
        nextBtn.textContent = '下一页';
        nextBtn.onclick = function() { loadAuditLogs(page + 1); };
        el.appendChild(nextBtn);
    }
}


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

function renderMonitorCards(data) {
    var container = document.getElementById('monitor-cards');
    container.innerHTML = '';

    // 总览摘要
    var summary = document.getElementById('monitor-summary');
    if (summary) {
        summary.textContent = '在线 ' + data.total_online + ' 人 / ' + data.total_sessions + ' 个会话';
    }

    (data.apps || []).forEach(function(app) {
        var card = document.createElement('div');
        card.className = 'monitor-card';

        var iconEl = document.createElement('span');
        iconEl.className = 'monitor-card__icon';
        iconEl.textContent = ICON_MAP[app.icon] || ICON_MAP['desktop'];

        var info = document.createElement('div');
        info.className = 'monitor-card__info';

        var nameEl = document.createElement('div');
        nameEl.className = 'monitor-card__name';
        nameEl.textContent = app.app_name;

        var countEl = document.createElement('div');
        countEl.className = 'monitor-card__count' + (app.active_count > 0 ? ' monitor-card__count--active' : '');
        countEl.textContent = app.active_count + ' ';

        var dot = document.createElement('span');
        dot.className = 'monitor-card__dot ' + (app.active_count > 0 ? 'monitor-card__dot--green' : 'monitor-card__dot--gray');
        countEl.appendChild(dot);

        info.appendChild(nameEl);
        info.appendChild(countEl);
        card.appendChild(iconEl);
        card.appendChild(info);
        container.appendChild(card);
    });
}

function formatDuration(seconds) {
    if (!seconds || seconds < 0) return '0s';
    var h = Math.floor(seconds / 3600);
    var m = Math.floor((seconds % 3600) / 60);
    var s = seconds % 60;
    if (h > 0) return h + 'h ' + m + 'm';
    if (m > 0) return m + 'm ' + s + 's';
    return s + 's';
}

function renderMonitorSessions(sessions) {
    var tbody = document.querySelector('#monitor-table tbody');
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
        var tr = document.createElement('tr');

        var userTd = document.createElement('td');
        userTd.textContent = s.display_name || s.username;
        tr.appendChild(userTd);

        var appTd = document.createElement('td');
        appTd.textContent = s.app_name;
        tr.appendChild(appTd);

        var startTd = document.createElement('td');
        startTd.textContent = s.started_at || '';
        startTd.style.fontSize = '0.8rem';
        tr.appendChild(startTd);

        var durTd = document.createElement('td');
        durTd.textContent = formatDuration(s.duration_seconds);
        tr.appendChild(durTd);

        var hbTd = document.createElement('td');
        hbTd.textContent = s.last_heartbeat || '';
        hbTd.style.fontSize = '0.8rem';
        tr.appendChild(hbTd);

        var statusTd = document.createElement('td');
        var badge = document.createElement('span');
        badge.className = 'badge badge--active';
        badge.textContent = '在线';
        statusTd.appendChild(badge);
        tr.appendChild(statusTd);

        var actionTd = document.createElement('td');
        var reclaimBtn = document.createElement('button');
        reclaimBtn.className = 'btn btn--danger btn--small';
        reclaimBtn.textContent = '回收';
        reclaimBtn.onclick = (function(id) { return function() { reclaimSession(id); }; })(s.session_id);
        actionTd.appendChild(reclaimBtn);
        tr.appendChild(actionTd);

        tbody.appendChild(tr);
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


// ---- 配额转换 ----

function _quotaBytesToLabel(bytes) {
    if (!bytes) return '默认(10GB)';
    var gb = bytes / 1073741824;
    if (gb >= 9000) return '不限制';
    if (gb <= 5) return '5 GB';
    if (gb <= 10) return '10 GB';
    if (gb <= 20) return '20 GB';
    if (gb <= 50) return '50 GB';
    if (gb <= 100) return '100 GB';
    return '不限制';
}

function _quotaLabelToGb(label) {
    if (label === '不限制') return 9999;
    if (label === '默认(10GB)') return 0;
    var m = label.match(/(\d+)/);
    return m ? parseInt(m[1]) : 0;
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
