/**
 * RemoteApp 管理后台 - 前端逻辑
 */

var API_ADMIN = '/api/admin';

// ---- 认证工具 (与 app.js 保持一致) ----
function getToken() { return localStorage.getItem('portal_token'); }
function getUser() {
    try { return JSON.parse(localStorage.getItem('portal_user')); }
    catch (e) { return null; }
}
function authHeaders() {
    return {
        'Authorization': 'Bearer ' + getToken(),
        'Content-Type': 'application/json',
    };
}
function logout() {
    localStorage.removeItem('portal_token');
    localStorage.removeItem('portal_user');
    window.location.href = '/login.html';
}

function escapeHtml(str) {
    var div = document.createElement('div');
    div.appendChild(document.createTextNode(str || ''));
    return div.innerHTML;
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
    var opts = { method: method, headers: authHeaders() };
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
var _currentTab = 'apps';
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
    // 首次加载数据
    if (!_tabLoaded[tab]) {
        _tabLoaded[tab] = true;
        if (tab === 'apps') loadApps();
        else if (tab === 'users') loadUsers();
        else if (tab === 'acl') loadAcl();
        else if (tab === 'audit') loadAuditLogs(1);
    }
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

function showAppModal(app) {
    var isEdit = !!app;
    var title = isEdit ? '编辑应用' : '新建应用';

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
        '<div class="form-group form-group--checkbox">' +
        '<input type="checkbox" id="app-ignore-cert"' + ((!app || app.ignore_cert) ? ' checked' : '') + '>' +
        '<label for="app-ignore-cert">忽略证书错误</label>' +
        '</div>' +
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
    };

    if (!data.name || !data.hostname) {
        showToast('名称和主机为必填项', 'error');
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
        (isEdit ? '<div class="form-group"><label>用户名</label><input type="text" value="' + escapeHtml(u.username) + '" disabled></div>' :
            formGroup('用户名', 'user-username', '', 'text', true)) +
        formGroup(isEdit ? '新密码（留空不改）' : '密码', 'user-password', '', 'password', !isEdit) +
        formGroup('显示名称', 'user-display', isEdit ? u.display_name : '') +
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
// 工具函数
// ============================================

function formGroup(label, id, value, type, required, placeholder) {
    type = type || 'text';
    value = value === undefined || value === null ? '' : value;
    var req = required ? ' required' : '';
    var ph = placeholder ? ' placeholder="' + escapeHtml(placeholder) + '"' : '';
    return '<div class="form-group">' +
        '<label for="' + id + '">' + escapeHtml(label) + '</label>' +
        '<input type="' + type + '" id="' + id + '" value="' + escapeHtml(String(value)) + '"' + req + ph + '>' +
        '</div>';
}

function formGroupSelect(label, id, options, selected) {
    var opts = options.map(function(opt) {
        var sel = opt === selected ? ' selected' : '';
        return '<option value="' + escapeHtml(opt) + '"' + sel + '>' + escapeHtml(opt) + '</option>';
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

    // 加载默认 tab
    _tabLoaded['apps'] = true;
    loadApps();
}

document.addEventListener('DOMContentLoaded', init);
