(function() {
    var TASK_API = '/api/tasks';
    var _taskPoller = 0;
    var _browserState = {
        appId: 0,
        appName: '',
        currentPath: '',
        selectedPath: '',
        preflight: null,
        preflightLoading: false,
    };
    var _logPoller = 0;
    var TASK_STALL_THRESHOLD_MS = 90 * 1000;

    function taskHeaders() {
        return {
            'Authorization': 'Bearer ' + getToken(),
            'Content-Type': 'application/json',
        };
    }

    async function taskRequest(method, path, body) {
        var opts = { method: method, headers: taskHeaders() };
        if (body !== undefined) opts.body = JSON.stringify(body);
        var resp = await fetch(TASK_API + path, opts);
        if (resp.status === 401) { logout(); return null; }
        if (!resp.ok) {
            var err = await resp.json().catch(function() { return {}; });
            var message = err && err.detail && typeof err.detail === 'object'
                ? (err.detail.message || err.detail.code)
                : (err.detail || ('HTTP ' + resp.status));
            throw new Error(message);
        }
        return await resp.json();
    }

    function _statusClass(status) {
        if (status === 'succeeded' || status === 'fulfilled') return 'jobs-status jobs-status--done';
        if (status === 'failed' || status === 'cancelled') return 'jobs-status jobs-status--fail';
        return 'jobs-status';
    }

    function _closeLogPoller() {
        if (_logPoller) {
            clearInterval(_logPoller);
            _logPoller = 0;
        }
    }

    function _parseTaskTime(value) {
        if (!value) return 0;
        var normalized = String(value).replace(' ', 'T');
        var parsed = Date.parse(normalized);
        return Number.isFinite(parsed) ? parsed : 0;
    }

    function describeTaskState(task, nowMs) {
        var current = Number.isFinite(nowMs) ? nowMs : Date.now();
        var status = String((task && task.status) || '-');
        var label = status;
        var tone = status;
        var message = '';
        var isStalled = false;
        if (status === 'assigned' || status === 'preparing') {
            var startedAt = _parseTaskTime(task && (task.assigned_at || task.created_at));
            if (startedAt && current - startedAt >= TASK_STALL_THRESHOLD_MS) {
                isStalled = true;
                tone = 'failed';
                label = status + ' · 超时';
                message = 'Worker 已领取任务，但长时间没有回写运行状态。通常是共享路径、快照复制或本地预执行阶段异常。';
            }
        }
        return {
            status: status,
            tone: tone,
            label: label,
            message: message,
            isStalled: isStalled,
        };
    }

    function _updateSubmitState() {
        var submitBtn = document.getElementById('script-submit-btn');
        if (!submitBtn) return;
        var canSubmit = !!_browserState.selectedPath;
        if (_browserState.preflightLoading) canSubmit = false;
        if (_browserState.preflight && _browserState.preflight.is_schedulable === false) canSubmit = false;
        submitBtn.disabled = !canSubmit;
    }

    function renderScriptPreflight(data) {
        _browserState.preflight = data || null;
        var summaryEl = document.getElementById('script-preflight-summary');
        var reasonsEl = document.getElementById('script-preflight-reasons');
        if (!summaryEl || !reasonsEl) return;
        if (_browserState.preflightLoading) {
            summaryEl.textContent = '正在检查节点调度能力...';
            reasonsEl.innerHTML = '';
            _updateSubmitState();
            return;
        }
        if (!data) {
            summaryEl.textContent = '暂时无法获取节点调度能力';
            reasonsEl.innerHTML = '';
            _updateSubmitState();
            return;
        }
        summaryEl.textContent = data.summary || '未返回调度摘要';
        reasonsEl.innerHTML = '';
        var reasons = Array.isArray(data.reasons) ? data.reasons : [];
        if (!reasons.length) {
            reasonsEl.innerHTML = '<li>当前节点组可调度</li>';
        } else {
            reasons.forEach(function(reason) {
                var li = document.createElement('li');
                li.textContent = reason.message || reason.code || '未知原因';
                reasonsEl.appendChild(li);
            });
        }
        _updateSubmitState();
    }

    async function loadScriptPreflight() {
        _browserState.preflightLoading = true;
        renderScriptPreflight(_browserState.preflight);
        try {
            var data = await taskRequest('GET', '/preflight?requested_runtime_id=' + encodeURIComponent(_browserState.appId));
            _browserState.preflightLoading = false;
            renderScriptPreflight(data);
        } catch (e) {
            _browserState.preflightLoading = false;
            renderScriptPreflight({
                is_schedulable: false,
                summary: '节点调度能力检查失败',
                reasons: [{ message: e.message || '未知错误' }],
            });
        }
    }

    async function loadTasks() {
        try {
            var items = await taskRequest('GET', '');
            if (!items) return;
            renderTasks(items);
            if (!_taskPoller) {
                _taskPoller = setInterval(refreshTasks, 5000);
            }
        } catch (e) {
            showError('加载作业失败: ' + (e.message || ''));
        }
    }

    async function refreshTasks() {
        try {
            var items = await taskRequest('GET', '');
            if (!items) return;
            renderTasks(items);
        } catch (e) {}
    }

    function renderTasks(items) {
        var tbody = document.querySelector('#jobs-table tbody');
        if (!tbody) return;
        tbody.innerHTML = '';
        if (!items || !items.length) {
            var tr = document.createElement('tr');
            tr.innerHTML = '<td colspan="5" class="jobs-empty">暂无脚本任务</td>';
            tbody.appendChild(tr);
            return;
        }

        items.forEach(function(task) {
            var tr = document.createElement('tr');
            var createdAt = task.created_at || '-';
            var stateInfo = describeTaskState(task);
            var statusHtml = '<span class="' + _statusClass(stateInfo.tone) + '">' + escapeHtml(stateInfo.label) + '</span>';
            if (stateInfo.message) {
                statusHtml += '<div style="margin-top:0.25rem;font-size:0.78rem;color:#b45309;line-height:1.4;">' + escapeHtml(stateInfo.message) + '</div>';
            }
            var actions = '<button class="btn btn--outline" onclick="showTaskLogsModal(\'' + escapeAttr(task.task_id) + '\')">日志</button>' +
                '<button class="btn btn--outline" style="margin-left:0.3rem;" onclick="showTaskArtifactsModal(\'' + escapeAttr(task.task_id) + '\')">结果</button>';
            if (['queued', 'assigned', 'preparing', 'running', 'uploading'].indexOf(task.status) !== -1) {
                actions += '<button class="btn btn--danger" style="margin-left:0.3rem;" onclick="cancelTaskById(\'' + escapeAttr(task.task_id) + '\')">取消</button>';
            }
            tr.innerHTML =
                '<td>' + escapeHtml(task.task_id) + '</td>' +
                '<td>' + escapeHtml(task.entry_path || '-') + '</td>' +
                '<td>' + statusHtml + '</td>' +
                '<td>' + escapeHtml(createdAt) + '</td>' +
                '<td>' + actions + '</td>';
            tbody.appendChild(tr);
        });
    }

    async function showTaskSubmitModal(appId, appName) {
        _browserState.appId = appId;
        _browserState.appName = appName;
        _browserState.currentPath = '';
        _browserState.selectedPath = '';
        _browserState.preflight = null;
        _browserState.preflightLoading = true;
        var container = document.getElementById('portal-modal-container');
        if (!container) return;
        container.innerHTML =
            '<div class="modal-overlay" onclick="closePortalModal(event)">' +
            '<div class="modal" onclick="event.stopPropagation()">' +
            '<div class="modal__title">脚本模式 · ' + escapeHtml(appName) + '</div>' +
            '<div class="modal__subtitle">从“我的空间”里选择入口脚本。系统会自动冻结它所在目录的快照，再提交成平台任务。</div>' +
            '<div class="script-preflight">' +
                '<div class="script-preflight__summary" id="script-preflight-summary">正在检查节点调度能力...</div>' +
                '<ul class="script-preflight__reasons" id="script-preflight-reasons"></ul>' +
            '</div>' +
            '<div class="script-browser">' +
                '<div class="script-browser__toolbar">' +
                    '<div class="script-browser__path" id="script-browser-path">/</div>' +
                    '<button type="button" class="btn btn--outline" onclick="browseScriptParent()">上一级</button>' +
                '</div>' +
                '<div class="script-browser__list" id="script-browser-list"></div>' +
            '</div>' +
            '<div class="form-group" style="margin-top:0.8rem;">' +
                '<label>已选入口脚本</label>' +
                '<input type="text" id="script-selected-path" value="" readonly>' +
            '</div>' +
            '<div class="modal__actions">' +
                '<button type="button" class="btn btn--outline" onclick="closePortalModal()">取消</button>' +
                '<button type="button" class="btn btn--primary" id="script-submit-btn" onclick="submitSelectedScriptTask()">提交任务</button>' +
            '</div>' +
            '</div></div>';
        _updateSubmitState();
        await Promise.all([loadScriptBrowser(''), loadScriptPreflight()]);
    }

    async function loadScriptBrowser(path) {
        try {
            var resp = await fetch('/api/files/list?path=' + encodeURIComponent(path || ''), { headers: authHeaders() });
            if (resp.status === 401) { logout(); return; }
            if (!resp.ok) {
                throw new Error('HTTP ' + resp.status);
            }
            var data = await resp.json();
            _browserState.currentPath = data.path || '';
            renderScriptBrowser(data);
        } catch (e) {
            showError('加载脚本目录失败: ' + (e.message || ''));
        }
    }

    function renderScriptBrowser(data) {
        var pathEl = document.getElementById('script-browser-path');
        var listEl = document.getElementById('script-browser-list');
        var selectedEl = document.getElementById('script-selected-path');
        if (!pathEl || !listEl || !selectedEl) return;
        pathEl.textContent = '/' + (_browserState.currentPath || '');
        selectedEl.value = _browserState.selectedPath || '';
        listEl.innerHTML = '';
        (data.items || []).forEach(function(item) {
            var itemPath = (_browserState.currentPath ? (_browserState.currentPath + '/') : '') + item.name;
            var row = document.createElement('button');
            row.type = 'button';
            row.className = 'script-browser__item';
            row.onclick = function() {
                if (item.is_dir) {
                    loadScriptBrowser(itemPath);
                } else {
                    _browserState.selectedPath = itemPath;
                    selectedEl.value = itemPath;
                    _updateSubmitState();
                }
            };
            row.innerHTML =
                '<span>' + escapeHtml(item.is_dir ? ('📁 ' + item.name) : ('📄 ' + item.name)) + '</span>' +
                '<span class="script-browser__meta">' + (item.is_dir ? '目录' : formatBytes(item.size || 0)) + '</span>';
            listEl.appendChild(row);
        });
        if (!data.items || !data.items.length) {
            listEl.innerHTML = '<div class="jobs-empty">当前目录为空</div>';
        }
    }

    function browseScriptParent() {
        var current = _browserState.currentPath || '';
        if (!current) return;
        var parts = current.split('/');
        parts.pop();
        loadScriptBrowser(parts.join('/'));
    }

    async function submitSelectedScriptTask() {
        if (!_browserState.selectedPath) {
            showError('请先选择入口脚本');
            return;
        }
        if (_browserState.preflightLoading || (_browserState.preflight && _browserState.preflight.is_schedulable === false)) {
            showError('当前节点组不可调度，请先处理软件或节点问题');
            return;
        }
        try {
            await taskRequest('POST', '', {
                requested_runtime_id: _browserState.appId,
                entry_path: _browserState.selectedPath,
            });
            closePortalModal();
            switchPortalTab('jobs');
            await loadTasks();
        } catch (e) {
            showError('提交作业失败: ' + (e.message || ''));
        }
    }

    async function showTaskLogsModal(taskId) {
        var container = document.getElementById('portal-modal-container');
        if (!container) return;
        container.innerHTML =
            '<div class="modal-overlay" onclick="closePortalModal(event); _closeLogPoller();">' +
            '<div class="modal" onclick="event.stopPropagation()">' +
            '<div class="modal__title">任务日志 · ' + escapeHtml(taskId) + '</div>' +
            '<pre id="task-log-output" style="background:#0f172a;color:#e5edf8;padding:0.9rem;border-radius:8px;min-height:240px;max-height:420px;overflow:auto;font-size:0.82rem;"></pre>' +
            '<div class="modal__actions"><button type="button" class="btn btn--outline" onclick="closePortalModal(); _closeLogPoller();">关闭</button></div>' +
            '</div></div>';

        async function _render() {
            try {
                var detail = await taskRequest('GET', '/' + encodeURIComponent(taskId));
                var data = await taskRequest('GET', '/' + encodeURIComponent(taskId) + '/logs');
                if (!data || !detail) return;
                var stateInfo = describeTaskState(detail);
                var lines = (data.items || []).map(function(item) {
                    return '[' + item.seq_no + '] ' + item.message;
                });
                if (!lines.length && stateInfo.message) {
                    lines.push(stateInfo.message);
                }
                var output = document.getElementById('task-log-output');
                if (output) output.textContent = lines.join('\n') || '暂无日志';
                if (['succeeded', 'failed', 'cancelled'].indexOf(detail.status) !== -1 || stateInfo.isStalled) {
                    _closeLogPoller();
                }
            } catch (e) {}
        }

        _closeLogPoller();
        await _render();
        _logPoller = setInterval(_render, 3000);
    }

    async function showTaskArtifactsModal(taskId) {
        try {
            var data = await taskRequest('GET', '/' + encodeURIComponent(taskId) + '/artifacts');
            var items = (data && data.items) ? data.items : [];
            var listHtml = items.length
                ? items.map(function(item) {
                    var tail = item.relative_path || item.minio_object_key || item.external_url || '-';
                    return '<li style="margin-bottom:0.5rem;"><strong>' + escapeHtml(item.display_name || item.artifact_kind || 'artifact') + '</strong><br><span class="script-browser__meta">' + escapeHtml(tail) + '</span></li>';
                }).join('')
                : '<div class="jobs-empty">暂无结果索引</div>';
            var container = document.getElementById('portal-modal-container');
            if (!container) return;
            container.innerHTML =
                '<div class="modal-overlay" onclick="closePortalModal(event)">' +
                '<div class="modal" onclick="event.stopPropagation()">' +
                '<div class="modal__title">任务结果 · ' + escapeHtml(taskId) + '</div>' +
                '<div class="modal__subtitle">当前显示的是平台记录到的结果索引。实际文件请结合“我的空间 / Output”使用。</div>' +
                '<ul style="padding-left:1.2rem;">' + listHtml + '</ul>' +
                '<div class="modal__actions"><button type="button" class="btn btn--outline" onclick="closePortalModal()">关闭</button></div>' +
                '</div></div>';
        } catch (e) {
            showError('加载任务结果失败: ' + (e.message || ''));
        }
    }

    async function cancelTaskById(taskId) {
        if (!confirm('确定取消这个任务？')) return;
        try {
            await taskRequest('POST', '/' + encodeURIComponent(taskId) + '/cancel');
            await refreshTasks();
        } catch (e) {
            showError('取消任务失败: ' + (e.message || ''));
        }
    }

    window.PortalTasks = {
        loadTasks: loadTasks,
        refreshTasks: refreshTasks,
        describeTaskState: describeTaskState,
    };
    window.refreshTasks = refreshTasks;
    window.showTaskSubmitModal = showTaskSubmitModal;
    window.showTaskLogsModal = showTaskLogsModal;
    window.showTaskArtifactsModal = showTaskArtifactsModal;
    window.cancelTaskById = cancelTaskById;
    window.browseScriptParent = browseScriptParent;
    window.submitSelectedScriptTask = submitSelectedScriptTask;
})();
