/**
 * RemoteApp 门户 - 前端逻辑
 */

const API_BASE = '/api/remote-apps';
const CURRENT_USER_ID = 1;  // PoC 固定用户

// 图标映射
const ICON_MAP = {
    'desktop':   '🖥️',
    'edit':      '📝',
    'calculate': '🔢',
    'folder':    '📁',
    'terminal':  '💻',
    'browser':   '🌐',
    'database':  '🗄️',
    'chart':     '📊',
};

/**
 * 获取应用列表
 */
async function fetchApps() {
    const resp = await fetch(`${API_BASE}/?user_id=${CURRENT_USER_ID}`);
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    return await resp.json();
}

/**
 * 启动应用
 * 使用 about:blank + iframe 隐藏 Guacamole 内部 URL，
 * 防止用户复制地址栏中的 token 和连接信息。
 */
async function launchApp(appId, appName) {
    // 同步打开 about:blank —— 必须在 click 事件同步调用栈中，否则被弹窗拦截器阻止
    var win = window.open('about:blank', '_blank');
    if (!win) {
        showError('弹窗被浏览器拦截，请允许本站弹出窗口');
        return;
    }

    // 立即写入加载状态页面
    win.document.write(
        '<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8">' +
        '<title>' + appName + ' - \u52A0\u8F7D\u4E2D...</title>' +
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
        '<p>\u6B63\u5728\u542F\u52A8 ' + appName + '...</p></div>' +
        '</body></html>'
    );
    win.document.close();

    try {
        var resp = await fetch(API_BASE + '/launch/' + appId + '?user_id=' + CURRENT_USER_ID, {
            method: 'POST',
        });

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
            '<title>' + appName + '</title>' +
            '<style>html,body{margin:0;padding:0;overflow:hidden}</style></head>' +
            '<body><iframe id="guac" src="' + data.redirect_url + '" ' +
            'style="width:100vw;height:100vh;border:none" ' +
            'allow="clipboard-read;clipboard-write" ' +
            'onload="this.focus()"></iframe>' +
            '<script>' +
            'var f=document.getElementById("guac");' +
            'document.body.addEventListener("click",function(){f.focus()});' +
            'document.addEventListener("keydown",function(){f.focus()},true);' +
            '</script>' +
            '</body></html>'
        );
        win.document.close();
    } catch (e) {
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
            '<p style="margin-top:.5rem;color:#aaa">' + e.message + '</p>' +
            '</div></body></html>'
        );
        win.document.close();
    }
}

/**
 * 渲染卡片
 */
function renderCards(apps) {
    const grid = document.getElementById('app-grid');
    grid.innerHTML = '';

    apps.forEach(app => {
        const card = document.createElement('div');
        card.className = 'app-card';
        card.onclick = () => launchApp(app.id, app.name);

        const icon = ICON_MAP[app.icon] || ICON_MAP['desktop'];
        const appLabel = app.remote_app
            ? app.remote_app.replace(/^\|\|/, '')
            : '远程桌面';

        card.innerHTML = `
            <span class="app-card__icon">${icon}</span>
            <div class="app-card__name">${app.name}</div>
            <div class="app-card__protocol">${app.protocol.toUpperCase()} · ${appLabel}</div>
        `;
        grid.appendChild(card);
    });
}

/**
 * 显示错误
 */
function showError(msg) {
    const el = document.getElementById('error');
    el.textContent = msg;
    el.style.display = 'block';
    setTimeout(() => { el.style.display = 'none'; }, 5000);
}

/**
 * 初始化
 */
async function init() {
    const loading = document.getElementById('loading');
    const empty = document.getElementById('empty');

    try {
        const apps = await fetchApps();
        loading.style.display = 'none';

        if (apps.length === 0) {
            empty.style.display = 'block';
            return;
        }

        renderCards(apps);
    } catch (e) {
        loading.style.display = 'none';
        showError(`加载应用列表失败: ${e.message}`);
    }
}

document.addEventListener('DOMContentLoaded', init);
