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

function _writeLaunchPage(win, title, bodyHtml, bodyStyle) {
    if (!win || win.closed) return;
    win.document.open();
    win.document.write(
        '<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8">' +
        '<title>' + title + '</title>' +
        '<style>' +
        '*{margin:0;padding:0;box-sizing:border-box}' +
        'body{' + bodyStyle + '}' +
        '.spinner{width:40px;height:40px;margin:0 auto 1rem;' +
        'border:4px solid rgba(255,255,255,0.2);border-top-color:#fff;' +
        'border-radius:50%;animation:spin .8s linear infinite}' +
        '.queue-badge{display:inline-block;padding:0.35rem 0.7rem;border-radius:999px;' +
        'background:rgba(255,255,255,0.12);margin-bottom:1rem;font-size:0.9rem}' +
        '.queue-position{font-size:3rem;font-weight:700;line-height:1;margin:0.75rem 0}' +
        '.queue-note{margin-top:0.75rem;color:rgba(255,255,255,0.72);font-size:0.9rem}' +
        '@keyframes spin{to{transform:rotate(360deg)}}' +
        '</style></head><body>' +
        bodyHtml +
        '</body></html>'
    );
    win.document.close();
}

function _showLaunchLoading(win, appName) {
    var safeName = escapeHtml(appName);
    _writeLaunchPage(
        win,
        safeName + ' - 加载中...',
        '<div style="text-align:center"><div class="spinner"></div>' +
        '<p>正在启动 ' + safeName + '...</p></div>',
        'display:flex;align-items:center;justify-content:center;height:100vh;' +
        'font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Microsoft YaHei",sans-serif;' +
        'background:#1a1a2e;color:#fff'
    );
}

function _showLaunchQueue(win, appName, data) {
    var safeName = escapeHtml(appName);
    var position = parseInt(data.queue_position, 10) || 0;
    var retry = parseInt(data.retry_after_seconds, 10) || 5;
    var message = escapeHtml(data.message || '当前资源繁忙，正在等待空闲槽位');
    _writeLaunchPage(
        win,
        safeName + ' - 等待队列',
        '<div style="max-width:480px;padding:2rem;text-align:center">' +
        '<div class="queue-badge">排队中</div>' +
        '<h1 style="font-size:1.8rem;font-weight:600">' + safeName + '</h1>' +
        '<div class="queue-position">#' + position + '</div>' +
        '<p>' + message + '</p>' +
        '<p class="queue-note">系统将每 ' + retry + ' 秒自动重试一次，无需手动刷新。</p>' +
        '</div>',
        'display:flex;align-items:center;justify-content:center;height:100vh;' +
        'font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Microsoft YaHei",sans-serif;' +
        'background:linear-gradient(135deg,#0f172a,#1d4ed8);color:#fff'
    );
}

function _showLaunchError(win, msg) {
    var safeMsg = escapeHtml(msg || '未知错误');
    _writeLaunchPage(
        win,
        '启动失败',
        '<div style="text-align:center">' +
        '<p style="font-size:1.2rem">启动失败</p>' +
        '<p style="margin-top:.5rem;color:#aaa">' + safeMsg + '</p>' +
        '</div>',
        'display:flex;align-items:center;justify-content:center;height:100vh;' +
        'font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Microsoft YaHei",sans-serif;' +
        'background:#1a1a2e;color:#e74c3c'
    );
}

function _showLaunchFrame(win, appName, data) {
    var safeName = escapeHtml(appName);
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
        'var wb=new Blob(["setInterval(function(){postMessage(1)},30000)"],' +
        '{type:"text/javascript"});' +
        'var wk=new Worker(URL.createObjectURL(wb));' +
        'wk.onmessage=function(){' +
        '  try{f.contentWindow.postMessage("keepalive","*")}catch(e){}' +
        '};' +
        'var _sid="' + (data.session_id || '') + '";' +
        'var _token="' + getToken() + '";' +
        'if(_sid){' +
        '  var _hbUrl="/api/monitor/heartbeat";' +
        '  var _endUrl="/api/monitor/session-end";' +
        '  setInterval(function(){' +
        '    fetch(_hbUrl,{method:"POST",' +
        '      headers:{"Authorization":"Bearer "+_token,"Content-Type":"application/json"},' +
        '      body:JSON.stringify({session_id:_sid})' +
        '    }).catch(function(){});' +
        '  },30000);' +
        '  window.addEventListener("beforeunload",function(){' +
        '    navigator.sendBeacon(_endUrl,' +
        '      new Blob([JSON.stringify({session_id:_sid})],{type:"application/json"})' +
        '    );' +
        '  });' +
        '}' +
        '</script>' +
        '</body></html>'
    );
    win.document.close();
}

async function _pollQueuedLaunch(win, appId, appName, retryAfterSeconds) {
    var waitMs = Math.max(parseInt(retryAfterSeconds, 10) || 5, 1) * 1000;
    window.setTimeout(async function() {
        if (!win || win.closed) return;
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
            if (data.status === 'queued') {
                _showLaunchQueue(win, appName, data);
                _pollQueuedLaunch(win, appId, appName, data.retry_after_seconds);
                return;
            }
            _showLaunchFrame(win, appName, data);
        } catch (e) {
            _showLaunchError(win, e.message || '未知错误');
        }
    }, waitMs);
}

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

    _showLaunchLoading(win, appName);

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
        if (data.status === 'queued') {
            _showLaunchQueue(win, appName, data);
            _pollQueuedLaunch(win, appId, appName, data.retry_after_seconds);
        } else {
            _showLaunchFrame(win, appName, data);
        }
    } catch (e) {
        _showLaunchError(win, e.message || '未知错误');
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

// ============================================
// Portal Tab 切换
// ============================================

var _currentPortalTab = 'apps';
var _filesLoaded = false;

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


// ============================================
// 个人空间 — 配额
// ============================================

async function loadSpaceInfo() {
    try {
        var resp = await fetch('/api/files/space', { headers: authHeaders() });
        if (resp.status === 401) { logout(); return; }
        if (!resp.ok) return;
        var data = await resp.json();
        var el = document.getElementById('files-quota');
        var pct = data.usage_percent;
        var fillClass = 'files-quota__fill';
        if (pct > 95) fillClass += ' files-quota__fill--danger';
        else if (pct > 80) fillClass += ' files-quota__fill--warn';

        el.innerHTML =
            '<div class="files-quota__bar"><div class="' + fillClass + '" style="width:' + pct + '%"></div></div>' +
            '<div class="files-quota__text">' + escapeHtml(data.used_display) + ' / ' + escapeHtml(data.quota_display) + ' (' + pct + '%)</div>';
    } catch (e) {
        // silent
    }
}


// ============================================
// 个人空间 — 文件列表
// ============================================

var _currentPath = '';

async function loadFiles(path) {
    _currentPath = path;
    renderBreadcrumb(path);

    try {
        var resp = await fetch('/api/files/list?path=' + encodeURIComponent(path), { headers: authHeaders() });
        if (resp.status === 401) { logout(); return; }
        if (!resp.ok) {
            var err = await resp.json().catch(function() { return {}; });
            showError(err.detail || '加载文件列表失败');
            return;
        }
        var data = await resp.json();
        renderFileTable(data.items || []);
    } catch (e) {
        showError('加载文件列表失败: ' + (e.message || ''));
    }
}

function renderBreadcrumb(path) {
    var el = document.getElementById('files-breadcrumb');
    el.innerHTML = '';
    var root = document.createElement('a');
    root.textContent = '根目录';
    root.onclick = function() { loadFiles(''); };
    el.appendChild(root);

    if (path) {
        var parts = path.split('/').filter(function(p) { return p; });
        var acc = '';
        parts.forEach(function(part) {
            acc += (acc ? '/' : '') + part;
            var sep = document.createElement('span');
            sep.textContent = '/';
            el.appendChild(sep);
            var link = document.createElement('a');
            link.textContent = part;
            link.onclick = (function(p) { return function() { loadFiles(p); }; })(acc);
            el.appendChild(link);
        });
    }
}

function renderFileTable(items) {
    var tbody = document.querySelector('#files-table tbody');
    tbody.innerHTML = '';

    if (!items.length) {
        var tr = document.createElement('tr');
        var td = document.createElement('td');
        td.colSpan = 4;
        td.style.textAlign = 'center';
        td.style.color = '#999';
        td.style.padding = '2rem';
        td.textContent = '空文件夹';
        tr.appendChild(td);
        tbody.appendChild(tr);
        return;
    }

    items.forEach(function(item) {
        var tr = document.createElement('tr');

        // 名称
        var nameTd = document.createElement('td');
        var nameSpan = document.createElement('span');
        nameSpan.className = 'files-table__icon';
        nameSpan.textContent = item.is_dir ? '\uD83D\uDCC1' : '\uD83D\uDCC4';
        nameTd.appendChild(nameSpan);

        if (item.is_dir) {
            var link = document.createElement('span');
            link.className = 'files-table__name';
            link.textContent = item.name;
            var dirPath = (_currentPath ? _currentPath + '/' : '') + item.name;
            link.onclick = (function(p) { return function() { loadFiles(p); }; })(dirPath);
            nameTd.appendChild(link);
        } else {
            var fname = document.createElement('span');
            fname.textContent = item.name;
            nameTd.appendChild(fname);
        }
        tr.appendChild(nameTd);

        // 大小
        var sizeTd = document.createElement('td');
        sizeTd.textContent = item.is_dir ? '-' : formatBytes(item.size);
        sizeTd.style.fontSize = '0.85rem';
        sizeTd.style.color = '#666';
        tr.appendChild(sizeTd);

        // 修改时间
        var mtimeTd = document.createElement('td');
        mtimeTd.textContent = formatTime(item.mtime);
        mtimeTd.style.fontSize = '0.85rem';
        mtimeTd.style.color = '#666';
        tr.appendChild(mtimeTd);

        // 操作
        var actionTd = document.createElement('td');
        var filePath = (_currentPath ? _currentPath + '/' : '') + item.name;

        if (!item.is_dir) {
            var dlBtn = document.createElement('button');
            dlBtn.className = 'btn btn--outline';
            dlBtn.style.padding = '0.2rem 0.5rem';
            dlBtn.style.fontSize = '0.8rem';
            dlBtn.style.border = '1px solid #ddd';
            dlBtn.style.borderRadius = '4px';
            dlBtn.style.cursor = 'pointer';
            dlBtn.style.background = 'transparent';
            dlBtn.textContent = '下载';
            dlBtn.onclick = (function(p) { return function() { downloadFile(p); }; })(filePath);
            actionTd.appendChild(dlBtn);
        }

        var delBtn = document.createElement('button');
        delBtn.style.padding = '0.2rem 0.5rem';
        delBtn.style.fontSize = '0.8rem';
        delBtn.style.border = 'none';
        delBtn.style.borderRadius = '4px';
        delBtn.style.cursor = 'pointer';
        delBtn.style.background = '#e74c3c';
        delBtn.style.color = '#fff';
        delBtn.style.marginLeft = '0.3rem';
        delBtn.textContent = '删除';
        delBtn.onclick = (function(p, n) { return function() { deleteItem(p, n); }; })(filePath, item.name);
        actionTd.appendChild(delBtn);
        tr.appendChild(actionTd);

        tbody.appendChild(tr);
    });
}


// ============================================
// 个人空间 — 下载
// ============================================

async function downloadFile(path) {
    try {
        var resp = await fetch('/api/files/download-token', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + getToken() },
            body: JSON.stringify({ path: path }),
        });
        if (resp.status === 401) { logout(); return; }
        if (!resp.ok) {
            var err = await resp.json().catch(function() { return {}; });
            showError(err.detail || '获取下载链接失败');
            return;
        }
        var data = await resp.json();
        window.open('/api/files/download?path=' + encodeURIComponent(path) + '&_token=' + data.token);
    } catch (e) {
        showError('下载失败: ' + (e.message || ''));
    }
}


// ============================================
// 个人空间 — 删除
// ============================================

async function deleteItem(path, name) {
    if (!confirm('确定删除 "' + name + '"？')) return;
    try {
        var resp = await fetch('/api/files/file?path=' + encodeURIComponent(path), {
            method: 'DELETE',
            headers: authHeaders(),
        });
        if (resp.status === 401) { logout(); return; }
        if (!resp.ok) {
            var err = await resp.json().catch(function() { return {}; });
            showError(err.detail || '删除失败');
            return;
        }
        loadFiles(_currentPath);
        loadSpaceInfo();
    } catch (e) {
        showError('删除失败: ' + (e.message || ''));
    }
}


// ============================================
// 个人空间 — 新建文件夹
// ============================================

async function createFolder() {
    var name = prompt('文件夹名称');
    if (!name || !name.trim()) return;
    name = name.trim();

    var path = (_currentPath ? _currentPath + '/' : '') + name;
    try {
        var resp = await fetch('/api/files/mkdir', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + getToken() },
            body: JSON.stringify({ path: path }),
        });
        if (resp.status === 401) { logout(); return; }
        if (!resp.ok) {
            var err = await resp.json().catch(function() { return {}; });
            showError(err.detail || '创建失败');
            return;
        }
        loadFiles(_currentPath);
    } catch (e) {
        showError('创建失败: ' + (e.message || ''));
    }
}


// ============================================
// 个人空间 — 分片上传
// ============================================

var _uploads = {};
var CHUNK_SIZE = 10 * 1024 * 1024;  // 10MB

function triggerUpload() {
    document.getElementById('file-input').click();
}

function _handleFileSelect(evt) {
    var files = evt.target.files;
    for (var i = 0; i < files.length; i++) {
        uploadFile(files[i], _currentPath);
    }
    evt.target.value = '';
}

async function uploadFile(file, targetDir) {
    var path = (targetDir ? targetDir + '/' : '') + file.name;
    var id = Date.now() + '_' + Math.random().toString(36).slice(2, 8);

    _uploads[id] = {
        file: file, path: path, name: file.name,
        offset: 0, size: file.size, speed: 0,
        aborted: false, controller: new AbortController(),
        status: 'uploading', error: '',
    };

    renderUploads();

    try {
        // init
        var initForm = new FormData();
        initForm.append('path', path);
        initForm.append('size', file.size);

        var initResp = await fetch('/api/files/upload/init', {
            method: 'POST',
            headers: { 'Authorization': 'Bearer ' + getToken() },
            body: initForm,
            signal: _uploads[id].controller.signal,
        });
        if (initResp.status === 401) { logout(); return; }
        if (!initResp.ok) {
            var err = await initResp.json().catch(function() { return {}; });
            _uploads[id].status = 'error';
            _uploads[id].error = err.detail || 'init 失败';
            renderUploads();
            return;
        }
        var initData = await initResp.json();
        var uploadId = initData.upload_id;
        var offset = initData.offset || 0;

        _uploads[id].offset = offset;
        _uploads[id].uploadId = uploadId;
        renderUploads();

        // chunk loop
        var chunkTimes = [];
        while (offset < file.size) {
            if (_uploads[id].aborted) return;

            var end = Math.min(offset + CHUNK_SIZE, file.size);
            var blob = file.slice(offset, end);

            var chunkForm = new FormData();
            chunkForm.append('upload_id', uploadId);
            chunkForm.append('offset', offset);
            chunkForm.append('chunk', blob, file.name);

            var t0 = Date.now();
            var chunkResp = await fetch('/api/files/upload/chunk', {
                method: 'POST',
                headers: { 'Authorization': 'Bearer ' + getToken() },
                body: chunkForm,
                signal: _uploads[id].controller.signal,
            });

            if (!chunkResp.ok) {
                var cerr = await chunkResp.json().catch(function() { return {}; });
                _uploads[id].status = 'error';
                _uploads[id].error = cerr.detail || 'chunk 失败';
                renderUploads();
                return;
            }

            var chunkData = await chunkResp.json();
            var elapsed = (Date.now() - t0) / 1000;
            chunkTimes.push({ bytes: end - offset, time: elapsed });
            if (chunkTimes.length > 5) chunkTimes.shift();

            offset = chunkData.offset;
            _uploads[id].offset = offset;
            _uploads[id].speed = calcSpeed(chunkTimes);
            renderUploads();

            if (chunkData.complete) {
                _uploads[id].status = 'done';
                renderUploads();
                loadFiles(_currentPath);
                loadSpaceInfo();
                // 3秒后移除完成条目
                setTimeout(function(uid) { delete _uploads[uid]; renderUploads(); }, 3000, id);
                return;
            }
        }
    } catch (e) {
        if (!_uploads[id]) return;  // 已被 cancelUpload() 清理
        if (e.name === 'AbortError') {
            _uploads[id].status = 'cancelled';
        } else {
            _uploads[id].status = 'error';
            _uploads[id].error = e.message || '上传失败';
        }
        renderUploads();
    }
}

function cancelUpload(id) {
    var u = _uploads[id];
    if (!u) return;
    u.aborted = true;
    u.controller.abort();
    // 取消服务端
    if (u.uploadId) {
        fetch('/api/files/upload/' + u.uploadId, {
            method: 'DELETE',
            headers: authHeaders(),
        }).catch(function() {});
    }
    delete _uploads[id];
    renderUploads();
}

function calcSpeed(chunkTimes) {
    if (!chunkTimes.length) return 0;
    var totalBytes = 0, totalTime = 0;
    chunkTimes.forEach(function(c) { totalBytes += c.bytes; totalTime += c.time; });
    return totalTime > 0 ? totalBytes / totalTime : 0;
}

function renderUploads() {
    var container = document.getElementById('files-uploads');
    if (!container) return;
    var keys = Object.keys(_uploads);
    if (!keys.length) { container.innerHTML = ''; return; }

    var html = '';
    keys.forEach(function(id) {
        var u = _uploads[id];
        var pct = u.size > 0 ? Math.round(u.offset / u.size * 100) : 0;
        var fillClass = 'files-upload-item__fill';
        if (u.status === 'done') fillClass += ' files-upload-item__fill--done';
        else if (u.status === 'error') fillClass += ' files-upload-item__fill--error';

        var statusText = '';
        if (u.status === 'done') statusText = '完成';
        else if (u.status === 'error') statusText = u.error;
        else if (u.status === 'cancelled') statusText = '已取消';
        else statusText = formatBytes(u.offset) + ' / ' + formatBytes(u.size);

        var speedText = u.status === 'uploading' && u.speed > 0 ? formatBytes(u.speed) + '/s' : '';

        html += '<div class="files-upload-item">' +
            '<div class="files-upload-item__name"><span>' + escapeHtml(u.name) + '</span>' +
            (u.status === 'uploading' ? '<button class="files-upload-item__cancel" onclick="cancelUpload(\'' + id + '\')">取消</button>' : '') +
            '</div>' +
            '<div class="files-upload-item__progress"><div class="' + fillClass + '" style="width:' + pct + '%"></div></div>' +
            '<div class="files-upload-item__info"><span>' + statusText + '</span><span>' + speedText + '</span></div>' +
            '</div>';
    });
    container.innerHTML = html;
}


// ============================================
// 个人空间 — 拖拽上传
// ============================================

var _dragCounter = 0;

function _initDragDrop() {
    var body = document.body;
    body.addEventListener('dragenter', function(e) {
        if (_currentPortalTab !== 'files') return;
        e.preventDefault();
        _dragCounter++;
        document.getElementById('files-dropzone').classList.add('files-dropzone--active');
    });
    body.addEventListener('dragleave', function(e) {
        _dragCounter--;
        if (_dragCounter <= 0) {
            _dragCounter = 0;
            document.getElementById('files-dropzone').classList.remove('files-dropzone--active');
        }
    });
    body.addEventListener('dragover', function(e) {
        if (_currentPortalTab !== 'files') return;
        e.preventDefault();
    });
    body.addEventListener('drop', function(e) {
        e.preventDefault();
        _dragCounter = 0;
        document.getElementById('files-dropzone').classList.remove('files-dropzone--active');
        if (_currentPortalTab !== 'files') return;

        var files = e.dataTransfer.files;
        for (var i = 0; i < files.length; i++) {
            uploadFile(files[i], _currentPath);
        }
    });
}


// ============================================
// 个人空间 — 使用说明折叠
// ============================================

function _initTip() {
    var hidden = localStorage.getItem('portal_files_tip_hidden') === '1';
    if (hidden) {
        var el = document.getElementById('files-tip');
        if (el) el.style.display = 'none';
    }
}

function closeTip() {
    var el = document.getElementById('files-tip');
    if (el) el.style.display = 'none';
    localStorage.setItem('portal_files_tip_hidden', '1');
}


// ============================================
// 格式化工具
// ============================================

function formatBytes(bytes) {
    if (bytes === 0) return '0 B';
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB';
    if (bytes < 1073741824) return (bytes / 1048576).toFixed(1) + ' MB';
    return (bytes / 1073741824).toFixed(2) + ' GB';
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

    // Tab 切换
    document.getElementById('portal-tabs').addEventListener('click', function(e) {
        var tab = e.target.getAttribute('data-tab');
        if (tab) switchPortalTab(tab);
    });

    // 文件选择
    document.getElementById('file-input').addEventListener('change', _handleFileSelect);

    // 拖拽上传
    _initDragDrop();

    // 上传列表容器
    var uploadsDiv = document.createElement('div');
    uploadsDiv.className = 'files-uploads';
    uploadsDiv.id = 'files-uploads';
    document.body.appendChild(uploadsDiv);
}

document.addEventListener('DOMContentLoaded', init);
