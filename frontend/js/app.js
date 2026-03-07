/**
 * RemoteApp 门户 - 前端逻辑
 */

const API_BASE = '/api/remote-apps';

// ---- HTML 转义 (防 XSS) ----
function escapeHtml(str) {
    var div = document.createElement('div');
    div.appendChild(document.createTextNode(str));
    return div.innerHTML;
}

// ---- 认证工具函数 ----
function getToken() { return localStorage.getItem('portal_token'); }
function getUser() {
    try { return JSON.parse(localStorage.getItem('portal_user')); }
    catch (e) { return null; }
}
function authHeaders() { return { 'Authorization': 'Bearer ' + getToken() }; }
function logout() {
    localStorage.removeItem('portal_token');
    localStorage.removeItem('portal_user');
    window.location.href = '/login.html';
}
function requireAuth() {
    if (!getToken()) { window.location.href = '/login.html'; return false; }
    return true;
}

// 图标映射
const ICON_MAP = {
    'desktop':   '\u{1F5A5}\uFE0F',
    'edit':      '\u{1F4DD}',
    'calculate': '\u{1F522}',
    'folder':    '\u{1F4C1}',
    'terminal':  '\u{1F4BB}',
    'browser':   '\u{1F310}',
    'database':  '\u{1F5C4}\uFE0F',
    'chart':     '\u{1F4CA}',
};

/**
 * 获取应用列表
 */
async function fetchApps() {
    var resp = await fetch(API_BASE + '/', { headers: authHeaders() });
    if (resp.status === 401) { logout(); return []; }
    if (!resp.ok) throw new Error('HTTP ' + resp.status);
    return await resp.json();
}

// ---- 防重复点击锁 ----
var _launchLock = {};

/**
 * 启动应用
 * 使用 about:blank + iframe 隐藏 Guacamole 内部 URL，
 * 防止用户复制地址栏中的 token 和连接信息。
 */
async function launchApp(appId, appName) {
    // 3 秒内同一应用不可重复点击
    if (_launchLock[appId] && Date.now() - _launchLock[appId] < 3000) return;
    _launchLock[appId] = Date.now();

    // 同步打开 about:blank —— 必须在 click 事件同步调用栈中，否则被弹窗拦截器阻止
    var win = window.open('about:blank', '_blank');
    if (!win) {
        showError('弹窗被浏览器拦截，请允许本站弹出窗口');
        return;
    }

    var safeName = escapeHtml(appName);

    // 立即写入加载状态页面
    win.document.write(
        '<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8">' +
        '<title>' + safeName + ' - \u52A0\u8F7D\u4E2D...</title>' +
        '<style>' +
        '*{margin:0;padding:0}' +
        'body{display:flex;align-items:center;justify-content:center;height:100vh;' +
        'font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Microsoft YaHei",sans-serif;' +
        'background:#1a1a2e;color:#fff}' +
        '.spinner{width:40px;height:40px;margin:0 auto 1rem;' +
        'border:4px solid rgba(255,255,255,0.2);border-top-color:#fff;' +
        'border-radius:50%;animation:spin .8s linear infinite}' +
        '@keyframes spin{to{transform:rotate(360deg)}}' +
        '</style></head><body>' +
        '<div style="text-align:center"><div class="spinner"></div>' +
        '<p>\u6B63\u5728\u542F\u52A8 ' + safeName + '...</p></div>' +
        '</body></html>'
    );
    win.document.close();

    try {
        var resp = await fetch(API_BASE + '/launch/' + appId, {
            method: 'POST',
            headers: authHeaders(),
        });

        if (resp.status === 401) { win.close(); logout(); return; }

        if (!resp.ok) {
            var err = await resp.json().catch(function() { return {}; });
            throw new Error(err.detail || 'HTTP ' + resp.status);
        }

        var data = await resp.json();

        // 用 iframe 加载 Guacamole —— 地址栏保持 about:blank
        // 关键: iframe 必须获得焦点，否则键盘事件落在 parent document 上，Guacamole 收不到
        win.document.open();
        win.document.write(
            '<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8">' +
            '<title>' + safeName + '</title>' +
            '<style>html,body{margin:0;padding:0;overflow:hidden}</style></head>' +
            '<body><iframe id="guac" src="' + escapeHtml(data.redirect_url) + '" ' +
            'style="width:100vw;height:100vh;border:none" ' +
            'allow="clipboard-read;clipboard-write" ' +
            'onload="this.focus()"></iframe>' +
            '<script>' +
            'var f=document.getElementById("guac");' +
            'document.body.addEventListener("click",function(){f.focus()});' +
            'document.addEventListener("keydown",function(e){' +
            '  if(document.activeElement!==f){e.preventDefault();f.focus();}' +
            '},true);' +
            // Web Worker keepalive: 防止浏览器后台节流冻结 Guacamole 的 NOP ping
            'var wb=new Blob(["setInterval(function(){postMessage(1)},30000)"],' +
            '{type:"text/javascript"});' +
            'var wk=new Worker(URL.createObjectURL(wb));' +
            'wk.onmessage=function(){' +
            '  try{f.contentWindow.postMessage("keepalive","*")}catch(e){}' +
            '};' +
            '</script>' +
            '</body></html>'
        );
        win.document.close();
    } catch (e) {
        var safeMsg = escapeHtml(e.message || '未知错误');
        win.document.open();
        win.document.write(
            '<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8">' +
            '<title>\u542F\u52A8\u5931\u8D25</title>' +
            '<style>' +
            '*{margin:0;padding:0}' +
            'body{display:flex;align-items:center;justify-content:center;height:100vh;' +
            'font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Microsoft YaHei",sans-serif;' +
            'background:#1a1a2e;color:#e74c3c}' +
            '</style></head><body>' +
            '<div style="text-align:center">' +
            '<p style="font-size:1.2rem">\u542F\u52A8\u5931\u8D25</p>' +
            '<p style="margin-top:.5rem;color:#aaa">' + safeMsg + '</p>' +
            '</div></body></html>'
        );
        win.document.close();
    } finally {
        delete _launchLock[appId];
    }
}

/**
 * 渲染卡片 (DOM API 构建，防止 XSS)
 */
function renderCards(apps) {
    var grid = document.getElementById('app-grid');
    grid.innerHTML = '';

    apps.forEach(function(app) {
        var card = document.createElement('div');
        card.className = 'app-card';
        card.onclick = function() { launchApp(app.id, app.name); };

        var icon = ICON_MAP[app.icon] || ICON_MAP['desktop'];
        var appLabel = app.remote_app
            ? app.remote_app.replace(/^\|\|/, '')
            : '远程桌面';

        var iconSpan = document.createElement('span');
        iconSpan.className = 'app-card__icon';
        iconSpan.textContent = icon;

        var nameDiv = document.createElement('div');
        nameDiv.className = 'app-card__name';
        nameDiv.textContent = app.name;

        var protoDiv = document.createElement('div');
        protoDiv.className = 'app-card__protocol';
        protoDiv.textContent = app.protocol.toUpperCase() + ' \u00B7 ' + appLabel;

        card.appendChild(iconSpan);
        card.appendChild(nameDiv);
        card.appendChild(protoDiv);
        grid.appendChild(card);
    });
}

/**
 * 显示错误
 */
function showError(msg) {
    var el = document.getElementById('error');
    el.textContent = msg;
    el.style.display = 'block';
    setTimeout(function() { el.style.display = 'none'; }, 5000);
}

/**
 * 初始化
 */
async function init() {
    if (!requireAuth()) return;

    // 显示用户信息
    var user = getUser();
    if (user) {
        var nameEl = document.getElementById('user-display-name');
        var infoEl = document.getElementById('user-info');
        if (nameEl) nameEl.textContent = user.display_name || user.username;
        if (infoEl) infoEl.style.display = 'flex';

        // 管理员显示管理入口
        var adminLink = document.getElementById('admin-link');
        if (adminLink && user.is_admin) {
            adminLink.style.display = 'inline';
        }
    }

    var loading = document.getElementById('loading');
    var empty = document.getElementById('empty');

    try {
        var apps = await fetchApps();
        loading.style.display = 'none';

        if (apps.length === 0) {
            empty.style.display = 'block';
            return;
        }

        renderCards(apps);
    } catch (e) {
        loading.style.display = 'none';
        showError('加载应用列表失败: ' + (e.message || '未知错误'));
    }
}

document.addEventListener('DOMContentLoaded', init);
