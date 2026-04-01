var _currentPath = '';
var _filesState = {
    items: [],
    query: '',
    sortKey: 'name',
    groupByExt: false,
};

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
    } catch (e) {}
}

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
        _filesState.items = data.items || [];
        renderFileTable();
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

        if (!item.is_dir) {
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
        loadFiles(_currentPath);
    } catch (e) {
        showError('创建失败: ' + (e.message || ''));
    }
}
