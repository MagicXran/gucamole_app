var _currentPath = '';
var _filesState = {
    items: [],
    query: '',
    sortKey: 'name',
    groupByExt: false,
};
var _filesRefreshTimer = 0;
var _spaceRefreshTimer = 0;
var _filesAutoRefreshRunning = false;
var _filesRefreshBurstUntil = 0;
var FILES_REFRESH_FAST_MS = 2000;
var FILES_REFRESH_STABLE_MS = 10000;
var FILES_REFRESH_BURST_WINDOW_MS = 12000;
var SPACE_REFRESH_INTERVAL_MS = 60000;

async function loadSpaceInfo(forceRefresh) {
    try {
        var url = '/api/files/space';
        if (forceRefresh) url += '?refresh=1';
        var resp = await fetch(url, {
            headers: authHeaders(),
            cache: 'no-store',
        });
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
    } catch (e) {}
}

function hasPendingTransferItems(items) {
    return (items || []).some(function(item) {
        return !item.is_dir && !!item.is_pending;
    });
}

function resolveFilesRefreshDelay(hasPendingItems) {
    var browser = window.PortalFileBrowser;
    if (browser && typeof browser.resolveRefreshDelay === 'function') {
        return browser.resolveRefreshDelay({
            hasPendingItems: !!hasPendingItems,
            nowMs: Date.now(),
            burstUntilMs: _filesRefreshBurstUntil,
        });
    }
    if (hasPendingItems || _filesRefreshBurstUntil > Date.now()) {
        return FILES_REFRESH_FAST_MS;
    }
    return FILES_REFRESH_STABLE_MS;
}

function scheduleNextFilesRefresh(delayMs) {
    if (!_filesAutoRefreshRunning) return;
    if (_currentPortalTab !== 'files' || document.hidden) return;
    if (_filesRefreshTimer) {
        clearTimeout(_filesRefreshTimer);
        _filesRefreshTimer = 0;
    }
    var delay = typeof delayMs === 'number'
        ? delayMs
        : resolveFilesRefreshDelay(hasPendingTransferItems(_filesState.items));
    _filesRefreshTimer = setTimeout(function() {
        _filesRefreshTimer = 0;
        if (!_filesAutoRefreshRunning) return;
        if (_currentPortalTab !== 'files' || document.hidden) return;
        loadFiles(_currentPath || '', { skipSpaceRefresh: false });
    }, Math.max(0, Number(delay) || 0));
}

function markFilesRefreshBurst() {
    _filesRefreshBurstUntil = Date.now() + FILES_REFRESH_BURST_WINDOW_MS;
    if (_filesAutoRefreshRunning && _currentPortalTab === 'files' && !document.hidden) {
        scheduleNextFilesRefresh(FILES_REFRESH_FAST_MS);
    }
}

async function loadFiles(path, options) {
    options = options || {};
    _currentPath = path;
    renderBreadcrumb(path);

    try {
        var resp = await fetch('/api/files/list?path=' + encodeURIComponent(path), {
            headers: authHeaders(),
            cache: 'no-store',
        });
        if (resp.status === 401) { logout(); return; }
        if (!resp.ok) {
            var err = await resp.json().catch(function() { return {}; });
            showError(err.detail || '加载文件列表失败');
            return;
        }
        var data = await resp.json();
        var nextItems = data.items || [];
        var browser = window.PortalFileBrowser;
        if (browser && typeof browser.annotatePendingTransfers === 'function') {
            nextItems = browser.annotatePendingTransfers(nextItems, _filesState.items, {
                nowSeconds: Math.floor(Date.now() / 1000),
                recentWindowSeconds: 15,
            });
        }
        var nextSignature = JSON.stringify(nextItems.map(function(item) {
            return [item.name, !!item.is_dir, Number(item.size || 0), Number(item.mtime || 0)];
        }));
        var prevSignature = JSON.stringify((_filesState.items || []).map(function(item) {
            return [item.name, !!item.is_dir, Number(item.size || 0), Number(item.mtime || 0)];
        }));
        var signatureChanged = nextSignature !== prevSignature;
        var hasPendingItems = hasPendingTransferItems(nextItems);
        _filesState.items = nextItems;
        renderFileTable();
        if (signatureChanged) {
            markFilesRefreshBurst();
        }
        if (hasPendingItems) {
            markFilesRefreshBurst();
        }
        if (!options.skipSpaceRefresh && signatureChanged) {
            loadSpaceInfo(true);
        }
    } catch (e) {
        showError('加载文件列表失败: ' + (e.message || ''));
    } finally {
        if (_filesAutoRefreshRunning && _currentPortalTab === 'files' && !document.hidden) {
            scheduleNextFilesRefresh();
        }
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

function renderFileTable() {
    var tbody = document.querySelector('#files-table tbody');
    tbody.innerHTML = '';
    var browser = window.PortalFileBrowser;
    var items = _filesState.items || [];
    if (browser && typeof browser.filterAndSortItems === 'function') {
        items = browser.filterAndSortItems(items, {
            query: _filesState.query,
            sortKey: _filesState.sortKey,
        });
    }

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

    var groups = [{ label: '', items: items }];
    if (_filesState.groupByExt && browser && typeof browser.groupItemsByExtension === 'function') {
        groups = browser.groupItemsByExtension(items);
    }

    groups.forEach(function(group) {
        if (group.label) {
            var headerTr = document.createElement('tr');
            headerTr.className = 'files-group-header';
            headerTr.innerHTML = '<td colspan="4">' + escapeHtml(group.label) + '</td>';
            tbody.appendChild(headerTr);
        }

        group.items.forEach(function(item) {
        var tr = document.createElement('tr');

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
            if (item.is_pending) {
                var pendingBadge = document.createElement('span');
                pendingBadge.textContent = '写入中';
                pendingBadge.style.marginLeft = '0.45rem';
                pendingBadge.style.padding = '0.1rem 0.35rem';
                pendingBadge.style.borderRadius = '999px';
                pendingBadge.style.fontSize = '0.72rem';
                pendingBadge.style.color = '#8a5a00';
                pendingBadge.style.background = '#fff3cd';
                nameTd.appendChild(pendingBadge);
            }
        }
        tr.appendChild(nameTd);

        var sizeTd = document.createElement('td');
        sizeTd.textContent = item.is_dir ? '-' : formatBytes(item.size);
        sizeTd.style.fontSize = '0.85rem';
        sizeTd.style.color = '#666';
        tr.appendChild(sizeTd);

        var mtimeTd = document.createElement('td');
        mtimeTd.textContent = formatTime(item.mtime);
        mtimeTd.style.fontSize = '0.85rem';
        mtimeTd.style.color = '#666';
        tr.appendChild(mtimeTd);

        var actionTd = document.createElement('td');
        var filePath = (_currentPath ? _currentPath + '/' : '') + item.name;

        if (!item.is_dir && !item.is_pending) {
            if (browser ? browser.isViewerResultFile(filePath) : isViewerResultFile(filePath)) {
                var viewBtn = document.createElement('button');
                viewBtn.className = 'btn btn--outline';
                viewBtn.style.padding = '0.2rem 0.5rem';
                viewBtn.style.fontSize = '0.8rem';
                viewBtn.style.border = '1px solid #ddd';
                viewBtn.style.borderRadius = '4px';
                viewBtn.style.cursor = 'pointer';
                viewBtn.style.background = 'transparent';
                viewBtn.textContent = '查看';
                viewBtn.onclick = (function(p) {
                    return function() {
                        window.open('/viewer.html?path=' + encodeURIComponent(p), '_blank');
                    };
                })(filePath);
                actionTd.appendChild(viewBtn);
            }

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
            if (actionTd.childNodes.length) {
                dlBtn.style.marginLeft = '0.3rem';
            }
            actionTd.appendChild(dlBtn);
        } else if (item.is_pending) {
            var pendingText = document.createElement('span');
            pendingText.textContent = '等待稳定后可下载';
            pendingText.style.fontSize = '0.78rem';
            pendingText.style.color = '#8a6d3b';
            actionTd.appendChild(pendingText);
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
    });
}

function updateFileBrowserControls() {
    var searchEl = document.getElementById('files-search');
    var sortEl = document.getElementById('files-sort');
    var groupEl = document.getElementById('files-group-ext');
    _filesState.query = searchEl ? searchEl.value.trim() : '';
    _filesState.sortKey = sortEl ? sortEl.value : 'name';
    _filesState.groupByExt = !!(groupEl && groupEl.checked);
    renderFileTable();
}

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
        markFilesRefreshBurst();
        loadFiles(_currentPath);
        loadSpaceInfo();
    } catch (e) {
        showError('删除失败: ' + (e.message || ''));
    }
}

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
        markFilesRefreshBurst();
        loadFiles(_currentPath);
    } catch (e) {
        showError('创建失败: ' + (e.message || ''));
    }
}

function refreshCurrentFiles() {
    loadFiles(_currentPath || '', { skipSpaceRefresh: false });
}

function startFilesAutoRefresh() {
    if (_filesAutoRefreshRunning) return;
    _filesAutoRefreshRunning = true;
    scheduleNextFilesRefresh(FILES_REFRESH_FAST_MS);
    if (_spaceRefreshTimer) return;
    _spaceRefreshTimer = setInterval(function() {
        if (_currentPortalTab !== 'files' || document.hidden) return;
        loadSpaceInfo(true);
    }, SPACE_REFRESH_INTERVAL_MS);
}

function stopFilesAutoRefresh() {
    _filesAutoRefreshRunning = false;
    if (_filesRefreshTimer) {
        clearTimeout(_filesRefreshTimer);
        _filesRefreshTimer = 0;
    }
    if (_spaceRefreshTimer) {
        clearInterval(_spaceRefreshTimer);
        _spaceRefreshTimer = 0;
    }
}
