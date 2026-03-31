/**
 * RemoteApp 门户 - 核心壳层
 */

const API_BASE = '/api/remote-apps';
var _currentPortalTab = 'apps';
var _filesLoaded = false;

async function fetchApps() {
    var resp = await fetch(API_BASE + '/', { headers: authHeaders() });
    if (resp.status === 401) { logout(); return []; }
    if (!resp.ok) throw new Error('HTTP ' + resp.status);
    return await resp.json();
}

function showError(msg) {
    var el = document.getElementById('error');
    el.textContent = msg;
    el.style.display = 'block';
    setTimeout(function() { el.style.display = 'none'; }, 5000);
}

function switchPortalTab(tab) {
    _currentPortalTab = tab;
    document.querySelectorAll('.portal-tabs__btn').forEach(function(btn) {
        btn.classList.toggle('portal-tabs__btn--active', btn.getAttribute('data-tab') === tab);
    });
    document.getElementById('apps-panel').style.display = tab === 'apps' ? '' : 'none';
    document.getElementById('files-panel').style.display = tab === 'files' ? '' : 'none';

    if (tab === 'files' && !_filesLoaded) {
        _filesLoaded = true;
        loadSpaceInfo();
        loadFiles('');
        _initTip();
    }
}

function formatBytes(bytes) {
    if (bytes === 0) return '0 B';
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB';
    if (bytes < 1073741824) return (bytes / 1048576).toFixed(1) + ' MB';
    return (bytes / 1073741824).toFixed(2) + ' GB';
}

function isViewerResultFile(path) {
    var normalized = String(path || '').replace(/\\/g, '/');
    if (normalized.toLowerCase().indexOf('output/') !== 0) return false;
    var dot = normalized.lastIndexOf('.');
    if (dot < 0) return false;
    var ext = normalized.slice(dot).toLowerCase();
    return ['.vtp', '.vtu', '.stl', '.obj'].indexOf(ext) !== -1;
}

function formatTime(ts) {
    if (!ts) return '-';
    var d = new Date(ts * 1000);
    var mm = String(d.getMonth() + 1).padStart(2, '0');
    var dd = String(d.getDate()).padStart(2, '0');
    var hh = String(d.getHours()).padStart(2, '0');
    var mi = String(d.getMinutes()).padStart(2, '0');
    return mm + '-' + dd + ' ' + hh + ':' + mi;
}

async function init() {
    if (!requireAuth()) return;

    var user = getUser();
    if (user) {
        var nameEl = document.getElementById('user-display-name');
        var infoEl = document.getElementById('user-info');
        if (nameEl) nameEl.textContent = user.display_name || user.username;
        if (infoEl) infoEl.style.display = 'flex';

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

    document.getElementById('portal-tabs').addEventListener('click', function(e) {
        var tab = e.target.getAttribute('data-tab');
        if (tab) switchPortalTab(tab);
    });
    document.getElementById('file-input').addEventListener('change', _handleFileSelect);
    _initDragDrop();

    var uploadsDiv = document.createElement('div');
    uploadsDiv.className = 'files-uploads';
    uploadsDiv.id = 'files-uploads';
    document.body.appendChild(uploadsDiv);
}

document.addEventListener('DOMContentLoaded', init);
