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
 */
async function launchApp(appId, appName) {
    // 显示加载遮罩
    document.getElementById('launch-name').textContent = appName;
    document.getElementById('launch-overlay').style.display = 'flex';

    try {
        const resp = await fetch(`${API_BASE}/launch/${appId}?user_id=${CURRENT_USER_ID}`, {
            method: 'POST',
        });

        if (!resp.ok) {
            const err = await resp.json().catch(() => ({}));
            throw new Error(err.detail || `HTTP ${resp.status}`);
        }

        const data = await resp.json();
        // 新标签页打开 Guacamole 连接
        window.open(data.redirect_url, '_blank');
    } catch (e) {
        showError(`启动失败: ${e.message}`);
    } finally {
        document.getElementById('launch-overlay').style.display = 'none';
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
